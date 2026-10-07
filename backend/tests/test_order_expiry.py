"""Scheduled expiry of abandoned pending orders (EC-4).

Covers every acceptance criterion: TTL boundary, stock release via the shared
helper, the paid/cancelled no-op guards, double-run idempotency, the
paid-in-the-meantime race, configurability, observability, and the on-demand
admin trigger.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models.order import Order, OrderStatus, PaymentStatus
from app.services import orders as orders_service
from app.services.orders import expire_pending_orders
from tests.conftest import auth
from tests.helpers import create_category, create_product
from tests.test_orders import _inventory, _webhook


def _checkout(client, admin_token, *, sku, qty=1, stock=10, price_cents=50000) -> dict:
    """Create a product and check out ``qty`` units; returns the checkout body."""
    cat = create_category(client, admin_token, slug=f"cat-{sku}")
    product = create_product(
        client, admin_token, category_id=cat["id"], slug=f"prod-{sku}",
        name=f"Prod {sku}", sku=sku, price_cents=price_cents, quantity=stock,
    )
    vid = product["variants"][0]["id"]
    cart = client.post(
        "/api/v1/cart/items", json={"variant_id": vid, "quantity": qty}
    ).json()
    r = client.post(
        "/api/v1/checkout",
        json={
            "cart_token": cart["token"],
            "email": "buyer@example.com",
            "shipping_address": {
                "full_name": "Buyer", "line1": "1 Main St", "city": "Town",
                "postal_code": "12345", "country": "US",
            },
            "delivery_option": "standard",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def _backdate(db, order_number: str, minutes: int) -> None:
    """Pretend the order was created ``minutes`` ago so the TTL applies."""
    order = db.scalar(select(Order).where(Order.order_number == order_number))
    order.created_at = datetime.now(UTC) - timedelta(minutes=minutes)
    db.commit()


# --- AC1 + AC5: expired pending order is cancelled and stock released --------
def test_expired_pending_order_is_cancelled_and_stock_released(client, admin_token, db):
    res = _checkout(client, admin_token, sku="EXP1", qty=3, stock=10)
    number = res["order"]["order_number"]
    assert _inventory(db, "EXP1").reserved == 3

    _backdate(db, number, minutes=120)
    result = expire_pending_orders(db, ttl_minutes=60)

    assert result.expired_orders == 1
    assert result.released_units == 3
    assert number in result.order_numbers

    inv = _inventory(db, "EXP1")
    assert inv.reserved == 0 and inv.quantity == 10  # released, nothing sold

    # AC5: the customer sees the order as cancelled, not perpetually pending.
    order = client.get(
        f"/api/v1/orders/{number}", params={"email": res["order"]["email"]}
    ).json()
    assert order["status"] == OrderStatus.CANCELLED.value
    assert order["payment_status"] == PaymentStatus.FAILED.value


# --- AC2: an order younger than the TTL is left untouched -------------------
def test_young_pending_order_is_left_untouched(client, admin_token, db):
    res = _checkout(client, admin_token, sku="EXP2", qty=2, stock=10)
    number = res["order"]["order_number"]
    _backdate(db, number, minutes=30)  # younger than the 60-min TTL

    result = expire_pending_orders(db, ttl_minutes=60)

    assert result.expired_orders == 0
    inv = _inventory(db, "EXP2")
    assert inv.reserved == 2  # still held
    order = db.scalar(select(Order).where(Order.order_number == number))
    assert order.status == OrderStatus.PENDING.value


# --- AC3: a paid order is never expired -------------------------------------
def test_paid_order_is_not_expired(client, admin_token, db):
    res = _checkout(client, admin_token, sku="EXP3", qty=1, stock=10)
    number = res["order"]["order_number"]
    assert _webhook(client, "payment.succeeded", res["payment_intent_id"]).json()["handled"]

    _backdate(db, number, minutes=120)
    result = expire_pending_orders(db, ttl_minutes=60)

    assert result.expired_orders == 0
    inv = _inventory(db, "EXP3")
    assert inv.quantity == 9 and inv.reserved == 0  # sold, not released
    order = db.scalar(select(Order).where(Order.order_number == number))
    assert order.status == OrderStatus.PAID.value


# --- AC3: an already-failed/cancelled order is not touched ------------------
def test_already_failed_order_is_not_touched(client, admin_token, db):
    res = _checkout(client, admin_token, sku="EXP4", qty=1, stock=10)
    number = res["order"]["order_number"]
    # Failed webhook already released the reservation and set status=failed.
    _webhook(client, "payment.failed", res["payment_intent_id"])
    assert _inventory(db, "EXP4").reserved == 0

    _backdate(db, number, minutes=120)
    result = expire_pending_orders(db, ttl_minutes=60)

    assert result.expired_orders == 0
    assert _inventory(db, "EXP4").reserved == 0  # not released a second time
    order = db.scalar(select(Order).where(Order.order_number == number))
    assert order.status == OrderStatus.FAILED.value


# --- AC4: running twice releases each reservation exactly once --------------
def test_running_twice_releases_stock_once(client, admin_token, db):
    res = _checkout(client, admin_token, sku="EXP5", qty=4, stock=10)
    number = res["order"]["order_number"]
    _backdate(db, number, minutes=120)

    first = expire_pending_orders(db, ttl_minutes=60)
    second = expire_pending_orders(db, ttl_minutes=60)

    assert first.expired_orders == 1 and first.released_units == 4
    assert second.expired_orders == 0 and second.released_units == 0
    inv = _inventory(db, "EXP5")
    assert inv.reserved == 0 and inv.quantity == 10  # not double-released


# --- AC4: paid-in-the-meantime race is guarded inside the transaction -------
def test_paid_in_the_meantime_race_is_not_expired(client, admin_token, db, monkeypatch):
    """An order selected as a candidate but marked paid before processing.

    Simulates the webhook winning the race between candidate selection and the
    per-order transaction. The in-transaction status re-check must skip it.
    """
    res = _checkout(client, admin_token, sku="EXP6", qty=2, stock=10)
    number = res["order"]["order_number"]
    order_id = db.scalar(select(Order).where(Order.order_number == number)).id

    # Force this order to be treated as an expiry candidate...
    monkeypatch.setattr(
        orders_service, "_select_expiry_candidates", lambda _db, _cutoff: [order_id]
    )
    # ...then let the webhook win the race just before per-order processing.
    order = db.scalar(select(Order).where(Order.id == order_id))
    order.status = OrderStatus.PAID.value
    order.payment_status = PaymentStatus.PAID.value
    db.commit()

    result = expire_pending_orders(db, ttl_minutes=60)

    assert result.expired_orders == 0
    inv = _inventory(db, "EXP6")
    assert inv.reserved == 2  # untouched — reservation not released
    assert db.scalar(select(Order).where(Order.id == order_id)).status == OrderStatus.PAID.value


# --- AC6: the TTL is configurable -------------------------------------------
def test_ttl_is_configurable(client, admin_token, db):
    res = _checkout(client, admin_token, sku="EXP7", qty=1, stock=10)
    number = res["order"]["order_number"]
    _backdate(db, number, minutes=45)

    # With a 60-min TTL the 45-min-old order survives...
    assert expire_pending_orders(db, ttl_minutes=60).expired_orders == 0
    # ...but a tighter 30-min TTL expires it.
    assert expire_pending_orders(db, ttl_minutes=30).expired_orders == 1
    assert _inventory(db, "EXP7").reserved == 0


def test_default_ttl_is_sixty_minutes():
    from app.core.config import settings

    assert settings.ORDER_PENDING_TTL_MINUTES == 60


# --- AC7: a run emits a structured, observable summary line -----------------
def test_run_emits_structured_summary_log(client, admin_token, db, caplog):
    res = _checkout(client, admin_token, sku="EXP8", qty=2, stock=10)
    _backdate(db, res["order"]["order_number"], minutes=120)

    with caplog.at_level(logging.INFO, logger="app.orders"):
        expire_pending_orders(db, ttl_minutes=60)

    line = next(m for m in caplog.messages if "expire_pending_orders complete" in m)
    assert "expired=1" in line and "released_units=2" in line


# --- On-demand admin trigger ------------------------------------------------
def test_admin_can_trigger_expiry_on_demand(client, admin_token, db):
    res = _checkout(client, admin_token, sku="EXP9", qty=3, stock=10)
    number = res["order"]["order_number"]
    _backdate(db, number, minutes=120)  # default 60-min TTL will catch it

    r = client.post("/api/v1/admin/orders/expire-pending", headers=auth(admin_token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["expired_orders"] == 1
    assert body["released_units"] == 3
    assert number in body["order_numbers"]
    assert _inventory(db, "EXP9").reserved == 0


def test_expire_pending_requires_admin(client):
    r = client.post("/api/v1/admin/orders/expire-pending")
    assert r.status_code == 401


# --- Error isolation: a failing order rolls back and is skipped -------------
def test_failure_on_one_order_is_isolated(client, admin_token, db, monkeypatch):
    res = _checkout(client, admin_token, sku="EXP10", qty=2, stock=10)
    number = res["order"]["order_number"]
    _backdate(db, number, minutes=120)

    def _boom(*_a, **_k):
        raise RuntimeError("release failed")

    monkeypatch.setattr(orders_service, "release_order_reservation", _boom)
    result = expire_pending_orders(db, ttl_minutes=60)

    assert result.expired_orders == 0  # error caught, order left for the next run
    order = db.scalar(select(Order).where(Order.order_number == number))
    assert order.status == OrderStatus.PENDING.value
    assert _inventory(db, "EXP10").reserved == 2  # rolled back, nothing lost


def test_release_ignores_items_without_a_variant(db):
    """A line whose variant was deleted (variant_id NULL) is simply skipped."""
    from app.models.order import OrderItem

    order = Order(
        order_number="ORD-NOVAR", email="x@example.com",
        status=OrderStatus.PENDING.value, payment_status=PaymentStatus.UNPAID.value,
    )
    order.items.append(
        OrderItem(variant_id=None, product_name="Gone", unit_price_cents=1000, quantity=2)
    )
    db.add(order)
    db.commit()

    assert orders_service.release_order_reservation(db, order) == 0


def test_capture_exception_is_a_safe_noop():
    from app.core.observability import capture_exception

    # No Sentry configured in tests: must not raise.
    capture_exception(RuntimeError("boom"))
