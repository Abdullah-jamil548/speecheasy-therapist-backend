from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings
from app.repositories.supabase_client import get_db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(*, doctor_id: str, email: str) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": doctor_id,
        "email": email,
        "role": "doctor",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from exc


def new_token_value() -> str:
    return secrets.token_urlsafe(32)


def new_otp_code(length: int = 6) -> str:
    """Numeric one-time code for email verification / password reset."""
    upper = 10**length
    return f"{secrets.randbelow(upper):0{length}d}"


def otp_token(*, purpose: str, doctor_id: str, code: str) -> str:
    """Stable unique token key for a short OTP (avoids colliding 6-digit codes)."""
    prefix = "vcode" if purpose == "verify_email" else "rcode"
    return f"{prefix}_{doctor_id}_{code}"


def new_doctor_id() -> str:
    return str(uuid4())


def get_current_doctor_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> str:
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = decode_token(credentials.credentials)
    doctor_id = payload.get("sub")
    if not doctor_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return str(doctor_id)


def get_current_doctor(doctor_id: str = Depends(get_current_doctor_id)) -> dict[str, Any]:
    db = get_db()
    rows = db.select(
        "therapists",
        filters={"id": f"eq.{doctor_id}"},
        limit=1,
    )
    if not rows:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Doctor not found")
    return rows[0]


def public_therapist(row: dict[str, Any]) -> dict[str, Any]:
    """Strip secrets before returning to clients."""
    data = dict(row)
    password_hash = data.pop("password_hash", None)
    data["has_password"] = bool(password_hash)
    return data
