"""Cart domain helpers: resolve/create carts, serialise, merge on login."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.cart import Cart, CartItem
from app.models.product import Product, ProductVariant
from app.schemas.cart import CartItemOut, CartOut


def get_or_create_cart(
    db: Session, *, token: str | None = None, user_id: str | None = None
) -> Cart:
    """Resolve the active cart for a request.

    Priority: the logged-in user's cart, else the cart identified by ``token``,
    else a freshly created cart.
    """
    cart: Cart | None = None
    if user_id:
        cart = db.scalar(select(Cart).where(Cart.user_id == user_id))
    if cart is None and token:
        cart = db.scalar(select(Cart).where(Cart.token == token))
        # Claim an anonymous cart for the user who just logged in.
        if cart and user_id and cart.user_id is None:
            cart.user_id = user_id
    if cart is None:
        cart = Cart(user_id=user_id)
        db.add(cart)
        db.flush()
    return cart


def merge_carts(db: Session, *, guest_token: str, user_id: str) -> Cart:
    """Merge a guest cart into the user's cart on login, summing quantities."""
    user_cart = get_or_create_cart(db, user_id=user_id)
    guest_cart = db.scalar(select(Cart).where(Cart.token == guest_token))
    if guest_cart and guest_cart.id != user_cart.id:
        existing = {i.variant_id: i for i in user_cart.items}
        for item in list(guest_cart.items):
            if item.variant_id in existing:
                existing[item.variant_id].quantity += item.quantity
            else:
                db.add(
                    CartItem(
                        cart_id=user_cart.id,
                        variant_id=item.variant_id,
                        quantity=item.quantity,
                    )
                )
        db.delete(guest_cart)
        db.flush()
    return user_cart


def serialize_cart(db: Session, cart: Cart) -> CartOut:
    """Build the API representation, joining product + inventory data."""
    rows = db.scalars(
        select(CartItem)
        .where(CartItem.cart_id == cart.id)
        .options(
            selectinload(CartItem.variant)
            .selectinload(ProductVariant.product)
            .selectinload(Product.images),
            selectinload(CartItem.variant).selectinload(ProductVariant.inventory),
        )
    ).all()

    items: list[CartItemOut] = []
    subtotal = 0
    currency = "usd"
    for row in rows:
        variant = row.variant
        if variant is None:
            continue
        product = variant.product
        available = variant.inventory.available if variant.inventory else 0
        thumb = product.images[0].url if product.images else None
        line_total = variant.price_cents * row.quantity
        subtotal += line_total
        currency = variant.currency
        items.append(
            CartItemOut(
                id=row.id,
                variant_id=variant.id,
                product_id=product.id,
                product_name=product.name,
                product_slug=product.slug,
                variant_name=variant.name,
                sku=variant.sku,
                thumbnail=thumb,
                unit_price_cents=variant.price_cents,
                currency=variant.currency,
                quantity=row.quantity,
                line_total_cents=line_total,
                available=available,
                in_stock=available > 0,
            )
        )

    return CartOut(
        id=cart.id,
        token=cart.token,
        items=items,
        subtotal_cents=subtotal,
        currency=currency,
        item_count=sum(i.quantity for i in items),
    )
