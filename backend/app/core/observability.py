"""Small, dependency-tolerant observability helpers.

Sentry is optional: it is only wired when ``SENTRY_DSN`` is set (see
``app/main.py``). These helpers no-op when the SDK is absent or uninitialised so
background jobs and request handlers can report errors unconditionally without
caring whether Sentry is configured.
"""
from __future__ import annotations


def capture_exception(exc: BaseException) -> None:
    """Report an exception to Sentry if available; otherwise do nothing."""
    try:  # pragma: no cover - exercised only when Sentry is installed
        import sentry_sdk

        sentry_sdk.capture_exception(exc)
    except Exception:
        # Never let error reporting raise inside a background job.
        return
