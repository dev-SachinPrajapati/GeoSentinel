from datetime import datetime, timezone, timedelta
from jose import jwt, JWTError
from fastapi import HTTPException, status
from core.config import get_settings

settings  = get_settings()
ALGORITHM = "HS256"
EXPIRE_H  = 24


def create_access_token(subject: str, extra: dict = {}) -> str:
    payload = {
        "sub": subject,
        "exp": datetime.now(tz=timezone.utc) + timedelta(hours=EXPIRE_H),
        "iat": datetime.now(tz=timezone.utc),
        **extra,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        if not payload.get("sub"):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token invalid or expired: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )