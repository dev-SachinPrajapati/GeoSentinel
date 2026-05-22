"""
Backend tests — pytest + pytest-asyncio
Run: pytest tests/ -v
"""
import pytest
import pytest_asyncio
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from main import app
from services.ingestion_service import (
    _magnitude_to_severity,
    _extract_country,
    _frp_to_severity,
    _wind_to_severity,
    _rain_to_severity,
)
from models.disaster import DisasterType, SeverityLevel
from schemas.disaster import DisasterEventCreate, DisasterFilter


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


# ── Unit Tests: USGS helpers ──────────────────────────────────────────────────

class TestMagnitudeToSeverity:
    def test_low(self):
        assert _magnitude_to_severity(1.0) == SeverityLevel.LOW
        assert _magnitude_to_severity(2.9) == SeverityLevel.LOW

    def test_medium(self):
        assert _magnitude_to_severity(3.0) == SeverityLevel.MEDIUM
        assert _magnitude_to_severity(4.9) == SeverityLevel.MEDIUM

    def test_high(self):
        assert _magnitude_to_severity(5.0) == SeverityLevel.HIGH
        assert _magnitude_to_severity(6.9) == SeverityLevel.HIGH

    def test_critical(self):
        assert _magnitude_to_severity(7.0) == SeverityLevel.CRITICAL
        assert _magnitude_to_severity(9.5) == SeverityLevel.CRITICAL


class TestExtractCountry:
    def test_extracts_country(self):
        assert _extract_country("50km NE of Tokyo, Japan") == "Japan"

    def test_no_comma(self):
        assert _extract_country("California") == "California"

    def test_empty(self):
        assert _extract_country("") is None

    def test_none_input(self):
        assert _extract_country(None) is None  # type: ignore


# ── Unit Tests: NASA FIRMS helpers ────────────────────────────────────────────

class TestFrpToSeverity:
    def test_low(self):
        assert _frp_to_severity(10.0) == SeverityLevel.LOW
        assert _frp_to_severity(49.9) == SeverityLevel.LOW

    def test_medium(self):
        assert _frp_to_severity(50.0) == SeverityLevel.MEDIUM
        assert _frp_to_severity(199.9) == SeverityLevel.MEDIUM

    def test_high(self):
        assert _frp_to_severity(200.0) == SeverityLevel.HIGH
        assert _frp_to_severity(499.9) == SeverityLevel.HIGH

    def test_critical(self):
        assert _frp_to_severity(500.0) == SeverityLevel.CRITICAL
        assert _frp_to_severity(9999.0) == SeverityLevel.CRITICAL


# ── Unit Tests: OpenWeatherMap helpers ───────────────────────────────────────

class TestWindToSeverity:
    def test_below_threshold_returns_none(self):
        assert _wind_to_severity(10.0) is None
        assert _wind_to_severity(17.1) is None

    def test_low(self):
        assert _wind_to_severity(17.2) == SeverityLevel.LOW
        assert _wind_to_severity(32.8) == SeverityLevel.LOW

    def test_medium(self):
        assert _wind_to_severity(32.9) == SeverityLevel.MEDIUM
        assert _wind_to_severity(49.3) == SeverityLevel.MEDIUM

    def test_high(self):
        assert _wind_to_severity(49.4) == SeverityLevel.HIGH
        assert _wind_to_severity(69.3) == SeverityLevel.HIGH

    def test_critical(self):
        assert _wind_to_severity(69.4) == SeverityLevel.CRITICAL
        assert _wind_to_severity(85.0) == SeverityLevel.CRITICAL


class TestRainToSeverity:
    def test_below_threshold_returns_none(self):
        assert _rain_to_severity(0.0) is None
        assert _rain_to_severity(4.9) is None

    def test_low(self):
        assert _rain_to_severity(5.0) == SeverityLevel.LOW
        assert _rain_to_severity(9.9) == SeverityLevel.LOW

    def test_medium(self):
        assert _rain_to_severity(10.0) == SeverityLevel.MEDIUM
        assert _rain_to_severity(19.9) == SeverityLevel.MEDIUM

    def test_high(self):
        assert _rain_to_severity(20.0) == SeverityLevel.HIGH
        assert _rain_to_severity(49.9) == SeverityLevel.HIGH

    def test_critical(self):
        assert _rain_to_severity(50.0) == SeverityLevel.CRITICAL
        assert _rain_to_severity(200.0) == SeverityLevel.CRITICAL


# ── Unit Tests: Schemas ───────────────────────────────────────────────────────

class TestDisasterFilter:
    def test_radius_requires_center(self):
        with pytest.raises(ValueError, match="center_lat and center_lon required"):
            DisasterFilter(radius_km=100)

    def test_valid_radius_filter(self):
        f = DisasterFilter(center_lat=35.0, center_lon=139.0, radius_km=100)
        assert f.radius_km == 100

    def test_defaults(self):
        f = DisasterFilter()
        assert f.limit == 100
        assert f.offset == 0
        assert f.types is None


class TestDisasterEventCreate:
    def test_title_stripped(self):
        event = DisasterEventCreate(
            type="earthquake",
            severity="low",
            title="  Test Event  ",
            latitude=35.0,
            longitude=139.0,
            occurred_at=datetime.now(tz=timezone.utc),
        )
        assert event.title == "Test Event"

    def test_invalid_latitude(self):
        with pytest.raises(ValueError):
            DisasterEventCreate(
                type="earthquake",
                severity="low",
                title="Test",
                latitude=91.0,
                longitude=0.0,
                occurred_at=datetime.now(tz=timezone.utc),
            )

    def test_usgs_source_fields(self):
        """Verify a USGS-style event validates correctly."""
        event = DisasterEventCreate(
            external_id="us2024abcd",
            type=DisasterType.EARTHQUAKE,
            severity=SeverityLevel.HIGH,
            title="M5.8 Earthquake - 50km NE of Tokyo, Japan",
            description="50km NE of Tokyo, Japan",
            latitude=35.689,
            longitude=139.692,
            country="Japan",
            region="50km NE of Tokyo, Japan",
            occurred_at=datetime.now(tz=timezone.utc),
            event_metadata={"magnitude": 5.8, "depth_km": 35, "tsunami": 0},
            source="usgs",
        )
        assert event.source == "usgs"
        assert event.type == DisasterType.EARTHQUAKE

    def test_firms_source_fields(self):
        """Verify a NASA FIRMS-style event validates correctly."""
        event = DisasterEventCreate(
            external_id="firms-36.0_-119.0-2024-03-22",
            type=DisasterType.FIRE,
            severity=SeverityLevel.HIGH,
            title="Active Wildfire — California, USA",
            description="15 fire detections detected by NASA VIIRS satellite",
            latitude=36.0,
            longitude=-119.0,
            country="USA",
            region="California, USA",
            occurred_at=datetime.now(tz=timezone.utc),
            event_metadata={
                "detection_count": 15,
                "total_frp_mw": 320.5,
                "confidence": "nominal",
                "source_satellite": "VIIRS SNPP NRT",
            },
            source="nasa_firms",
        )
        assert event.source == "nasa_firms"
        assert event.type == DisasterType.FIRE

    def test_owm_source_fields(self):
        """Verify an OpenWeatherMap-style event validates correctly."""
        event = DisasterEventCreate(
            external_id="owm-flood-Miami_USA-2024-03-22-14",
            type=DisasterType.FLOOD,
            severity=SeverityLevel.MEDIUM,
            title="Heavy Rainfall / Flood Risk — Miami, USA",
            description="Rainfall 22.0 mm/h (1h). Heavy rain.",
            latitude=25.775,
            longitude=-80.208,
            country="USA",
            region="Miami, USA",
            occurred_at=datetime.now(tz=timezone.utc),
            event_metadata={
                "rain_1h_mm": 22.0,
                "wind_speed_ms": 8.5,
                "humidity_pct": 95,
                "source": "OpenWeatherMap",
            },
            source="openweathermap",
        )
        assert event.source == "openweathermap"
        assert event.type == DisasterType.FLOOD


# ── Integration Tests: API ────────────────────────────────────────────────────

class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "version" in data


class TestDisastersEndpoint:
    @pytest.mark.asyncio
    async def test_list_returns_paginated_shape(self, client: AsyncClient):
        resp = await client.get("/api/v1/disasters/")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        assert isinstance(data["data"], list)

    @pytest.mark.asyncio
    async def test_invalid_lat(self, client: AsyncClient):
        resp = await client.get("/api/v1/disasters/?center_lat=999")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_filter_by_type(self, client: AsyncClient):
        resp = await client.get("/api/v1/disasters/?types=earthquake")
        assert resp.status_code == 200
        data = resp.json()
        for event in data["data"]:
            assert event["type"] == "earthquake"

    @pytest.mark.asyncio
    async def test_filter_by_real_sources(self, client: AsyncClient):
        """Verify source filter works — no mock source should appear."""
        resp = await client.get("/api/v1/disasters/?limit=500")
        assert resp.status_code == 200
        data = resp.json()
        for event in data["data"]:
            assert event["source"] != "mock", (
                f"Found mock event in DB: {event['id']} — "
                "run cleanup_mock_data.sql to remove stale mock records"
            )

    @pytest.mark.asyncio
    async def test_radius_requires_center(self, client: AsyncClient):
        resp = await client.get("/api/v1/disasters/?radius_km=100")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_heatmap_endpoint(self, client: AsyncClient):
        resp = await client.get("/api/v1/disasters/heatmap")
        assert resp.status_code == 200
        assert "data" in resp.json()

    @pytest.mark.asyncio
    async def test_stats_endpoint(self, client: AsyncClient):
        resp = await client.get("/api/v1/disasters/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "by_type_severity" in data

    @pytest.mark.asyncio
    async def test_not_found(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/disasters/00000000-0000-0000-0000-000000000000"
        )
        assert resp.status_code == 404


# ── WebSocket Tests ───────────────────────────────────────────────────────────

from fastapi.testclient import TestClient

class TestWebSocket:
    def test_connect_receives_confirmation(self):
        with TestClient(app) as client:
            with client.websocket_connect("/ws/disasters") as ws:
                msg = ws.receive_json()
                assert msg["type"] == "connected"
                assert "client_id" in msg["payload"]

    def test_subscribe_message(self):
        with TestClient(app) as client:
            with client.websocket_connect("/ws/disasters") as ws:
                ws.receive_json()  # connected msg
                ws.send_json({
                    "type": "subscribe",
                    "payload": {"user_lat": 35.0, "user_lon": 139.0, "alert_radius_km": 200},
                })
                msg = ws.receive_json()
                assert msg["type"] == "subscribed"
                assert msg["payload"]["alert_radius_km"] == 200

    def test_ping_pong(self):
        with TestClient(app) as client:
            with client.websocket_connect("/ws/disasters") as ws:
                ws.receive_json()  # connected
                ws.send_json({"type": "ping", "payload": {}})
                msg = ws.receive_json()
                assert msg["type"] == "pong"