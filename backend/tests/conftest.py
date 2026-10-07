"""Pytest fixtures.

The suite runs against an in-memory SQLite database (StaticPool so every
connection shares it) with the fake payment provider — no Postgres, Redis,
Stripe or network required.
"""
from __future__ import annotations

import os

# Must be set before any app module imports settings / creates the engine.
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("PAYMENT_PROVIDER", "fake")
os.environ.setdefault("STRIPE_SECRET_KEY", "")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-tests-only")
# Don't spin up the in-process APScheduler during tests; the expiry job is
# exercised directly and via the on-demand admin endpoint instead.
os.environ.setdefault("SCHEDULER_ENABLED", "false")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import User  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_db():
    """Recreate all tables around every test for isolation."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def user_token(client) -> str:
    r = client.post(
        "/api/v1/auth/register",
        json={"email": "shopper@example.com", "password": "password123", "full_name": "Shopper"},
    )
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


@pytest.fixture
def admin_token(client, db) -> str:
    admin = User(
        email="admin@example.com",
        hashed_password=hash_password("adminpass123"),
        full_name="Admin",
        is_admin=True,
    )
    db.add(admin)
    db.commit()
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "adminpass123"},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
