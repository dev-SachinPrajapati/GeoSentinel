import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Float, DateTime, JSON, Index, Text,
    Enum as SAEnum, func
)
from sqlalchemy.dialects.postgresql import UUID
from db.database import Base
import enum


class DisasterType(str, enum.Enum):
    EARTHQUAKE = "earthquake"
    FLOOD = "flood"
    FIRE = "fire"
    HURRICANE = "hurricane"
    TSUNAMI = "tsunami"


class SeverityLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    notification_radius_km = Column(Float, default=100.0)
    # Store lat/lon as floats — PostGIS GEOGRAPHY managed via raw SQL in services
    home_lat = Column(Float, nullable=True)
    home_lon = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class DisasterEvent(Base):
    __tablename__ = "disaster_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id = Column(String(255), unique=True, nullable=True, index=True)
    type = Column(SAEnum(DisasterType), nullable=False, index=True)
    severity = Column(SAEnum(SeverityLevel), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    description = Column(String(2000), nullable=True)

    # Store coordinates as floats for ORM reads
    # PostGIS GEOGRAPHY column is created via raw SQL in schema.sql
    # We do NOT define it here to avoid geoalchemy2 system dependency on Windows
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    country = Column(String(100), nullable=True, index=True)
    region = Column(String(200), nullable=True)

    occurred_at = Column(DateTime(timezone=True), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    # Renamed from 'metadata' — reserved by SQLAlchemy DeclarativeBase
    event_metadata = Column("metadata", JSON, default={})

    source = Column(String(100), nullable=False, default="manual")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        Index("idx_disaster_type_severity", "type", "severity"),
        Index("idx_disaster_occurred_at", "occurred_at"),
        Index("idx_disaster_country", "country"),
    )