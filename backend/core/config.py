from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── App ──────────────────────────────────────────────────────────────────
    APP_NAME:    str = "Disaster Monitor API"
    APP_VERSION: str = "1.0.0"
    DEBUG:       bool = False
    ENVIRONMENT: str = "production"

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL:          str
    DATABASE_POOL_SIZE:    int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # ── Security ─────────────────────────────────────────────────────────────
    SECRET_KEY:             str
    ALLOWED_ORIGINS:        list[str] = ["http://localhost:3000"]
    RATE_LIMIT_PER_MINUTE:  int = 60

    # ── External API keys ────────────────────────────────────────────────────
    OPENWEATHER_API_KEY: str = ""
    NASA_FIRMS_API_KEY:  str = ""

    # ── External API URLs ────────────────────────────────────────────────────
    # 1. USGS — earthquakes (past 1 h, all magnitudes)
    USGS_API_URL: str = (
        "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson"
    )

    # 2. NASA FIRMS VIIRS — active wildfires (past 24 h, world)
    FIRMS_API_URL: str = (
        "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/VIIRS_SNPP_NRT/world/1"
    )

    # 3. OpenWeatherMap — current weather per city
    OWM_API_URL: str = "https://api.openweathermap.org/data/2.5/weather"

    # 4. GDACS UN — global disaster RSS feed (all active events, no key)
    GDACS_RSS_URL: str = "https://www.gdacs.org/xml/rss.xml"

    # 5. NOAA NHC — active Atlantic/Pacific tropical storms (no key)
    NHC_API_URL: str = "https://www.nhc.noaa.gov/CurrentStorms.json"

    # 6. NOAA PTWC — tsunami warning Atom feeds (no key)
    PTWC_FEED_URLS: list[str] = [
        "https://tsunami.gov/events/xml/PHEBAtom.xml",
    ]

    # ── WebSocket ─────────────────────────────────────────────────────────────
    WS_HEARTBEAT_INTERVAL: int = 30

    # ── Ingestion ─────────────────────────────────────────────────────────────
    INGESTION_INTERVAL_SECONDS: int = 60

    # ── SMTP — OTP verification e-mails ───────────────────────────────────────
    SMTP_HOST:      str = "smtp.gmail.com"
    SMTP_PORT:      int = 587
    SMTP_USER:      str = ""   # your Gmail address
    SMTP_PASSWORD:  str = ""   # Gmail App Password (16 chars)
    SMTP_FROM_NAME: str = "GeoSentinel Disaster Monitor"

    class Config:
        env_file       = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()  # type: ignore