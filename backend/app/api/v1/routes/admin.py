from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentAdmin, DbSession
from app.core.redis_client import cache_delete_prefix
from app.models.category import Category
from app.models.inventory import Inventory
from app.models.order import Order, OrderStatus, PaymentStatus
from app.models.product import Product, ProductImage, ProductVariant
from app.schemas.admin import AdminStats, InventoryUpdate, VariantInventoryOut
from app.schemas.catalog import (
    CategoryCreate,
    CategoryOut,
    CategoryUpdate,
    ProductCreate,
    ProductDetail,
    ProductUpdate,
    VariantCreate,
    VariantOut,
)
from app.schemas.common import Message, Page
from app.schemas.order import OrderOut, OrderStatusUpdate
from app.services.email import send_order_status_update

# Every route here requires an admin (enforced via the router dependency).
router = APIRouter(
    prefix="/admin", tags=["admin"], dependencies=[]
)

LOW_STOCK_THRESHOLD = 5


# --- Dashboard ----------------------------------------------------------
@router.get("/stats", response_model=AdminStats)
def stats(db: DbSession, _: CurrentAdmin) -> AdminStats:
    products = db.scalar(select(func.count(Product.id))) or 0
    active_products = (
        db.scalar(select(func.count(Product.id)).where(Product.is_active.is_(True))) or 0
    )
    orders = db.scalar(select(func.count(Order.id))) or 0
    pending = (
        db.scalar(
            select(func.count(Order.id)).where(Order.status == OrderStatus.PENDING.value)
        )
        or 0
    )
    paid = (
        db.scalar(
            select(func.count(Order.id)).where(
                Order.payment_status == PaymentStatus.PAID.value
            )
        )
        or 0
    )
    revenue = (
        db.scalar(
            select(func.coalesce(func.sum(Order.total_cents), 0)).where(
                Order.payment_status == PaymentStatus.PAID.value
            )
        )
        or 0
    )
    low_stock = (
        db.scalar(
            select(func.count(Inventory.variant_id)).where(
                (Inventory.quantity - Inventory.reserved) <= LOW_STOCK_THRESHOLD
            )
        )
        or 0
    )
    return AdminStats(
        products=products,
        active_products=active_products,
        orders=orders,
        pending_orders=pending,
        paid_orders=paid,
        revenue_cents=revenue,
        low_stock=low_stock,
    )


# --- Categories ---------------------------------------------------------
@router.post("/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(payload: CategoryCreate, db: DbSession, _: CurrentAdmin) -> Category:
    if db.scalar(select(Category).where(Category.slug == payload.slug)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slug already exists")
    cat = Category(**payload.model_dump())
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


@router.patch("/categories/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: str, payload: CategoryUpdate, db: DbSession, _: CurrentAdmin
) -> Category:
    cat = db.get(Category, category_id)
    if cat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(cat, field, value)
    db.commit()
    db.refresh(cat)
    return cat


# --- Products -----------------------------------------------------------
@router.get("/products", response_model=Page[ProductDetail])
def admin_list_products(
    db: DbSession,
    _: CurrentAdmin,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Page[ProductDetail]:
    total = db.scalar(select(func.count(Product.id))) or 0
    products = db.scalars(
        select(Product)
        .options(
            selectinload(Product.images),
            selectinload(Product.variants).selectinload(ProductVariant.inventory),
            selectinload(Product.category),
        )
        .order_by(Product.created_at.desc())
        .limit(page_size)
        .offset((page - 1) * page_size)
    ).all()
    items = [_product_detail(p) for p in products]
    return Page(items=items, total=total, page=page, page_size=page_size)


def _variant_out(v: ProductVariant) -> VariantOut:
    available = v.inventory.available if v.inventory else 0
    return VariantOut(
        id=v.id, sku=v.sku, name=v.name, color=v.color, size=v.size,
        price_cents=v.price_cents, currency=v.currency, dimensions=v.dimensions,
        weight_kg=v.weight_kg, in_stock=available > 0, available=available,
    )


def _product_detail(p: Product) -> ProductDetail:
    return ProductDetail(
        id=p.id, name=p.name, slug=p.slug, description=p.description,
        category_id=p.category_id, room_type=p.room_type, material=p.material,
        is_active=p.is_active,
        category=CategoryOut.model_validate(p.category) if p.category else None,
        images=p.images,  # type: ignore[arg-type]
        variants=[_variant_out(v) for v in p.variants],
    )


def _add_variant(db: DbSession, product_id: str, data: VariantCreate) -> ProductVariant:
    if db.scalar(select(ProductVariant).where(ProductVariant.sku == data.sku)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"SKU {data.sku} already exists"
        )
    variant = ProductVariant(
        product_id=product_id,
        sku=data.sku, name=data.name, color=data.color, size=data.size,
        price_cents=data.price_cents, currency=data.currency,
        dimensions=data.dimensions, weight_kg=data.weight_kg,
    )
    db.add(variant)
    db.flush()
    db.add(Inventory(variant_id=variant.id, quantity=data.quantity))
    db.flush()
    return variant


@router.post("/products", response_model=ProductDetail, status_code=status.HTTP_201_CREATED)
def create_product(payload: ProductCreate, db: DbSession, _: CurrentAdmin) -> ProductDetail:
    if db.scalar(select(Product).where(Product.slug == payload.slug)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slug already exists")
    if db.get(Category, payload.category_id) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown category")

    product = Product(
        name=payload.name, slug=payload.slug, description=payload.description,
        category_id=payload.category_id, room_type=payload.room_type,
        material=payload.material, is_active=payload.is_active,
    )
    db.add(product)
    db.flush()
    for i, img in enumerate(payload.images):
        db.add(
            ProductImage(
                product_id=product.id, url=img.url, alt=img.alt, position=img.position or i
            )
        )
    for variant in payload.variants:
        _add_variant(db, product.id, variant)
    db.commit()
    cache_delete_prefix("catalog:")
    db.refresh(product)
    return _product_detail(product)


@router.patch("/products/{product_id}", response_model=ProductDetail)
def update_product(
    product_id: str, payload: ProductUpdate, db: DbSession, _: CurrentAdmin
) -> ProductDetail:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    data = payload.model_dump(exclude_unset=True)
    if "slug" in data and data["slug"] != product.slug:
        if db.scalar(select(Product).where(Product.slug == data["slug"])):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slug already exists")
    for field, value in data.items():
        setattr(product, field, value)
    db.commit()
    cache_delete_prefix("catalog:")
    db.refresh(product)
    return _product_detail(product)


@router.delete("/products/{product_id}", response_model=Message)
def deactivate_product(product_id: str, db: DbSession, _: CurrentAdmin) -> Message:
    """Soft-delete: products are deactivated, never hard-deleted, to preserve
    order history integrity."""
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    product.is_active = False
    db.commit()
    cache_delete_prefix("catalog:")
    return Message(detail="Product deactivated")


@router.post(
    "/products/{product_id}/variants",
    response_model=VariantOut,
    status_code=status.HTTP_201_CREATED,
)
def add_variant(
    product_id: str, payload: VariantCreate, db: DbSession, _: CurrentAdmin
) -> VariantOut:
    if db.get(Product, product_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    variant = _add_variant(db, product_id, payload)
    db.commit()
    db.refresh(variant)
    return _variant_out(variant)


# --- Inventory ----------------------------------------------------------
@router.put("/variants/{variant_id}/inventory", response_model=VariantInventoryOut)
def set_inventory(
    variant_id: str, payload: InventoryUpdate, db: DbSession, _: CurrentAdmin
) -> VariantInventoryOut:
    variant = db.get(ProductVariant, variant_id)
    if variant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variant not found")
    inv = variant.inventory
    if inv is None:
        inv = Inventory(variant_id=variant.id, quantity=payload.quantity)
        db.add(inv)
    else:
        inv.quantity = payload.quantity
    db.commit()
    db.refresh(inv)
    return VariantInventoryOut(
        variant_id=variant.id, sku=variant.sku, quantity=inv.quantity,
        reserved=inv.reserved, available=inv.available,
    )


# --- Orders -------------------------------------------------------------
@router.get("/orders", response_model=Page[OrderOut])
def admin_list_orders(
    db: DbSession,
    _: CurrentAdmin,
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Page[OrderOut]:
    base = select(Order)
    if status_filter:
        base = base.where(Order.status == status_filter)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    orders = db.scalars(
        base.options(selectinload(Order.items))
        .order_by(Order.created_at.desc())
        .limit(page_size)
        .offset((page - 1) * page_size)
    ).all()
    return Page(
        items=[OrderOut.model_validate(o) for o in orders],
        total=total, page=page, page_size=page_size,
    )


@router.patch("/orders/{order_number}/status", response_model=OrderOut)
def update_order_status(
    order_number: str, payload: OrderStatusUpdate, db: DbSession, _: CurrentAdmin
) -> Order:
    valid = {s.value for s in OrderStatus}
    if payload.status not in valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid status. Allowed: {sorted(valid)}",
        )
    order = db.scalar(
        select(Order)
        .where(Order.order_number == order_number)
        .options(selectinload(Order.items))
    )
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    order.status = payload.status
    db.commit()
    db.refresh(order)
    send_order_status_update(order.email, order.order_number, order.status)
    return order
