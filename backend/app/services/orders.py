"""Order lifecycle services: stock-reservation release and pending-order expiry.

``release_order_reservation`` is the single stock-release path shared by the
failed-payment webhook branch (``routes/payments.py``) and the expiry job here,
so the two can never drift apart.

``expire_pending_orders`` cancels pending orders left unpaid past
``ORDER_PENDING_TTL_MINUTES`` and releases their reservation. It is safe to run
repeatedly and concurrently: each order is handled in its own transaction and
its status is re-checked under a row lock, so a reservation is released exactly
once and an order that reached ``paid`` in the meantime is never touched.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.observability import capture_exception
from app.models.order import Order, OrderStatus, PaymentStatus
from app.models.product import ProductVariant

logger = logging.getLogger("app.orders")


def release_order_reservation(db: Session, order: Order) -> int:
    """Return reserved stock for every line on ``order`` to its variant.

    Returns the number of units released. This is the exact release path used by
    the failed-payment webhook, so the webhook and the expiry job stay in sync.
    Clamped at zero so a double-release can never inflate (or negate) stock.
    """
    released = 0
    for item in order.items:
        if not item.variant_id:
            continue
        variant = db.get(ProductVariant, item.variant_id)
        if variant and variant.inventory:
            before = variant.inventory.reserved
            variant.inventory.reserved = max(before - item.quantity, 0)
            released += before - variant.inventory.reserved
    return released


@dataclass
class ExpiryResult:
    """Outcome of an ``expire_pending_orders`` run (used for logs / the API)."""

    expired_orders: int = 0
    released_units: int = 0
    order_numbers: list[str] = field(default_factory=list)


def _select_expiry_candidates(db: Session, cutoff: datetime) -> list[str]:
    """IDs of orders still pending and created before ``cutoff``.

    Only the IDs are snapshotted; each is re-checked under a lock before it is
    actually expired, so the window between this query and processing is safe.
    """
    return list(
        db.scalars(
            select(Order.id).where(
                Order.status == OrderStatus.PENDING.value,
                Order.created_at < cutoff,
            )
        ).all()
    )


def _expire_one(db: Session, order_id: str) -> int | None:
    """Expire a single order in its own transaction.

    Returns the units released, or ``None`` if the order was skipped (gone, or
    no longer pending because a webhook won the race). The status is re-checked
    under ``FOR UPDATE`` so this is idempotent and race-safe; on Postgres the
    row lock serialises against the payment webhook, and the re-check guards the
    behaviour everywhere (SQLite ignores the lock clause).
    """
    try:
        order = db.get(Order, order_id, with_for_update=True)
        # Re-check inside the transaction: a concurrent webhook may have marked
        # the order paid/failed, or another runner may have already expired it.
        if order is None or order.status != OrderStatus.PENDING.value:
            db.rollback()
            return None
        released = release_order_reservation(db, order)
        order.status = OrderStatus.CANCELLED.value
        # No payment ever completed; mark the payment side terminal too so the
        # order can't be mistaken for one still awaiting its webhook.
        order.payment_status = PaymentStatus.FAILED.value
        db.commit()
        return released
    except Exception as exc:  # noqa: BLE001 - one bad order must not stop the batch
        db.rollback()
        logger.exception("expire_pending_orders: failed to expire order %s", order_id)
        capture_exception(exc)
        return None


def expire_pending_orders(
    db: Session,
    *,
    ttl_minutes: int | None = None,
    now: datetime | None = None,
) -> ExpiryResult:
    """Cancel pending orders older than the TTL and release their stock.

    ``ttl_minutes`` / ``now`` are injectable for tests; both default to the
    configured TTL and the current UTC time. Emits one structured summary log
    line so a run is observable in production.
    """
    ttl = ttl_minutes if ttl_minutes is not None else settings.ORDER_PENDING_TTL_MINUTES
    reference = now or datetime.now(UTC)
    cutoff = reference - timedelta(minutes=ttl)

    result = ExpiryResult()
    for order_id in _select_expiry_candidates(db, cutoff):
        released = _expire_one(db, order_id)
        if released is None:
            continue
        order = db.get(Order, order_id)
        result.expired_orders += 1
        result.released_units += released
        if order is not None:
            result.order_numbers.append(order.order_number)

    logger.info(
        "expire_pending_orders complete: expired=%d released_units=%d ttl_minutes=%d orders=%s",
        result.expired_orders,
        result.released_units,
        ttl,
        ",".join(result.order_numbers) or "-",
    )
    return result
