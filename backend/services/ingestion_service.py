"""
Background data ingestion service.

Data sources (all real, all free, no mock):
  1. USGS GeoJSON       — earthquakes         (no key, past 1h)
  2. NASA FIRMS VIIRS   — wildfires            (NASA key required, past 24h)
  3. OpenWeatherMap     — floods / storms      (OWM key required, current)
  4. GDACS UN RSS       — floods / hurricanes / tsunamis (no key, RSS feed)
  5. NOAA NHC JSON      — Atlantic/Pacific hurricanes (no key, active storms)
  6. NOAA PTWC          — tsunami warnings     (no key, active warnings)

All external URLs are loaded from settings (config.py / .env) — nothing
is hard-coded here.  Location data (country, state/region, city) is
resolved with the offline `reverse_geocoder` library so any country,
state, province, or city is supported without any API key or manual
country lists.
"""
from __future__ import annotations

import asyncio
import csv
import io
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from functools import lru_cache
from typing import Optional

import httpx
import pycountry
import reverse_geocoder as rg  # pip install reverse_geocoder

from core.config import get_settings
from db.database import AsyncSessionLocal
from models.disaster import DisasterType, SeverityLevel
from schemas.disaster import DisasterEventCreate
from services.disaster_service import DisasterService
from websocket.manager import manager

logger   = logging.getLogger(__name__)
settings = get_settings()


# Offline reverse-geocoding  — covers every nation, state, city
@lru_cache(maxsize=8192)
def _geocode_cached(lat_r: float, lon_r: float) -> tuple[str | None, str | None, str | None]:
    """
    Core geocoding call — arguments are pre-rounded so the LRU cache is
    effective across events that land in the same ~11 km cell.
    """
    try:
        result = rg.get((lat_r, lon_r))          # single tuple → single dict
        alpha2 = (result.get("cc") or "").upper()
        try:
            country_name: str | None = pycountry.countries.get(alpha_2=alpha2).name # type: ignore
        except AttributeError:
            country_name = alpha2 or None          # fall back to ISO-2 code
        region = result.get("admin1") or None      # state / province / oblast …
        city   = result.get("name")  or None       # nearest populated place
        return country_name, region, city
    except Exception:
        return None, None, None


def _get_location_info(lat: float, lon: float) -> tuple[str | None, str | None, str | None]:
    """
    Public wrapper.  Rounds lat/lon to 1 decimal place before hitting the
    cache so floating-point variance doesn't produce cache misses.

    Returns (country_name, state_or_region, city).
    All three values can be None if geocoding fails.
    """
    return _geocode_cached(round(lat, 1), round(lon, 1))


# ── datetime helper ───────────────────────────────────────────────────────────

def _parse_dt_safe(s: str, fallback: datetime) -> datetime:
    if not s:
        return fallback
    for fmt in [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S GMT",
    ]:
        try:
            dt = datetime.strptime(s[:25], fmt)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return fallback


# ══════════════════════════════════════════════════════════════════════════════
# 1. USGS — Earthquakes
# ══════════════════════════════════════════════════════════════════════════════

def _magnitude_to_severity(mag: float) -> SeverityLevel:
    if mag < 3.0: return SeverityLevel.LOW
    if mag < 5.0: return SeverityLevel.MEDIUM
    if mag < 7.0: return SeverityLevel.HIGH
    return SeverityLevel.CRITICAL


async def fetch_usgs_earthquakes(client: httpx.AsyncClient) -> list[DisasterEventCreate]:
    events: list[DisasterEventCreate] = []
    try:
        resp = await client.get(settings.USGS_API_URL, timeout=15)
        resp.raise_for_status()
        for feature in resp.json().get("features", []):
            props  = feature.get("properties", {})
            coords = feature["geometry"]["coordinates"]
            mag    = props.get("mag") or 0
            if mag < 1.0:
                continue

            lat  = float(coords[1])
            lon  = float(coords[0])
            place: str = props.get("place", "") or ""

            # ── proper offline reverse-geocoding ──────────────────────────────
            country, region, city = _get_location_info(lat, lon)
            # ─────────────────────────────────────────────────────────────────

            occurred_at = datetime.fromtimestamp(
                props.get("time", 0) / 1000, tz=timezone.utc
            )
            events.append(DisasterEventCreate(
                external_id=props.get("code") or feature.get("id"),
                type=DisasterType.EARTHQUAKE,
                severity=_magnitude_to_severity(float(mag)),
                title=props.get("title", f"M{mag} Earthquake"),
                description=place or None,
                latitude=lat,
                longitude=lon,
                country=country,
                region=region,
                occurred_at=occurred_at,
                event_metadata={
                    "magnitude": round(float(mag), 2),
                    "depth_km":  round(float(coords[2]), 1) if len(coords) > 2 else None,
                    "tsunami":   props.get("tsunami", 0),
                    "felt":      props.get("felt"),
                    "alert":     props.get("alert"),
                    "url":       props.get("url"),
                    # searchable location fields stored in metadata for full-text lookup
                    "city":      city,
                    "place":     place,
                },
                source="usgs",
            ))
    except Exception as exc:
        logger.warning(f"[USGS] {exc}")
    logger.info(f"[USGS] {len(events)} earthquakes")
    return events


# ══════════════════════════════════════════════════════════════════════════════
# 2. NASA FIRMS — Active Wildfires
# ══════════════════════════════════════════════════════════════════════════════

_FIRMS_MIN_FRP = 10.0
_CLUSTER_GRID  = 1.0   # 1° ≈ 111 km clustering grid


def _frp_to_severity(frp: float) -> SeverityLevel:
    if frp < 50:  return SeverityLevel.LOW
    if frp < 200: return SeverityLevel.MEDIUM
    if frp < 500: return SeverityLevel.HIGH
    return SeverityLevel.CRITICAL


async def fetch_nasa_fires(client: httpx.AsyncClient) -> list[DisasterEventCreate]:
    key = settings.NASA_FIRMS_API_KEY
    if not key:
        logger.warning("[FIRMS] key not set — skipping")
        return []

    events: list[DisasterEventCreate] = []
    try:
        # URL template lives in settings — no hard-coded endpoint here
        url  = settings.FIRMS_API_URL.format(key=key)
        resp = await client.get(url, timeout=30)
        resp.raise_for_status()
        text = resp.text
        if not text.strip() or text.startswith("<?xml"):
            logger.warning("[FIRMS] empty/error response")
            return []

        clusters: dict[str, dict] = {}
        for row in csv.DictReader(io.StringIO(text)):
            try:
                lat  = float(row.get("latitude",  0))
                lon  = float(row.get("longitude", 0))
                frp  = float(row.get("frp", 0) or 0)
                conf = row.get("confidence", "nominal")
                if frp < _FIRMS_MIN_FRP or conf == "low":
                    continue
                gk = (
                    f"{round(lat / _CLUSTER_GRID) * _CLUSTER_GRID:.1f}_"
                    f"{round(lon / _CLUSTER_GRID) * _CLUSTER_GRID:.1f}"
                )
                if gk not in clusters:
                    clusters[gk] = {
                        "lat_sum": 0.0, "lon_sum": 0.0, "frp_sum": 0.0, "count": 0,
                        "acq_date": row.get("acq_date", ""),
                        "acq_time": row.get("acq_time", "0000"),
                        "confidence": conf, "daynight": row.get("daynight", "D"),
                    }
                c = clusters[gk]
                c["lat_sum"] += lat; c["lon_sum"] += lon
                c["frp_sum"] += frp; c["count"]   += 1
            except (ValueError, KeyError):
                continue

        now = datetime.now(tz=timezone.utc)
        for gk, c in clusters.items():
            n         = c["count"]
            avg_lat   = round(c["lat_sum"] / n, 4)
            avg_lon   = round(c["lon_sum"] / n, 4)
            total_frp = round(c["frp_sum"], 1)
            try:
                occurred_at = datetime.strptime(
                    f"{c['acq_date']} {c['acq_time'].zfill(4)}", "%Y-%m-%d %H%M"
                ).replace(tzinfo=timezone.utc)
            except ValueError:
                occurred_at = now

            country, region, city = _get_location_info(avg_lat, avg_lon)
            # Build human-readable area label from most-specific to least
            area_desc = (
                city or region or country
                or f"{abs(avg_lat):.1f}°{'N' if avg_lat >= 0 else 'S'}"
            )

            events.append(DisasterEventCreate(
                external_id=f"firms-{gk}-{c['acq_date']}",
                type=DisasterType.FIRE,
                severity=_frp_to_severity(total_frp),
                title=f"Active Wildfire — {area_desc}",
                description=f"{n} fire detection{'s' if n > 1 else ''} by NASA VIIRS satellite",
                latitude=avg_lat, longitude=avg_lon,
                country=country, region=region,
                occurred_at=occurred_at,
                event_metadata={
                    "detection_count":  n,
                    "total_frp_mw":     total_frp,
                    "avg_frp_mw":       round(total_frp / n, 1),
                    "confidence":       c["confidence"],
                    "daynight":         c["daynight"],
                    "source_satellite": "VIIRS SNPP NRT",
                    "city":             city,
                },
                source="nasa_firms",
            ))
    except Exception as exc:
        logger.warning(f"[FIRMS] {exc}")
    logger.info(f"[FIRMS] {len(events)} fire clusters")
    return events


# ══════════════════════════════════════════════════════════════════════════════
# 3. OpenWeatherMap — Floods & Storms
# ══════════════════════════════════════════════════════════════════════════════

_HURRICANE_CODES = {902, 901, 900, 781}

# City list — only (name, lat, lon); country is resolved by reverse_geocoder
_OWM_LOCATIONS: list[tuple[str, float, float]] = [
    ("Manila",           14.599,  120.984),
    ("Ho Chi Minh City", 10.823,  106.630),
    ("Bangkok",          13.756,  100.502),
    ("Dhaka",            23.811,   90.412),
    ("Kolkata",          22.573,   88.364),
    ("Mumbai",           19.076,   72.877),
    ("Chennai",          13.082,   80.270),
    ("Guangzhou",        23.129,  113.264),
    ("Shanghai",         31.230,  121.474),
    ("Tokyo",            35.689,  139.692),
    ("Jakarta",          -6.200,  106.816),
    ("Taipei",           25.047,  121.514),
    ("Miami",            25.775,  -80.208),
    ("Houston",          29.760,  -95.370),
    ("New Orleans",      29.951,  -90.071),
    ("Nassau",           25.058,  -77.343),
    ("Havana",           23.136,  -82.359),
    ("San Juan",         18.466,  -66.105),
    ("Bridgetown",       13.098,  -59.614),
    ("São Paulo",       -23.550,  -46.633),
    ("Manaus",           -3.119,  -60.022),
    ("Lisbon",           38.717,   -9.139),
    ("Athens",           37.983,   23.728),
    ("Istanbul",         41.015,   28.979),
    ("Lagos",             6.524,    3.379),
    ("Maputo",          -25.966,   32.588),
    ("Antananarivo",    -18.914,   47.536),
    ("Suva",            -18.141,  178.441),
    ("Honiara",          -9.433,  160.033),
    ("Port Vila",       -17.734,  168.322),
    ("Port Louis",      -20.161,   57.499),
    ("Male",              4.175,   73.509),
    ("Colombo",           6.927,   79.861),
    ("Yangon",           16.871,   96.195),
    ("Cebu",             10.317,  123.891),
]


def _wind_to_severity(w: float) -> Optional[SeverityLevel]:
    if w >= 69.4: return SeverityLevel.CRITICAL
    if w >= 49.4: return SeverityLevel.HIGH
    if w >= 32.9: return SeverityLevel.MEDIUM
    if w >= 17.2: return SeverityLevel.LOW
    return None


def _rain_to_severity(r: float) -> Optional[SeverityLevel]:
    if r >= 50: return SeverityLevel.CRITICAL
    if r >= 20: return SeverityLevel.HIGH
    if r >= 10: return SeverityLevel.MEDIUM
    if r >=  5: return SeverityLevel.LOW
    return None


async def fetch_openweather_disasters(client: httpx.AsyncClient) -> list[DisasterEventCreate]:
    api_key = settings.OPENWEATHER_API_KEY
    if not api_key:
        logger.warning("[OWM] key not set — skipping")
        return []

    async def _one(name: str, lat: float, lon: float):
        try:
            r = await client.get(
                settings.OWM_API_URL,
                params={"lat": lat, "lon": lon, "appid": api_key, "units": "metric"},
                timeout=10,
            )
            r.raise_for_status()
            return name, lat, lon, r.json()
        except Exception:
            return name, lat, lon, None

    results = await asyncio.gather(
        *[_one(n, la, lo) for n, la, lo in _OWM_LOCATIONS],
        return_exceptions=True,
    )
    events: list[DisasterEventCreate] = []
    for res in results:
        if isinstance(res, Exception) or res is None:
            continue
        name, lat, lon, data = res # type: ignore
        if not data:
            continue
        try:
            # ── resolve location from coordinates ─────────────────────────────
            country, region, city = _get_location_info(lat, lon)
            display_name = city or name          # prefer geocoded city name
            # ─────────────────────────────────────────────────────────────────

            wid   = data.get("weather", [{}])[0].get("id", 800)
            wdesc = data.get("weather", [{}])[0].get("description", "")
            ws    = float(data.get("wind", {}).get("speed", 0))
            wg    = float(data.get("wind", {}).get("gust",  0) or 0)
            r1    = float(data.get("rain", {}).get("1h",    0) or 0)
            r3    = float(data.get("rain", {}).get("3h",    0) or 0)
            hum   = float(data.get("main", {}).get("humidity", 0))
            dt    = datetime.fromtimestamp(data.get("dt", 0), tz=timezone.utc)
            er    = max(r1, r3 / 3.0)
            ew    = max(ws, wg)
            dh    = dt.strftime("%Y-%m-%d-%H")

            def _mk(dtype: DisasterType, sev: SeverityLevel, title: str, desc: str):
                return DisasterEventCreate(
                    external_id=f"owm-{dtype.value}-{name.replace(' ','_').replace(',','')}-{dh}",
                    type=dtype, severity=sev,
                    title=title, description=desc,
                    latitude=lat, longitude=lon,
                    country=country, region=region,
                    occurred_at=dt,
                    event_metadata={
                        "weather_code":  wid,
                        "wind_speed_ms": round(ws, 1),
                        "wind_gust_ms":  round(wg, 1),
                        "rain_1h_mm":    round(r1, 1),
                        "rain_3h_mm":    round(r3, 1),
                        "humidity_pct":  round(hum),
                        "city":          city,
                        "source":        "OpenWeatherMap",
                    },
                    source="openweathermap",
                )

            if wid in _HURRICANE_CODES:
                events.append(_mk(DisasterType.HURRICANE, SeverityLevel.CRITICAL,
                    f"Hurricane / Tropical Storm — {display_name}",
                    f"{wdesc.title()}. Wind: {ws:.1f} m/s"))
            else:
                wsev = _wind_to_severity(ew)
                if wsev:
                    events.append(_mk(DisasterType.HURRICANE, wsev,
                        f"Severe Storm — {display_name}",
                        f"Strong winds: {ew:.1f} m/s. {wdesc.title()}"))
            if wid not in _HURRICANE_CODES:
                rsev = _rain_to_severity(er)
                if rsev:
                    events.append(_mk(DisasterType.FLOOD, rsev,
                        f"Heavy Rainfall / Flood Risk — {display_name}",
                        f"Rain: {r1:.1f} mm/h (1h), {r3:.1f} mm (3h). "
                        f"Humidity: {hum:.0f}%. {wdesc.title()}"))
        except Exception as exc:
            logger.debug(f"[OWM] {name}: {exc}")

    logger.info(f"[OWM] {len(events)} severe weather events")
    return events


# ══════════════════════════════════════════════════════════════════════════════
# 4. GDACS UN — RSS feed
# ══════════════════════════════════════════════════════════════════════════════

_GDACS_NS = {
    "georss": "http://www.georss.org/georss",
    "gdacs":  "http://www.gdacs.org",
    "dc":     "http://purl.org/dc/elements/1.1/",
}

_GDACS_TYPE_MAP = {
    "FL": DisasterType.FLOOD,
    "TC": DisasterType.HURRICANE,
    "TS": DisasterType.TSUNAMI,
    "EQ": DisasterType.EARTHQUAKE,
    "WF": DisasterType.FIRE,
}


def _gdacs_alert_to_severity(alert: str) -> SeverityLevel:
    a = (alert or "").lower()
    if a == "red":    return SeverityLevel.CRITICAL
    if a == "orange": return SeverityLevel.HIGH
    if a == "green":  return SeverityLevel.LOW
    return SeverityLevel.MEDIUM


async def fetch_gdacs_disasters(client: httpx.AsyncClient) -> list[DisasterEventCreate]:
    """
    GDACS UN RSS feed — all active globally-significant disasters.
    No API key required.  URL comes from settings.GDACS_RSS_URL.
    """
    events: list[DisasterEventCreate] = []
    now = datetime.now(tz=timezone.utc)
    try:
        resp = await client.get(
            settings.GDACS_RSS_URL,
            headers={"Accept": "application/rss+xml, application/xml, text/xml"},
            timeout=20,
        )
        resp.raise_for_status()

        root    = ET.fromstring(resp.text)
        channel = root.find("channel")
        if channel is None:
            logger.warning("[GDACS] No <channel> in RSS feed")
            return []

        items = channel.findall("item")
        logger.info(f"[GDACS] RSS has {len(items)} items")

        for item in items:
            try:
                title    = (item.findtext("title") or "").strip()
                desc     = (item.findtext("description") or "").strip()
                link     = (item.findtext("link") or "").strip()
                pub_date = (item.findtext("pubDate") or "").strip()

                event_type    = (item.findtext("gdacs:eventtype",  namespaces=_GDACS_NS) or "").strip().upper()
                event_id      = (item.findtext("gdacs:eventid",    namespaces=_GDACS_NS) or "").strip()
                alert_level   = (item.findtext("gdacs:alertlevel", namespaces=_GDACS_NS) or "green").strip()
                gdacs_country = (item.findtext("gdacs:country",    namespaces=_GDACS_NS) or "").strip()
                severity_v    = (item.findtext("gdacs:severity",   namespaces=_GDACS_NS) or "").strip()

                georss_pt = (item.findtext("georss:point", namespaces=_GDACS_NS) or "").strip()
                if not georss_pt:
                    continue
                parts = georss_pt.split()
                if len(parts) < 2:
                    continue
                lat = float(parts[0])
                lon = float(parts[1])
                if not event_id or not (-90 <= lat <= 90):
                    continue

                dtype = _GDACS_TYPE_MAP.get(event_type)
                if dtype is None:
                    continue   # VO (volcano), DR (drought) — not in schema

                occurred_at = _parse_dt_safe(pub_date, now)
                clean_desc  = re.sub(r"<[^>]+>", " ", desc).strip()[:500]

                # Offline geocoding supersedes the GDACS text country field
                country, region, city = _get_location_info(lat, lon)
                if not country:
                    country = gdacs_country or None   # fallback to GDACS value

                events.append(DisasterEventCreate(
                    external_id=f"gdacs-{event_type.lower()}-{event_id}",
                    type=dtype,
                    severity=_gdacs_alert_to_severity(alert_level),
                    title=title or f"GDACS {event_type} event",
                    description=clean_desc or None,
                    latitude=lat, longitude=lon,
                    country=country, region=region,
                    occurred_at=occurred_at,
                    event_metadata={
                        "alert_level":    alert_level,
                        "gdacs_event_id": event_id,
                        "gdacs_type":     event_type,
                        "severity_value": severity_v,
                        "source":         "GDACS UN",
                        "link":           link,
                        "city":           city,
                    },
                    source="gdacs",
                ))
            except Exception as exc:
                logger.debug(f"[GDACS] item error: {exc}")

    except httpx.HTTPError as exc:
        logger.warning(f"[GDACS] HTTP error: {exc}")
    except ET.ParseError as exc:
        logger.warning(f"[GDACS] XML parse error: {exc}")
    except Exception as exc:
        logger.error(f"[GDACS] Unexpected: {exc}", exc_info=True)

    logger.info(f"[GDACS] {len(events)} events from RSS")
    return events


# ══════════════════════════════════════════════════════════════════════════════
# 5. NOAA NHC — Atlantic & Eastern Pacific Hurricanes
# ══════════════════════════════════════════════════════════════════════════════

def _nhc_wind_to_severity(wind_kt: float) -> SeverityLevel:
    mph = wind_kt * 1.15078
    if mph >= 130: return SeverityLevel.CRITICAL
    if mph >= 111: return SeverityLevel.HIGH
    if mph >= 74:  return SeverityLevel.MEDIUM
    return SeverityLevel.LOW


async def fetch_noaa_nhc_hurricanes(client: httpx.AsyncClient) -> list[DisasterEventCreate]:
    """
    NOAA NHC CurrentStorms.json — active Atlantic/Pacific tropical cyclones.
    URL from settings.NHC_API_URL.
    Returns empty list when no active storms exist (normal off-season behaviour).
    """
    events: list[DisasterEventCreate] = []
    try:
        resp = await client.get(settings.NHC_API_URL, timeout=15)
        resp.raise_for_status()
        data   = resp.json()
        active = data.get("activeStorms") or data.get("storms") or []
        if not active:
            logger.info("[NHC] No active storms")
            return []

        for storm in active:
            try:
                storm_id = str(storm.get("id") or storm.get("stormId") or "")
                name     = str(storm.get("name") or "Unknown")
                basin    = str(storm.get("basin") or "")
                wind_kt  = float(storm.get("maxWindMph") or storm.get("intensity") or 0) / 1.15078
                lat      = float(storm.get("lat") or storm.get("latitude")  or 0)
                lon      = float(storm.get("lon") or storm.get("longitude") or 0)
                movement = str(storm.get("movement") or "")
                category = str(storm.get("category") or "")
                date_str = str(storm.get("date") or storm.get("advisoryDate") or "")
                occurred_at = _parse_dt_safe(date_str, datetime.now(tz=timezone.utc))
                if not storm_id or lat == 0.0:
                    continue

                ocean_region = (
                    "Atlantic Ocean"  if "al" in basin.lower() else
                    "Eastern Pacific" if "ep" in basin.lower() else
                    "Western Pacific" if "wp" in basin.lower() else
                    basin or "Open Ocean"
                )
                country, region, city = _get_location_info(lat, lon)

                events.append(DisasterEventCreate(
                    external_id=f"nhc-{storm_id}",
                    type=DisasterType.HURRICANE,
                    severity=_nhc_wind_to_severity(wind_kt),
                    title=f"Hurricane {name} — {ocean_region}",
                    description=(
                        f"Active {category} tropical cyclone. "
                        f"Max wind: {wind_kt * 1.852:.0f} km/h. {movement}"
                    ).strip(),
                    latitude=lat, longitude=lon,
                    country=country,
                    region=region or ocean_region,
                    occurred_at=occurred_at,
                    event_metadata={
                        "storm_id":     storm_id,
                        "basin":        basin,
                        "category":     category,
                        "max_wind_kmh": round(wind_kt * 1.852, 1),
                        "movement":     movement,
                        "source":       "NOAA NHC",
                        "city":         city,
                    },
                    source="noaa_nhc",
                ))
            except Exception as exc:
                logger.debug(f"[NHC] {exc}")
    except Exception as exc:
        logger.warning(f"[NHC] {exc}")
    logger.info(f"[NHC] {len(events)} active hurricanes")
    return events


# ══════════════════════════════════════════════════════════════════════════════
# 6. NOAA PTWC — Tsunami Warnings
# ══════════════════════════════════════════════════════════════════════════════

_PTWC_NS = {"atom": "http://www.w3.org/2005/Atom"}


def _ptwc_severity(msg: str) -> SeverityLevel:
    m = msg.lower()
    if "warning"  in m: return SeverityLevel.CRITICAL
    if "watch"    in m: return SeverityLevel.HIGH
    if "advisory" in m: return SeverityLevel.MEDIUM
    return SeverityLevel.LOW


def _extract_ptwc_coords(text: str) -> Optional[tuple[float, float]]:
    m = re.search(r"(\d+\.?\d*)\s*([NS])[,\s]+(\d+\.?\d*)\s*([EW])", text, re.I)
    if not m:
        return None
    lat = float(m.group(1)) * (-1 if m.group(2).upper() == "S" else 1)
    lon = float(m.group(3)) * (-1 if m.group(4).upper() == "W" else 1)
    return (lat, lon) if -90 <= lat <= 90 and -180 <= lon <= 180 else None


async def fetch_noaa_ptwc_tsunamis(client: httpx.AsyncClient) -> list[DisasterEventCreate]:
    """
    NOAA PTWC Atom feeds — active tsunami warnings/watches/advisories.
    Feed URLs come from settings.PTWC_FEED_URLS (list).
    """
    events: list[DisasterEventCreate] = []
    now = datetime.now(tz=timezone.utc)

    for feed_url in settings.PTWC_FEED_URLS:
        try:
            resp = await client.get(feed_url, timeout=15)
            resp.raise_for_status()
            root    = ET.fromstring(resp.text)
            entries = root.findall("atom:entry", _PTWC_NS)
            for entry in entries:
                try:
                    title   = (entry.findtext("atom:title",     default="", namespaces=_PTWC_NS) or "").strip()
                    summary = (entry.findtext("atom:summary",   default="", namespaces=_PTWC_NS) or "").strip()
                    link    = (entry.findtext("atom:id",        default="", namespaces=_PTWC_NS) or "").strip()
                    pub_str = (entry.findtext("atom:published", default="", namespaces=_PTWC_NS) or "").strip()

                    if not title or "no threat" in title.lower() or "cancellation" in title.lower():
                        continue
                    try:
                        occurred_at = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
                    except ValueError:
                        occurred_at = now

                    lat, lon  = _extract_ptwc_coords(summary) or (0.0, -160.0)
                    country, region, city = _get_location_info(lat, lon)
                    event_id  = link.split("/")[-1] or title[:40].replace(" ", "_")

                    events.append(DisasterEventCreate(
                        external_id=f"ptwc-{event_id}",
                        type=DisasterType.TSUNAMI,
                        severity=_ptwc_severity(title),
                        title=title,
                        description=summary[:500] if summary else None,
                        latitude=lat, longitude=lon,
                        country=country,
                        region=region or "Pacific Ocean",
                        occurred_at=occurred_at,
                        event_metadata={
                            "source_url": link,
                            "source":     "NOAA PTWC",
                            "city":       city,
                        },
                        source="noaa_ptwc",
                    ))
                except Exception as exc:
                    logger.debug(f"[PTWC] entry: {exc}")
        except Exception as exc:
            logger.debug(f"[PTWC] {feed_url}: {exc}")

    logger.info(f"[PTWC] {len(events)} tsunami warnings")
    return events


# ══════════════════════════════════════════════════════════════════════════════
# Ingestion orchestrator
# ══════════════════════════════════════════════════════════════════════════════

async def ingest_and_broadcast(events: list[DisasterEventCreate]) -> None:
    if not events:
        return
    async with AsyncSessionLocal() as db:
        service = DisasterService(db)
        saved = 0
        for ev in events:
            try:
                record  = await service.create_event(ev)
                lat     = float(record.latitude)   # type: ignore[arg-type]
                lon     = float(record.longitude)  # type: ignore[arg-type]
                from schemas.disaster import DisasterEventRead
                payload = DisasterEventRead.model_validate(record).model_dump(mode="json")
                await manager.broadcast_event(payload)
                await manager.send_proximity_alerts(payload, lat, lon)
                saved += 1
            except Exception as exc:
                logger.error(f"[ingest] '{ev.title}': {exc}")
        logger.info(f"[ingest] saved {saved}/{len(events)}")


async def ingestion_loop() -> None:
    """
    Fetches all 6 sources concurrently every INGESTION_INTERVAL_SECONDS.
    All results are deduplicated by external_id before DB insert.
    """
    interval = settings.INGESTION_INTERVAL_SECONDS
    logger.info(f"[ingestion] Started — interval={interval}s, sources=6")

    async with httpx.AsyncClient(
        headers={"User-Agent": "DisasterMonitor/1.0"},
        follow_redirects=True,
    ) as client:
        while True:
            try:
                eq, fire, wx, gdacs, nhc, ptwc = await asyncio.gather(
                    fetch_usgs_earthquakes(client),
                    fetch_nasa_fires(client),
                    fetch_openweather_disasters(client),
                    fetch_gdacs_disasters(client),
                    fetch_noaa_nhc_hurricanes(client),
                    fetch_noaa_ptwc_tsunamis(client),
                    return_exceptions=True,
                )
                all_events: list[DisasterEventCreate] = []
                summary: dict = {}
                for result, label in [
                    (eq,    "USGS"),
                    (fire,  "FIRMS"),
                    (wx,    "OWM"),
                    (gdacs, "GDACS"),
                    (nhc,   "NHC"),
                    (ptwc,  "PTWC"),
                ]:
                    if isinstance(result, Exception):
                        logger.error(f"[ingestion] {label}: {result}")
                        summary[label] = "err"
                    elif isinstance(result, list):
                        all_events.extend(result)
                        summary[label] = len(result)

                await ingest_and_broadcast(all_events)
                logger.info(f"[ingestion] Cycle complete — {summary}")

            except asyncio.CancelledError:
                logger.info("[ingestion] Cancelled")
                break
            except Exception as exc:
                logger.error(f"[ingestion] Unexpected: {exc}", exc_info=True)

            await asyncio.sleep(interval)