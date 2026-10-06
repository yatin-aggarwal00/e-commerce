"""Thin, failure-tolerant Redis wrapper used for response caching.

Caching is a performance optimisation, never a correctness requirement: if
Redis is unavailable the helpers degrade to no-ops so the API keeps serving.
"""
from __future__ import annotations

import json
from typing import Any

import redis

from app.core.config import settings

try:
    _client: redis.Redis | None = redis.Redis.from_url(
        settings.REDIS_URL, decode_responses=True, socket_connect_timeout=1
    )
except Exception:  # pragma: no cover - defensive
    _client = None


def cache_get(key: str) -> Any | None:
    if _client is None:
        return None
    try:
        raw = _client.get(key)
        return json.loads(raw) if raw else None
    except Exception:
        return None


def cache_set(key: str, value: Any, ttl: int | None = None) -> None:
    if _client is None:
        return
    try:
        _client.set(key, json.dumps(value, default=str), ex=ttl or settings.CACHE_TTL_SECONDS)
    except Exception:
        return


def cache_delete_prefix(prefix: str) -> None:
    """Invalidate every cached key under ``prefix`` (best effort)."""
    if _client is None:
        return
    try:
        for key in _client.scan_iter(match=f"{prefix}*"):
            _client.delete(key)
    except Exception:
        return
