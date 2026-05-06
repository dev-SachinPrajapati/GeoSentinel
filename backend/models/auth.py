"""
Auth DB models using SQLAlchemy 2.0 Mapped[] annotations.

Why this matters:
  Old style:  name = Column(String(255))
              → Pylance infers Column[str], so assignments like
                existing.name = "foo" produce:
                "str is not assignable to Column[str]"

  New style:  name: Mapped[str] = mapped_column(String(255))
              → Pylance sees plain Python types (str, bool, datetime, UUID).
                All comparisons, assignments and function calls type-check correctly.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Boolean, DateTime, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.database import Base


class AuthUser(Base):
    __tablename__ = "auth_users"

    id:              Mapped[uuid.UUID]          = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name:            Mapped[str]                = mapped_column(String(255), nullable=False)
    email:           Mapped[str]                = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str]                = mapped_column(Text, nullable=False)
    is_verified:     Mapped[bool]               = mapped_column(Boolean, default=False, nullable=False)
    created_at:      Mapped[datetime]           = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at:      Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)


class OTPRecord(Base):
    __tablename__ = "auth_otps"

    id:         Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email:      Mapped[str]       = mapped_column(String(255), nullable=False, index=True)
    otp:        Mapped[str]       = mapped_column(String(6), nullable=False)
    expires_at: Mapped[datetime]  = mapped_column(DateTime(timezone=True), nullable=False)
    is_used:    Mapped[bool]      = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime]  = mapped_column(DateTime(timezone=True), server_default=func.now())