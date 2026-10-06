"""FastAPI application factory and entrypoint."""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.v1.router import api_router
from app.core.config import settings
from app.middleware import RateLimitMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app")


def create_app() -> FastAPI:
    # Refuse to boot with insecure/incomplete production configuration.
    settings.validate_runtime()

    # Optional error tracking.
    if settings.SENTRY_DSN:
        try:  # pragma: no cover - only runs when configured
            import sentry_sdk

            sentry_sdk.init(dsn=settings.SENTRY_DSN, environment=settings.ENVIRONMENT)
            logger.info("Sentry initialised")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Sentry init failed: %s", exc)

    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=__version__,
        description=(
            "REST API for the Household Furniture storefront (V1). "
            "Interactive docs at /docs, OpenAPI schema at /openapi.json."
        ),
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RateLimitMiddleware)

    # Serve locally-stored product images when using the "local" storage
    # backend. In production (STORAGE_BACKEND=s3) images are served by S3/CDN.
    if settings.STORAGE_BACKEND.lower() == "local":
        media_root = Path(settings.MEDIA_ROOT)
        media_root.mkdir(parents=True, exist_ok=True)
        app.mount(
            settings.MEDIA_URL_PREFIX,
            StaticFiles(directory=str(media_root)),
            name="media",
        )

    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    @app.get("/", tags=["health"])
    def root() -> dict:
        return {
            "name": settings.PROJECT_NAME,
            "version": __version__,
            "docs": "/docs",
            "api": settings.API_V1_PREFIX,
        }

    return app


app = create_app()
