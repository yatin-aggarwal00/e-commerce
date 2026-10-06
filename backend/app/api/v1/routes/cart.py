from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CartToken, CurrentUser, DbSession, OptionalUser
from app.models.cart import CartItem
from app.models.product import ProductVariant
from app.schemas.cart import CartItemAdd, CartItemUpdate, CartOut
from app.services.cart import get_or_create_cart, merge_carts, serialize_cart

router = APIRouter(prefix="/cart", tags=["cart"])


def _load_variant(db: DbSession, variant_id: str) -> ProductVariant:
    variant = db.get(ProductVariant, variant_id)
    if variant is None or not variant.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variant not found")
    return variant


def _assert_stock(variant: ProductVariant, requested_qty: int) -> None:
    available = variant.inventory.available if variant.inventory else 0
    if requested_qty > available:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Only {available} in stock",
        )


@router.get("", response_model=CartOut)
def get_cart(db: DbSession, user: OptionalUser, token: CartToken) -> CartOut:
    cart = get_or_create_cart(db, token=token, user_id=user.id if user else None)
    db.commit()
    return serialize_cart(db, cart)


@router.post("/items", response_model=CartOut, status_code=status.HTTP_201_CREATED)
def add_item(
    payload: CartItemAdd, db: DbSession, user: OptionalUser, token: CartToken
) -> CartOut:
    cart = get_or_create_cart(db, token=token, user_id=user.id if user else None)
    variant = _load_variant(db, payload.variant_id)

    item = db.scalar(
        select(CartItem).where(
            CartItem.cart_id == cart.id, CartItem.variant_id == variant.id
        )
    )
    new_qty = (item.quantity if item else 0) + payload.quantity
    _assert_stock(variant, new_qty)

    if item:
        item.quantity = new_qty
    else:
        db.add(CartItem(cart_id=cart.id, variant_id=variant.id, quantity=payload.quantity))
    db.commit()
    return serialize_cart(db, cart)


@router.patch("/items/{item_id}", response_model=CartOut)
def update_item(
    item_id: str,
    payload: CartItemUpdate,
    db: DbSession,
    user: OptionalUser,
    token: CartToken,
) -> CartOut:
    cart = get_or_create_cart(db, token=token, user_id=user.id if user else None)
    item = db.get(CartItem, item_id)
    if item is None or item.cart_id != cart.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    if payload.quantity == 0:
        db.delete(item)
    else:
        _assert_stock(item.variant, payload.quantity)
        item.quantity = payload.quantity
    db.commit()
    return serialize_cart(db, cart)


@router.delete("/items/{item_id}", response_model=CartOut)
def remove_item(
    item_id: str, db: DbSession, user: OptionalUser, token: CartToken
) -> CartOut:
    cart = get_or_create_cart(db, token=token, user_id=user.id if user else None)
    item = db.get(CartItem, item_id)
    if item and item.cart_id == cart.id:
        db.delete(item)
        db.commit()
    return serialize_cart(db, cart)


@router.delete("", response_model=CartOut)
def clear_cart(db: DbSession, user: OptionalUser, token: CartToken) -> CartOut:
    cart = get_or_create_cart(db, token=token, user_id=user.id if user else None)
    for item in list(cart.items):
        db.delete(item)
    db.commit()
    return serialize_cart(db, cart)


@router.post("/merge", response_model=CartOut)
def merge(guest_token: str, db: DbSession, user: CurrentUser) -> CartOut:
    """Merge a guest cart (by token) into the authenticated user's cart."""
    cart = merge_carts(db, guest_token=guest_token, user_id=user.id)
    db.commit()
    return serialize_cart(db, cart)
