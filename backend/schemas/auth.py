from __future__ import annotations
from datetime import datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, model_validator


class RegisterRequest(BaseModel):
    name:             str      = Field(..., min_length=3, max_length=255)
    email:            EmailStr
    password:         str      = Field(..., min_length=6)
    confirm_password: str

    @model_validator(mode="after")
    def passwords_match(self) -> "RegisterRequest":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class RegisterResponse(BaseModel):
    message: str
    email:   str


class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp:   str = Field(..., min_length=6, max_length=6)


class ResendOTPRequest(BaseModel):
    email: EmailStr


class OTPResponse(BaseModel):
    message: str


class LoginRequest(BaseModel):
    email:    EmailStr
    password: str = Field(..., min_length=1)


class AuthUserRead(BaseModel):
    id:          UUID
    name:        str
    email:       str
    is_verified: bool
    created_at:  datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    user:         AuthUserRead


class MeResponse(BaseModel):
    user: AuthUserRead