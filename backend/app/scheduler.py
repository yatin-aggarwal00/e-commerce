"""In-process background scheduler for recurring maintenance jobs.

V1 runs a single service, so the lightweight choice is an in-process
APScheduler ``BackgroundScheduler`` rather than a dedicated worker (Celery/RQ
beat). To stay correct across multiple instances, each tick grabs a best-effort
Redis lock (``redis_client.try_lock``) so only one instance does the work;
correctness does not *depend* on the lock, because the job itself expires each
order in its own re-checked transaction (see ``app/services/orders.py``). This
aligns with the "move the rate-limit counter to Redis" follow-up — same shared
store, same single-service footprint.

The scheduler is started from the FastAPI lifespan and gated by
``SCHEDULER_ENABLED`` so tests and worker-owned deployments can opt out. The job
can always be triggered on demand via ``POST /admin/orders/expire-pending``.
"""
from __future__ import annotations

import logging

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.observability import capture_exception
from app.core.redis_client import try_lock
from app.services.orders import expire_pending_orders

logger = logging.getLogger("app.scheduler")

_EXPIRY_LOCK = "expire_pending_orders"

# Module-level handle so lifespan start/stop act on the same instance.
_scheduler = None


def run_expire_pending_orders_job() -> None:
    """Scheduler entry point: single-flight the expiry job across instances."""
    lock_ttl = max(settings.ORDER_EXPIRY_INTERVAL_MINUTES * 60, 60)
    try:
        with try_lock(_EXPIRY_LOCK, lock_ttl) as acquired:
            if not acquired:
                logger.debug("expire_pending_orders: another instance holds the lock; skipping")
                return
            with SessionLocal() as db:
                expire_pending_orders(db)
    except Exception as exc:  # noqa: BLE001 - a job error must not kill the scheduler
        logger.exception("expire_pending_orders job raised")
        capture_exception(exc)


def start_scheduler():
    """Start the background scheduler unless disabled. Returns it (or ``None``)."""
    global _scheduler
    if not settings.SCHEDULER_ENABLED:
        logger.info("Scheduler disabled (SCHEDULER_ENABLED=false)")
        return None
    if _scheduler is not None:
        return _scheduler

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except Exception as exc:  # pragma: no cover - only when APScheduler is absent
        logger.warning("APScheduler not installed; expiry job will not run: %s", exc)
        return None

    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        run_expire_pending_orders_job,
        trigger="interval",
        minutes=settings.ORDER_EXPIRY_INTERVAL_MINUTES,
        id=_EXPIRY_LOCK,
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.start()
    _scheduler = scheduler
    logger.info(
        "Scheduler started: expire_pending_orders every %d min (TTL %d min)",
        settings.ORDER_EXPIRY_INTERVAL_MINUTES,
        settings.ORDER_PENDING_TTL_MINUTES,
    )
    return scheduler


def shutdown_scheduler() -> None:
    """Stop the background scheduler if it is running."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler stopped")
