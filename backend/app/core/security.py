"""Password hashing and JWT token helpers."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.core.config import settings

# JWT "type" claim discriminators (not secrets).
ACCESS_TOKEN = "access"  # nosec B105
REFRESH_TOKEN = "refresh"  # nosec B105
RESET_TOKEN = "reset"  # nosec B105

# bcrypt hashes at most the first 72 bytes of the input, and modern bcrypt
# raises on longer input instead of truncating, so we truncate explicitly.
# Using the bcrypt library directly avoids passlib, which is unmaintained and
# breaks against bcrypt 4+/5+.
_BCRYPT_MAX_BYTES = 72


def hash_password(password: str) -> str:
    pw = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        pw = plain.encode("utf-8")[:_BCRYPT_MAX_BYTES]
        return bcrypt.checkpw(pw, hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def _create_token(subject: str, token_type: str, expires: timedelta, **claims: Any) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": token_type,
        "iat": now,
        "exp": now + expires,
        "jti": uuid.uuid4().hex,
        **claims,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(subject: str, **claims: Any) -> str:
    return _create_token(
        subject,
        ACCESS_TOKEN,
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        **claims,
    )


def create_refresh_token(subject: str) -> str:
    return _create_token(
        subject, REFRESH_TOKEN, timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )


def create_reset_token(subject: str) -> str:
    return _create_token(
        subject, RESET_TOKEN, timedelta(minutes=settings.PASSWORD_RESET_EXPIRE_MINUTES)
    )


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT. Raises ``jwt.PyJWTError`` on failure."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
