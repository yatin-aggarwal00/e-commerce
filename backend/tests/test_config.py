"""Production configuration guardrails (Settings.validate_runtime)."""
from __future__ import annotations

import pytest

from app.core.config import Settings

STRONG_SECRET = "s" * 48


def _prod(**overrides) -> Settings:
    base = dict(
        ENVIRONMENT="production",
        DEBUG=False,
        SECRET_KEY=STRONG_SECRET,
        PAYMENT_PROVIDER="fake",
        STORAGE_BACKEND="local",
        BACKEND_CORS_ORIGINS="https://shop.example.com",
    )
    base.update(overrides)
    return Settings(**base)


def test_development_never_raises():
    # Defaults (development) must boot with no configuration at all.
    Settings(ENVIRONMENT="development", SECRET_KEY="change-me").validate_runtime()


def test_valid_production_config_passes():
    _prod().validate_runtime()


def test_default_secret_key_rejected_in_production():
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        _prod(SECRET_KEY="change-me").validate_runtime()


def test_debug_rejected_in_production():
    with pytest.raises(RuntimeError, match="DEBUG"):
        _prod(DEBUG=True).validate_runtime()


def test_stripe_requires_keys_in_production():
    with pytest.raises(RuntimeError, match="STRIPE_SECRET_KEY"):
        _prod(PAYMENT_PROVIDER="stripe", STRIPE_SECRET_KEY="").validate_runtime()


def test_s3_requires_bucket_in_production():
    with pytest.raises(RuntimeError, match="S3_BUCKET"):
        _prod(STORAGE_BACKEND="s3", S3_BUCKET="").validate_runtime()


def test_cors_required_in_production():
    with pytest.raises(RuntimeError, match="BACKEND_CORS_ORIGINS"):
        _prod(BACKEND_CORS_ORIGINS="").validate_runtime()
