"""Auth API — /api/v1/auth/*"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from schemas.auth import (
    RegisterRequest, RegisterResponse,
    VerifyOTPRequest, ResendOTPRequest, OTPResponse,
    LoginRequest, TokenResponse,
    AuthUserRead, MeResponse,
)
from services.auth_service import (
    register_user, verify_otp, resend_otp, login_user, get_auth_user,
)
from utils.jwt_utils import decode_access_token

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
bearer = HTTPBearer(auto_error=False)


# ── JWT dependency ────────────────────────────────────────────────────────────

async def current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_db),
):
    if not creds or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(creds.credentials)
    return await get_auth_user(db, payload["sub"])


# ── Public routes ─────────────────────────────────────────────────────────────

@router.post("/register", response_model=RegisterResponse, status_code=201)
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    return await register_user(db, data)


@router.post("/verify-otp", response_model=TokenResponse)
async def verify(data: VerifyOTPRequest, db: AsyncSession = Depends(get_db)):
    return await verify_otp(db, data.email, data.otp)


@router.post("/resend-otp", response_model=OTPResponse)
async def resend(data: ResendOTPRequest, db: AsyncSession = Depends(get_db)):
    return await resend_otp(db, data.email)


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    return await login_user(db, data)


# ── Protected routes ──────────────────────────────────────────────────────────

@router.get("/me", response_model=MeResponse)
async def me(user=Depends(current_user)):
    return {"user": AuthUserRead.model_validate(user)}


@router.post("/logout")
async def logout():
    # JWT is stateless — client deletes the token. This endpoint is for symmetry.
    return {"message": "Logged out successfully."}