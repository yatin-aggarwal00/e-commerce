"""Application configuration loaded from environment variables.

All settings are overridable via env vars (see ``.env.example``). In production
every secret must come from the environment / a secrets vault — never commit
real values.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- General ---------------------------------------------------------
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    PROJECT_NAME: str = "Furniture E-commerce API"
    API_V1_PREFIX: str = "/api/v1"

    # --- Database --------------------------------------------------------
    # Default points at the docker-compose Postgres service. Tests override
    # this with an in-memory SQLite URL via the ``DATABASE_URL`` env var.
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/furniture"

    # --- Redis (caching + optional cart acceleration) --------------------
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL_SECONDS: int = 60

    # --- Auth / JWT ------------------------------------------------------
    SECRET_KEY: str = "change-me-in-production-please-use-a-long-random-string"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    PASSWORD_RESET_EXPIRE_MINUTES: int = 30

    # --- CORS ------------------------------------------------------------
    # Comma-separated list of allowed origins, e.g. the Next.js frontend.
    BACKEND_CORS_ORIGINS: str = "http://localhost:3000"

    # --- Rate limiting ---------------------------------------------------
    RATE_LIMIT_PER_MINUTE: int = 120

    # --- Payments (Stripe sandbox by default) ----------------------------
    PAYMENT_PROVIDER: str = "stripe"  # "stripe" | "fake"
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    CURRENCY: str = "usd"

    # --- Email -----------------------------------------------------------
    EMAIL_BACKEND: str = "console"  # "console" | "smtp"
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = "no-reply@furniture.example"

    # --- Frontend / storefront ------------------------------------------
    FRONTEND_URL: str = "http://localhost:3000"

    # --- Observability ---------------------------------------------------
    SENTRY_DSN: str = ""

    @field_validator("BACKEND_CORS_ORIGINS")
    @classmethod
    def _strip_origins(cls, v: str) -> str:
        return v.strip()

    @property
    def cors_origins(self) -> list[str]:
        if not self.BACKEND_CORS_ORIGINS:
            return []
        return [o.strip() for o in self.BACKEND_CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
