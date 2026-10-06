from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession
from app.models.category import Category
from app.models.inventory import Inventory
from app.models.product import Product, ProductVariant
from app.schemas.catalog import (
    AutocompleteItem,
    CategoryOut,
    ProductDetail,
    ProductListItem,
    VariantOut,
)
from app.schemas.common import Page

router = APIRouter(prefix="/catalog", tags=["catalog"])

SortOption = Literal["newest", "price_asc", "price_desc", "name"]


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: DbSession) -> list[Category]:
    return list(db.scalars(select(Category).order_by(Category.name)).all())


@router.get("/products", response_model=Page[ProductListItem])
def list_products(
    db: DbSession,
    q: Annotated[str | None, Query(description="Free-text search")] = None,
    category: Annotated[str | None, Query(description="Category slug")] = None,
    room_type: str | None = None,
    material: str | None = None,
    color: str | None = None,
    price_min: Annotated[int | None, Query(ge=0, description="Min price in cents")] = None,
    price_max: Annotated[int | None, Query(ge=0, description="Max price in cents")] = None,
    in_stock: bool = False,
    sort: SortOption = "newest",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 24,
) -> Page[ProductListItem]:
    # Per-product aggregates: cheapest active variant price and total availability.
    price_sq = (
        select(
            ProductVariant.product_id.label("pid"),
            func.min(ProductVariant.price_cents).label("min_price"),
            func.min(ProductVariant.currency).label("currency"),
        )
        .where(ProductVariant.is_active.is_(True))
        .group_by(ProductVariant.product_id)
        .subquery()
    )
    stock_sq = (
        select(
            ProductVariant.product_id.label("pid"),
            func.coalesce(func.sum(Inventory.quantity - Inventory.reserved), 0).label("avail"),
        )
        .join(Inventory, Inventory.variant_id == ProductVariant.id)
        .group_by(ProductVariant.product_id)
        .subquery()
    )

    stmt = (
        select(
            Product,
            price_sq.c.min_price,
            price_sq.c.currency,
            func.coalesce(stock_sq.c.avail, 0).label("avail"),
        )
        .outerjoin(price_sq, price_sq.c.pid == Product.id)
        .outerjoin(stock_sq, stock_sq.c.pid == Product.id)
        .where(Product.is_active.is_(True))
    )

    # --- Filters --------------------------------------------------------
    if category:
        cat = db.scalar(select(Category).where(Category.slug == category))
        if cat is None:
            return Page(items=[], total=0, page=page, page_size=page_size)
        stmt = stmt.where(Product.category_id == cat.id)
    if room_type:
        stmt = stmt.where(func.lower(Product.room_type) == room_type.lower())
    if material:
        stmt = stmt.where(func.lower(Product.material) == material.lower())
    if color:
        stmt = stmt.where(
            exists().where(
                and_(
                    ProductVariant.product_id == Product.id,
                    func.lower(ProductVariant.color) == color.lower(),
                )
            )
        )
    if price_min is not None or price_max is not None:
        lo = price_min if price_min is not None else 0
        hi = price_max if price_max is not None else 2**31
        stmt = stmt.where(
            exists().where(
                and_(
                    ProductVariant.product_id == Product.id,
                    ProductVariant.price_cents >= lo,
                    ProductVariant.price_cents <= hi,
                )
            )
        )
    if q:
        like = f"%{q.strip()}%"
        # Portable ILIKE search for V1; upgrade path is Postgres full-text
        # search (to_tsvector/plainto_tsquery) or Algolia/Elasticsearch.
        stmt = stmt.where(
            or_(Product.name.ilike(like), Product.description.ilike(like))
        )
    if in_stock:
        stmt = stmt.where(func.coalesce(stock_sq.c.avail, 0) > 0)

    # --- Sorting --------------------------------------------------------
    if sort == "price_asc":
        stmt = stmt.order_by(price_sq.c.min_price.asc().nulls_last())
    elif sort == "price_desc":
        stmt = stmt.order_by(price_sq.c.min_price.desc().nulls_last())
    elif sort == "name":
        stmt = stmt.order_by(Product.name.asc())
    else:  # newest
        stmt = stmt.order_by(Product.created_at.desc())

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    rows = db.execute(
        stmt.options(selectinload(Product.images))
        .limit(page_size)
        .offset((page - 1) * page_size)
    ).all()

    items = [
        ProductListItem(
            id=product.id,
            name=product.name,
            slug=product.slug,
            room_type=product.room_type,
            material=product.material,
            category_id=product.category_id,
            thumbnail=product.images[0].url if product.images else None,
            min_price_cents=min_price,
            currency=currency or "usd",
            in_stock=(avail or 0) > 0,
        )
        for (product, min_price, currency, avail) in rows
    ]
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.get("/autocomplete", response_model=list[AutocompleteItem])
def autocomplete(
    db: DbSession,
    q: Annotated[str, Query(min_length=1)],
    limit: Annotated[int, Query(ge=1, le=20)] = 8,
) -> list[AutocompleteItem]:
    like = f"%{q.strip()}%"
    rows = db.scalars(
        select(Product)
        .where(and_(Product.is_active.is_(True), Product.name.ilike(like)))
        .order_by(Product.name)
        .limit(limit)
    ).all()
    return [AutocompleteItem(name=p.name, slug=p.slug) for p in rows]


@router.get("/facets")
def facets(db: DbSession) -> dict:
    """Distinct filter values for building the storefront filter sidebar."""
    room_types = db.scalars(
        select(Product.room_type)
        .where(and_(Product.is_active.is_(True), Product.room_type != ""))
        .distinct()
    ).all()
    materials = db.scalars(
        select(Product.material)
        .where(and_(Product.is_active.is_(True), Product.material != ""))
        .distinct()
    ).all()
    colors = db.scalars(
        select(ProductVariant.color).where(ProductVariant.color != "").distinct()
    ).all()
    price_bounds = db.execute(
        select(func.min(ProductVariant.price_cents), func.max(ProductVariant.price_cents))
    ).first()
    return {
        "room_types": sorted(room_types),
        "materials": sorted(materials),
        "colors": sorted(colors),
        "price_min_cents": price_bounds[0] or 0,
        "price_max_cents": price_bounds[1] or 0,
    }


def _variant_out(variant: ProductVariant) -> VariantOut:
    available = variant.inventory.available if variant.inventory else 0
    return VariantOut(
        id=variant.id,
        sku=variant.sku,
        name=variant.name,
        color=variant.color,
        size=variant.size,
        price_cents=variant.price_cents,
        currency=variant.currency,
        dimensions=variant.dimensions,
        weight_kg=variant.weight_kg,
        in_stock=available > 0,
        available=available,
    )


@router.get("/products/{slug}", response_model=ProductDetail)
def product_detail(slug: str, db: DbSession) -> ProductDetail:
    product = db.scalar(
        select(Product)
        .where(Product.slug == slug)
        .options(
            selectinload(Product.images),
            selectinload(Product.variants).selectinload(ProductVariant.inventory),
            selectinload(Product.category),
        )
    )
    if product is None or not product.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    return ProductDetail(
        id=product.id,
        name=product.name,
        slug=product.slug,
        description=product.description,
        category_id=product.category_id,
        room_type=product.room_type,
        material=product.material,
        is_active=product.is_active,
        category=CategoryOut.model_validate(product.category) if product.category else None,
        images=product.images,  # type: ignore[arg-type]
        variants=[_variant_out(v) for v in product.variants if v.is_active],
    )
