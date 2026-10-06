"""Reusable FastAPI dependencies: DB session, current user, admin guard."""
from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import ACCESS_TOKEN, decode_token
from app.models.user import User

# auto_error=False so endpoints can accept both guests and logged-in users.
bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]
Credentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]


def _user_from_token(db: Session, token: str) -> User | None:
    try:
        payload = decode_token(token)
    except jwt.PyJWTError:
        return None
    if payload.get("type") != ACCESS_TOKEN:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    return db.get(User, user_id)


def get_optional_user(db: DbSession, creds: Credentials) -> User | None:
    """Return the authenticated user if a valid token is present, else None."""
    if creds is None:
        return None
    return _user_from_token(db, creds.credentials)


def get_current_user(db: DbSession, creds: Credentials) -> User:
    """Require a valid, active user. Raises 401 otherwise."""
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = _user_from_token(db, creds.credentials)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_current_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    """Require an admin user. Raises 403 for non-admins."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required"
        )
    return user


def cart_token_header(
    x_cart_token: Annotated[str | None, Header(alias="X-Cart-Token")] = None,
) -> str | None:
    """Guest cart identifier passed by the storefront via header."""
    return x_cart_token


OptionalUser = Annotated[User | None, Depends(get_optional_user)]
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentAdmin = Annotated[User, Depends(get_current_admin)]
CartToken = Annotated[str | None, Depends(cart_token_header)]
