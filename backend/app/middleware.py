"""Lightweight in-process rate limiting middleware.

A fixed-window counter keyed by client IP + path-prefix. This is adequate for
single-instance V1; for multi-instance production move the counter into Redis
(same algorithm, shared store) so the limit is global.
"""
from __future__ import annotations

import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limit_per_minute: int | None = None) -> None:
        super().__init__(app)
        self.limit = limit_per_minute or settings.RATE_LIMIT_PER_MINUTE
        self._hits: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        # Only throttle the API surface; skip docs/openapi/health.
        path = request.url.path
        if not path.startswith(settings.API_V1_PREFIX) or path.endswith("/health"):
            return await call_next(request)

        client = request.client.host if request.client else "anonymous"
        key = f"{client}:{path.rsplit('/', 1)[0]}"
        now = time.monotonic()
        window_start = now - 60
        recent = [t for t in self._hits[key] if t > window_start]
        if len(recent) >= self.limit:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again shortly."},
            )
        recent.append(now)
        self._hits[key] = recent
        return await call_next(request)
