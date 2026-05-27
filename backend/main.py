r"""Disaster Monitor API — entry point (with auth)."""
import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Any, Callable

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from core.config import get_settings
from db.database import init_db

# Import auth models BEFORE init_db so SQLAlchemy registers their tables
import models.auth  # noqa: F401  ← ensures auth_users / auth_otps are created

from routers.disasters import router as disasters_router
from routers.websocket  import router as websocket_router
from routers.auth       import router as auth_router

from schemas.disaster import HealthResponse
from services.ingestion_service import ingestion_loop
from websocket.manager import manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger   = logging.getLogger(__name__)
settings = get_settings()
limiter  = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Disaster Monitor API")
    await init_db()           # creates disaster_events + auth_users + auth_otps
    logger.info("Database initialized")
    task = asyncio.create_task(ingestion_loop())
    logger.info("Ingestion loop started")
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def timing(request: Request, call_next: Callable[..., Any]) -> Any:
    t = time.perf_counter()
    r = await call_next(request)
    r.headers["X-Process-Time-Ms"] = f"{(time.perf_counter()-t)*1000:.1f}"
    return r


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth_router)       # /api/v1/auth/*
app.include_router(disasters_router)  # /api/v1/disasters/*
app.include_router(websocket_router)  # /ws/disasters


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health():
    return HealthResponse(
        status="healthy",
        version=settings.APP_VERSION,
        database="connected",
        active_connections=manager.active_count,
    )


@app.get("/", tags=["health"])
async def root():
    return {"name": settings.APP_NAME, "version": settings.APP_VERSION}