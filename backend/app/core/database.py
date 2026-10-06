"""SQLAlchemy engine, session factory and declarative base.

The engine is configured from ``settings.DATABASE_URL``. SQLite (used by the
test suite) needs ``check_same_thread=False`` and benefits from a static pool
so the in-memory DB survives across connections within a test.
"""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings


class Base(DeclarativeBase):
    """Declarative base shared by every ORM model."""


def _make_engine():
    url = settings.DATABASE_URL
    if url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
        # ":memory:" needs a StaticPool so every session hits the same DB.
        if ":memory:" in url:
            return create_engine(
                url,
                connect_args=connect_args,
                poolclass=StaticPool,
                future=True,
            )
        return create_engine(url, connect_args=connect_args, future=True)
    return create_engine(url, pool_pre_ping=True, future=True)


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
