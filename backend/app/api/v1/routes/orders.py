from __future__ import annotations

import json
import secrets

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession, OptionalUser
from app.models.address import Address
from app.models.order import Order, OrderItem, OrderStatus, PaymentStatus
from app.models.payment import Payment
from app.models.product import Product, ProductVariant
from app.schemas.order import (
    CheckoutRequest,
    CheckoutResponse,
    OrderOut,
)
from app.services.cart import get_or_create_cart
from app.services.payment import get_payment_provider
from app.services.pricing import order_total_cents

router = APIRouter(tags=["orders"])


def _generate_order_number() -> str:
    return "ORD-" + secrets.token_hex(5).upper()


@router.post("/checkout", response_model=CheckoutResponse, status_code=status.HTTP_201_CREATED)
def checkout(
    payload: CheckoutRequest, db: DbSession, user: OptionalUser
) -> CheckoutResponse:
    cart = get_or_create_cart(
        db, token=payload.cart_token, user_id=user.id if user else None
    )
    if not cart.items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cart is empty")

    # --- Resolve shipping address --------------------------------------
    if payload.address_id:
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Login required to use a saved address",
            )
        addr = db.get(Address, payload.address_id)
        if addr is None or addr.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Address not found"
            )
        shipping_snapshot = addr.as_snapshot()
    elif payload.shipping_address:
        shipping_snapshot = payload.shipping_address.model_dump()
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A shipping address is required",
        )

    # --- Build order lines + reserve stock -----------------------------
    order = Order(
        order_number=_generate_order_number(),
        user_id=user.id if user else None,
        email=payload.email.lower(),
        status=OrderStatus.PENDING.value,
        payment_status=PaymentStatus.UNPAID.value,
        delivery_option=payload.delivery_option,
        shipping_address=json.dumps(shipping_snapshot),
    )

    subtotal = 0
    currency = "usd"
    for item in list(cart.items):
        variant = db.get(ProductVariant, item.variant_id)
        if variant is None or not variant.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A product in your cart is no longer available",
            )
        available = variant.inventory.available if variant.inventory else 0
        if item.quantity > available:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Insufficient stock for {variant.sku}",
            )
        product = db.get(Product, variant.product_id)
        # Reserve stock so a concurrent checkout can't oversell.
        variant.inventory.reserved += item.quantity
        subtotal += variant.price_cents * item.quantity
        currency = variant.currency
        order.items.append(
            OrderItem(
                variant_id=variant.id,
                product_name=product.name if product else "",
                variant_name=variant.name,
                sku=variant.sku,
                unit_price_cents=variant.price_cents,
                quantity=item.quantity,
            )
        )

    shipping, total = order_total_cents(subtotal, payload.delivery_option)
    order.subtotal_cents = subtotal
    order.shipping_cents = shipping
    order.total_cents = total
    order.currency = currency

    db.add(order)
    db.flush()

    # --- Create payment intent -----------------------------------------
    provider = get_payment_provider()
    intent = provider.create_payment_intent(
        amount_cents=total,
        currency=currency,
        metadata={"order_id": order.id, "order_number": order.order_number},
    )
    db.add(
        Payment(
            order_id=order.id,
            provider=provider.name,
            provider_payment_id=intent.id,
            status=intent.status,
            amount_cents=total,
            currency=currency,
            raw=json.dumps({"client_secret": "***", "status": intent.status}),
        )
    )

    # Empty the cart so the same cart can't be checked out twice (prevents
    # duplicate orders). Items are already snapshotted on the order.
    for item in list(cart.items):
        db.delete(item)

    db.commit()
    db.refresh(order)

    return CheckoutResponse(
        order=OrderOut.model_validate(order),
        payment_client_secret=intent.client_secret,
        payment_intent_id=intent.id,
        provider=provider.name,
    )


@router.get("/orders", response_model=list[OrderOut])
def list_orders(db: DbSession, user: CurrentUser) -> list[Order]:
    return list(
        db.scalars(
            select(Order)
            .where(Order.user_id == user.id)
            .options(selectinload(Order.items))
            .order_by(Order.created_at.desc())
        ).all()
    )


@router.get("/orders/{order_number}", response_model=OrderOut)
def get_order(
    order_number: str,
    db: DbSession,
    user: OptionalUser,
    email: str | None = Query(default=None, description="Required for guest lookups"),
) -> Order:
    order = db.scalar(
        select(Order)
        .where(Order.order_number == order_number)
        .options(selectinload(Order.items))
    )
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    # Owner may always view; guests must present the matching email.
    is_owner = user is not None and order.user_id == user.id
    is_guest_match = email is not None and order.email == email.lower()
    if not (is_owner or is_guest_match):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorised to view this order"
        )
    return order
