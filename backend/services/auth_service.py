"""
Auth business logic — register, OTP, login, get_current_user.

passlib[bcrypt]==1.7.4 is broken on Python 3.14 because:
  1. passlib reads bcrypt.__about__.__version__ — removed in bcrypt 4.x
  2. passlib's wrap-bug detection passes a 73-byte test hash — bcrypt 4.x
     rejects passwords > 72 bytes with a hard ValueError instead of silently
     truncating.

Fix: drop passlib entirely. Use bcrypt directly — it's the underlying library
passlib was wrapping. The API is 3 lines: bcrypt.hashpw(), bcrypt.checkpw(),
bcrypt.gensalt(). No wrapper needed.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import bcrypt
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.auth import AuthUser, OTPRecord
from schemas.auth import RegisterRequest, LoginRequest, AuthUserRead
from utils.jwt_utils import create_access_token
from utils.otp_utils import generate_otp
from utils.email_utils import send_otp_email

logger  = logging.getLogger(__name__)
OTP_TTL = 10  # minutes


# ── Password helpers (bcrypt direct — no passlib) ─────────────────────────────

def _hash(plain: str) -> str:
    """Hash a plain-text password with bcrypt. Returns the hashed string."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify(plain: str, hashed: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ── DB lookup ─────────────────────────────────────────────────────────────────

async def _by_email(db: AsyncSession, email: str) -> Optional[AuthUser]:
    r = await db.execute(select(AuthUser).where(AuthUser.email == email))
    return r.scalar_one_or_none()


# ── OTP issuing ───────────────────────────────────────────────────────────────

async def _issue_otp(db: AsyncSession, email: str, name: str) -> bool:
    """
    Invalidate all unused OTPs for this email, create a new one, and send it.
    Returns True if the email was delivered successfully.
    """
    # Mark all existing unused OTPs as used
    result = await db.execute(
        select(OTPRecord).where(
            OTPRecord.email   == email,
            OTPRecord.is_used == False,  # noqa: E712 — SQLAlchemy requires ==
        )
    )
    for old in result.scalars().all():
        old.is_used = True

    otp_code = generate_otp()
    db.add(OTPRecord(
        email      = email,
        otp        = otp_code,
        expires_at = datetime.now(tz=timezone.utc) + timedelta(minutes=OTP_TTL),
        is_used    = False,
    ))
    await db.commit()

    # SMTP is synchronous — run in a thread pool so it doesn't block the event loop
    loop = asyncio.get_event_loop()
    sent: bool = await loop.run_in_executor(None, send_otp_email, email, name, otp_code)
    return sent


# ── Register ──────────────────────────────────────────────────────────────────

async def register_user(db: AsyncSession, data: RegisterRequest) -> dict:
    existing = await _by_email(db, data.email)

    if existing is not None and existing.is_verified:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    if existing is not None and not existing.is_verified:
        # Unverified account already exists — update credentials and resend OTP
        existing.name            = data.name
        existing.hashed_password = _hash(data.password)
        await db.commit()
        await _issue_otp(db, existing.email, existing.name)
        return {
            "message": "Account exists but is unverified. A new code has been sent to your email.",
            "email":   data.email,
        }

    # Brand new user
    user = AuthUser(
        name            = data.name,
        email           = data.email,
        hashed_password = _hash(data.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    sent = await _issue_otp(db, user.email, user.name)
    if not sent:
        logger.warning(f"[auth] OTP email failed for {user.email} — check SMTP config in .env")

    return {
        "message": "Registration successful! Check your email for the 6-digit verification code.",
        "email":   data.email,
    }


# ── Verify OTP ────────────────────────────────────────────────────────────────

async def verify_otp(db: AsyncSession, email: str, otp: str) -> dict:
    user = await _by_email(db, email)
    if user is None:
        raise HTTPException(status_code=404, detail="No account found for this email.")
    if user.is_verified:
        raise HTTPException(status_code=400, detail="Account is already verified.")

    r = await db.execute(
        select(OTPRecord)
        .where(
            OTPRecord.email   == email,
            OTPRecord.otp     == otp,
            OTPRecord.is_used == False,  # noqa: E712
        )
        .order_by(OTPRecord.created_at.desc())
    )
    record = r.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=400, detail="Invalid OTP. Please check and try again.")

    # Make timezone-aware (defensive — Neon returns UTC but tzinfo can be None)
    exp: datetime = record.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if datetime.now(tz=timezone.utc) > exp:
        raise HTTPException(status_code=400, detail="OTP has expired. Please request a new one.")

    record.is_used   = True
    user.is_verified = True
    await db.commit()

    token = create_access_token(subject=user.email, extra={"user_id": str(user.id)})
    return {
        "access_token": token,
        "token_type":   "bearer",
        "user":         AuthUserRead.model_validate(user),
    }


# ── Resend OTP ────────────────────────────────────────────────────────────────

async def resend_otp(db: AsyncSession, email: str) -> dict:
    user = await _by_email(db, email)
    if user is None:
        raise HTTPException(status_code=404, detail="No account found for this email.")
    if user.is_verified:
        raise HTTPException(status_code=400, detail="Account is already verified.")

    sent = await _issue_otp(db, user.email, user.name)
    if not sent:
        raise HTTPException(
            status_code=500,
            detail="Failed to send OTP email. Check SMTP configuration in .env.",
        )
    return {"message": "A new verification code has been sent to your email."}


# ── Login ─────────────────────────────────────────────────────────────────────

async def login_user(db: AsyncSession, data: LoginRequest) -> dict:
    user = await _by_email(db, data.email)

    if user is None or not _verify(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please check your inbox for the verification code.",
        )

    token = create_access_token(subject=user.email, extra={"user_id": str(user.id)})
    return {
        "access_token": token,
        "token_type":   "bearer",
        "user":         AuthUserRead.model_validate(user),
    }


# ── Get current user (used by JWT dependency in routers/auth.py) ──────────────

async def get_auth_user(db: AsyncSession, email: str) -> AuthUser:
    user = await _by_email(db, email)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return user