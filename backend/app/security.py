from __future__ import annotations

import datetime
import uuid
from typing import Any, Literal

import bcrypt
import jwt

from app.config import get_settings

ALGORITHM = "HS256"
BCRYPT_ROUNDS = 12

Role = Literal["admin", "researcher", "participant"]


def hash_password(password: str) -> str:
    """Hash a password with bcrypt at cost 12 (NFR-5)."""
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def create_access_token(*, sub: str, role: Role, extra: dict[str, Any] | None = None) -> str:
    settings = get_settings()
    payload: dict[str, Any] = {
        "sub": sub,
        "role": role,
        "type": "access",
        "iat": _now(),
        "exp": _now() + datetime.timedelta(minutes=settings.access_token_expire_minutes),
        "jti": str(uuid.uuid4()),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def create_refresh_token(*, sub: str, role: Role, extra: dict[str, Any] | None = None) -> str:
    settings = get_settings()
    payload: dict[str, Any] = {
        "sub": sub,
        "role": role,
        "type": "refresh",
        "iat": _now(),
        "exp": _now() + datetime.timedelta(days=settings.refresh_token_expire_days),
        "jti": str(uuid.uuid4()),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    decoded: dict[str, Any] = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    return decoded


REFRESH_COOKIE_NAME = "refresh_token"


def refresh_cookie_kwargs(settings: Any, max_age_seconds: int | None) -> dict[str, Any]:
    """Common kwargs for setting/clearing the refresh cookie (NFR-5)."""
    return {
        "key": REFRESH_COOKIE_NAME,
        "httponly": True,
        "samesite": "lax",
        "secure": settings.cookie_secure,
        "path": "/api/v1/auth",
        **({"max_age": max_age_seconds} if max_age_seconds is not None else {}),
    }
