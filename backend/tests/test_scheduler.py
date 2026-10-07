"""Scheduler wiring, the single-flight Redis lock, and the job runner.

These exercise the plumbing around the expiry job (locking, error isolation,
start/stop) without waiting on the real APScheduler interval.
"""
from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import select

from app import scheduler as scheduler_module
from app.core import redis_client
from app.models.order import Order, OrderStatus
from tests.test_order_expiry import _backdate, _checkout
from tests.test_orders import _inventory


@contextmanager
def _lock(acquired: bool):
    yield acquired


def test_job_runner_expires_orders_when_lock_acquired(client, admin_token, db, monkeypatch):
    res = _checkout(client, admin_token, sku="SCH1", qty=2, stock=10)
    number = res["order"]["order_number"]
    _backdate(db, number, minutes=120)

    monkeypatch.setattr(scheduler_module, "try_lock", lambda *a, **k: _lock(True))
    scheduler_module.run_expire_pending_orders_job()

    assert _inventory(db, "SCH1").reserved == 0
    order = db.scalar(select(Order).where(Order.order_number == number))
    assert order.status == OrderStatus.CANCELLED.value


def test_job_runner_skips_when_lock_held_elsewhere(client, admin_token, db, monkeypatch):
    res = _checkout(client, admin_token, sku="SCH2", qty=2, stock=10)
    number = res["order"]["order_number"]
    _backdate(db, number, minutes=120)

    monkeypatch.setattr(scheduler_module, "try_lock", lambda *a, **k: _lock(False))
    scheduler_module.run_expire_pending_orders_job()

    # Lock not acquired -> work skipped, reservation still held.
    assert _inventory(db, "SCH2").reserved == 2
    order = db.scalar(select(Order).where(Order.order_number == number))
    assert order.status == OrderStatus.PENDING.value


def test_job_runner_swallows_errors(monkeypatch):
    monkeypatch.setattr(scheduler_module, "try_lock", lambda *a, **k: _lock(True))

    def _boom(*_a, **_k):
        raise RuntimeError("db exploded")

    monkeypatch.setattr(scheduler_module, "expire_pending_orders", _boom)
    # Must not raise: a job error is logged + reported, never propagated.
    scheduler_module.run_expire_pending_orders_job()


def test_start_scheduler_disabled_returns_none(monkeypatch):
    monkeypatch.setattr(scheduler_module.settings, "SCHEDULER_ENABLED", False)
    assert scheduler_module.start_scheduler() is None


def test_start_and_shutdown_scheduler(monkeypatch):
    monkeypatch.setattr(scheduler_module.settings, "SCHEDULER_ENABLED", True)
    monkeypatch.setattr(scheduler_module, "_scheduler", None)
    sched = scheduler_module.start_scheduler()
    try:
        assert sched is not None and sched.running
        # Idempotent: a second start returns the same instance.
        assert scheduler_module.start_scheduler() is sched
    finally:
        scheduler_module.shutdown_scheduler()
    assert scheduler_module._scheduler is None


def test_try_lock_falls_back_to_running_without_redis(monkeypatch):
    # No Redis client configured -> the lock degrades to "run anyway".
    monkeypatch.setattr(redis_client, "_client", None)
    with redis_client.try_lock("some-job", 60) as acquired:
        assert acquired is True


def test_try_lock_runs_when_redis_unreachable():
    # The default client never connects in tests; acquire() raises and we fall
    # back to running (DB transactions guarantee correctness regardless).
    with redis_client.try_lock("another-job", 60) as acquired:
        assert acquired is True
