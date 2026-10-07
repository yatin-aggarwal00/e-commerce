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

    # --- Orders / inventory integrity ------------------------------------
    # Pending orders left unpaid longer than this are cancelled by a scheduled
    # job, which releases the stock they reserved at checkout. See
    # ``app/services/orders.py`` and ``app/scheduler.py``.
    ORDER_PENDING_TTL_MINUTES: int = 60
    # How often the expiry job runs (in-process APScheduler interval).
    ORDER_EXPIRY_INTERVAL_MINUTES: int = 5
    # Set false to run without the in-process scheduler (e.g. tests, or when a
    # dedicated worker owns the schedule). The on-demand trigger still works.
    SCHEDULER_ENABLED: bool = True

    # --- Payments (Stripe sandbox by default) ----------------------------
    PAYMENT_PROVIDER: str = "stripe"  # "stripe" | "fake"
    STRIPE_SECRET_KEY: str = ""
    # Publishable key is safe to expose to the browser; served via
    # GET /payments/config so the storefront can mount the Payment Element.
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    CURRENCY: str = "usd"

    # --- Object storage / CDN (product images) ---------------------------
    # "local" writes to MEDIA_ROOT and serves it at /media (dev default);
    # "s3" uploads to an S3-compatible bucket and serves via S3_PUBLIC_BASE_URL
    # (point this at your CDN in production).
    STORAGE_BACKEND: str = "local"  # "local" | "s3"
    MEDIA_ROOT: str = "media"
    MEDIA_URL_PREFIX: str = "/media"
    # Absolute base used to build returned image URLs for the local backend.
    PUBLIC_MEDIA_BASE_URL: str = "http://localhost:8000"
    S3_BUCKET: str = ""
    S3_REGION: str = ""
    S3_ENDPOINT_URL: str = ""  # set for MinIO / non-AWS S3-compatible stores
    S3_ACCESS_KEY_ID: str = ""
    S3_SECRET_ACCESS_KEY: str = ""
    # CDN / public base URL for objects, e.g. https://cdn.example.com
    S3_PUBLIC_BASE_URL: str = ""

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

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() in {"production", "prod"}

    def validate_runtime(self) -> None:
        """Fail fast on insecure or incomplete production configuration.

        Called from the app factory. In non-production environments this is a
        no-op so local dev and tests work out of the box.
        """
        if not self.is_production:
            return

        errors: list[str] = []
        insecure_secrets = {
            "change-me",
            "change-me-in-production-please-use-a-long-random-string",
            "dev-only-change-me-to-a-long-random-string",
            "ci-test-secret-key-not-for-production",
        }
        if self.SECRET_KEY in insecure_secrets or len(self.SECRET_KEY) < 32:
            errors.append(
                "SECRET_KEY must be a unique random string of at least 32 chars "
                "in production (generate with "
                "`python -c \"import secrets;print(secrets.token_urlsafe(48))\"`)."
            )
        if self.DEBUG:
            errors.append("DEBUG must be false in production.")
        if self.PAYMENT_PROVIDER.lower() == "stripe" and not self.STRIPE_SECRET_KEY:
            errors.append(
                "STRIPE_SECRET_KEY is required when PAYMENT_PROVIDER=stripe."
            )
        if self.PAYMENT_PROVIDER.lower() == "stripe" and not self.STRIPE_WEBHOOK_SECRET:
            errors.append(
                "STRIPE_WEBHOOK_SECRET is required to verify payment webhooks."
            )
        if self.STORAGE_BACKEND.lower() == "s3" and not self.S3_BUCKET:
            errors.append("S3_BUCKET is required when STORAGE_BACKEND=s3.")
        if not self.cors_origins:
            errors.append("BACKEND_CORS_ORIGINS must list the storefront origin(s).")

        if errors:
            raise RuntimeError(
                "Refusing to start with insecure production configuration:\n  - "
                + "\n  - ".join(errors)
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
