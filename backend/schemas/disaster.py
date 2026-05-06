from __future__ import annotations
from datetime import datetime
from typing import Any, Optional
from uuid import UUID
from pydantic import BaseModel, Field, field_validator, model_validator

# Import enums from models
from models.disaster import DisasterType, SeverityLevel


# ─── Coordinates ──────────────────────────────────────────────────────────────

class Coordinates(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


# ─── Disaster Event ───────────────────────────────────────────────────────────

class DisasterEventCreate(BaseModel):
    external_id: Optional[str] = None
    type: DisasterType
    severity: SeverityLevel
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = Field(None, max_length=2000)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    country: Optional[str] = Field(None, max_length=100)
    region: Optional[str] = Field(None, max_length=200)
    occurred_at: datetime
    expires_at: Optional[datetime] = None
    event_metadata: dict[str, Any] = Field(default_factory=dict)
    source: str = Field(default="manual", max_length=100)

    @field_validator("title")
    @classmethod
    def sanitize_title(cls, v: str) -> str:
        return v.strip()


class DisasterEventRead(BaseModel):
    id: UUID
    external_id: Optional[str]
    type: DisasterType
    severity: SeverityLevel
    title: str
    description: Optional[str]
    latitude: float
    longitude: float
    country: Optional[str]
    region: Optional[str]
    occurred_at: datetime
    expires_at: Optional[datetime]
    event_metadata: dict[str, Any]
    source: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DisasterEventUpdate(BaseModel):
    severity: Optional[SeverityLevel] = None
    description: Optional[str] = Field(None, max_length=2000)
    expires_at: Optional[datetime] = None
    event_metadata: Optional[dict[str, Any]] = None


# ─── Filters ──────────────────────────────────────────────────────────────────

class DisasterFilter(BaseModel):
    types: Optional[list[DisasterType]] = None
    severities: Optional[list[SeverityLevel]] = None
    country: Optional[str] = None
    center_lat: Optional[float] = Field(None, ge=-90, le=90)
    center_lon: Optional[float] = Field(None, ge=-180, le=180)
    radius_km: Optional[float] = Field(None, gt=0, le=20000)
    from_dt: Optional[datetime] = None
    to_dt: Optional[datetime] = None
    limit: int = Field(100, ge=1, le=500)
    offset: int = Field(0, ge=0)

    @model_validator(mode="after")
    def validate_radius_filter(self) -> "DisasterFilter":
        has_center = self.center_lat is not None and self.center_lon is not None
        if self.radius_km is not None and not has_center:
            raise ValueError("center_lat and center_lon required when radius_km is set")
        return self


# ─── WebSocket ────────────────────────────────────────────────────────────────

class WSMessage(BaseModel):
    type: str
    payload: Any
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class WSSubscribePayload(BaseModel):
    user_lat: Optional[float] = Field(None, ge=-90, le=90)
    user_lon: Optional[float] = Field(None, ge=-180, le=180)
    alert_radius_km: float = Field(100.0, gt=0, le=5000)
    types: Optional[list[DisasterType]] = None


# ─── User ─────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    email: str = Field(..., pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    name: str = Field(..., min_length=1, max_length=255)
    notification_radius_km: float = Field(100.0, gt=0, le=5000)
    home_lat: Optional[float] = Field(None, ge=-90, le=90)
    home_lon: Optional[float] = Field(None, ge=-180, le=180)


class UserRead(BaseModel):
    id: UUID
    email: str
    name: str
    notification_radius_km: float
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── API Responses ────────────────────────────────────────────────────────────

class PaginatedResponse(BaseModel):
    data: list[DisasterEventRead]
    total: int
    limit: int
    offset: int


class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
    active_connections: int