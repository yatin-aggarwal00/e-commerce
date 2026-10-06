from __future__ import annotations

import json

from fastapi import APIRouter, Header, HTTPException, Request, status
from sqlalchemy import select

from app.api.deps import DbSession
from app.core.config import settings
from app.models.order import Order, OrderStatus, PaymentStatus
from app.models.payment import Payment
from app.models.product import ProductVariant
from app.services.email import send_order_confirmation
from app.services.payment import PaymentError, get_payment_provider

router = APIRouter(prefix="/payments", tags=["payments"])


def _finalize_paid(db: DbSession, order: Order) -> None:
    """Commit reserved stock to a sale. Safe to call once per order."""
    for item in order.items:
        if not item.variant_id:
            continue
        variant = db.get(ProductVariant, item.variant_id)
        if variant and variant.inventory:
            variant.inventory.quantity = max(
                variant.inventory.quantity - item.quantity, 0
            )
            variant.inventory.reserved = max(
                variant.inventory.reserved - item.quantity, 0
            )


def _release_reservation(db: DbSession, order: Order) -> None:
    for item in order.items:
        if not item.variant_id:
            continue
        variant = db.get(ProductVariant, item.variant_id)
        if variant and variant.inventory:
            variant.inventory.reserved = max(
                variant.inventory.reserved - item.quantity, 0
            )


@router.post("/webhook")
async def payment_webhook(
    request: Request,
    db: DbSession,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
) -> dict:
    """Payment provider webhook.

    This endpoint is the single source of truth for marking an order paid.
    It is idempotent: replayed events never double-apply because an already
    ``paid`` order short-circuits, and ``provider_payment_id`` is unique.
    """
    payload = await request.body()
    provider = get_payment_provider()
    try:
        event = provider.verify_and_parse_webhook(payload, stripe_signature or "")
    except PaymentError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook signature"
        ) from err

    payment = db.scalar(
        select(Payment).where(Payment.provider_payment_id == event.payment_intent_id)
    )
    if payment is None:
        # Unknown intent: acknowledge so the provider stops retrying.
        return {"received": True, "handled": False}

    order = db.get(Order, payment.order_id)
    if order is None:
        return {"received": True, "handled": False}

    if event.type == "payment.succeeded":
        if order.payment_status == PaymentStatus.PAID.value:
            return {"received": True, "handled": True, "idempotent": True}
        payment.status = "succeeded"
        payment.raw = json.dumps(event.raw, default=str)[:8000]
        order.payment_status = PaymentStatus.PAID.value
        order.status = OrderStatus.PAID.value
        _finalize_paid(db, order)
        db.commit()
        send_order_confirmation(
            order.email, order.order_number, order.total_cents, order.currency
        )
        return {"received": True, "handled": True}

    if event.type == "payment.failed":
        # Never override a successful payment.
        if order.payment_status == PaymentStatus.PAID.value:
            return {"received": True, "handled": True, "idempotent": True}
        payment.status = "failed"
        payment.raw = json.dumps(event.raw, default=str)[:8000]
        order.payment_status = PaymentStatus.FAILED.value
        order.status = OrderStatus.FAILED.value
        _release_reservation(db, order)
        db.commit()
        return {"received": True, "handled": True}

    return {"received": True, "handled": False}


@router.post("/dev/confirm/{order_number}")
def dev_confirm_payment(order_number: str, db: DbSession) -> dict:
    """Dev-only helper to mark an order paid without a real gateway.

    This lets the storefront demo a full purchase end-to-end when running with
    the built-in ``fake`` payment provider. It is disabled in production and
    when a real (Stripe) provider is configured, where the webhook is the only
    path that can mark an order paid.
    """
    provider = get_payment_provider()
    if settings.ENVIRONMENT == "production" or provider.name != "fake":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not available")

    order = db.scalar(select(Order).where(Order.order_number == order_number))
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.payment_status == PaymentStatus.PAID.value:
        return {"status": "paid", "idempotent": True}

    order.payment_status = PaymentStatus.PAID.value
    order.status = OrderStatus.PAID.value
    for payment in order.payments:
        payment.status = "succeeded"
    _finalize_paid(db, order)
    db.commit()
    send_order_confirmation(order.email, order.order_number, order.total_cents, order.currency)
    return {"status": "paid"}
