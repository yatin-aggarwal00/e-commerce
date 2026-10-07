"""Thin, failure-tolerant Redis wrapper used for response caching.

Caching is a performance optimisation, never a correctness requirement: if
Redis is unavailable the helpers degrade to no-ops so the API keeps serving.
"""
from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager, suppress
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


@contextmanager
def try_lock(name: str, ttl_seconds: int) -> Iterator[bool]:
    """Best-effort distributed lock used to single-flight background jobs.

    Yields ``True`` when the caller holds the lock and should do the work, and
    ``False`` when another instance already holds it (the caller should skip).

    If Redis is unavailable we yield ``True`` and run without the lock: the
    expiry job is made correct by per-order DB transactions, so the lock is only
    an optimisation that stops multiple instances doing redundant work.
    """
    if _client is None:
        yield True
        return
    lock = _client.lock(f"lock:{name}", timeout=ttl_seconds, blocking=False)
    acquired = False
    try:
        try:
            acquired = lock.acquire(blocking=False)
        except Exception:
            # Redis went away mid-flight: fall back to running (DB guards us).
            yield True
            return
        yield acquired
    finally:
        if acquired:
            # If release fails (e.g. the lock already expired via its TTL),
            # there is nothing to do — the TTL guarantees it is freed anyway.
            with suppress(Exception):
                lock.release()
