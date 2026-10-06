"""Seed the database with demo catalog data and an admin user.

Run with::

    python -m app.seed

Idempotent: re-running will not duplicate rows (it checks by slug / email).
Intended for dev and staging only.
"""
from __future__ import annotations

import logging

from sqlalchemy import select

from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_password
from app.models.category import Category
from app.models.inventory import Inventory
from app.models.product import Product, ProductImage, ProductVariant
from app.models.user import User

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("seed")

ADMIN_EMAIL = "admin@furniture.example"
ADMIN_PASSWORD = "admin12345"

CATEGORIES = [
    ("Sofas", "sofas", "Comfortable seating for your living room"),
    ("Beds", "beds", "Restful beds and frames"),
    ("Tables", "tables", "Dining and coffee tables"),
    ("Chairs", "chairs", "Chairs for every room"),
    ("Storage", "storage", "Wardrobes, shelves and cabinets"),
]

# (name, slug, category_slug, room_type, material, description, [variants], [images])
PRODUCTS = [
    (
        "Nordic 3-Seater Sofa", "nordic-3-seater-sofa", "sofas", "Living Room", "Fabric",
        "A minimalist Scandinavian-style three-seater with solid oak legs.",
        [
            ("NORD-SOFA-GRY", "Light Grey", "grey", "3-Seater", 89900, "220 x 90 x 85 cm", 45, 12),
            ("NORD-SOFA-BLU", "Deep Blue", "blue", "3-Seater", 94900, "220 x 90 x 85 cm", 45, 6),
        ],
        ["https://images.unsplash.com/photo-1555041469-a586c61ea9bc"],
    ),
    (
        "Oakwood Queen Bed", "oakwood-queen-bed", "beds", "Bedroom", "Wood",
        "Solid oak queen bed frame with a slatted headboard.",
        [
            ("OAK-BED-QN", "Natural Oak", "brown", "Queen", 124900, "210 x 160 x 100 cm", 60, 8),
        ],
        ["https://images.unsplash.com/photo-1505693416388-ac5ce068fe85"],
    ),
    (
        "Marble Round Dining Table", "marble-round-dining-table", "tables", "Dining Room", "Marble",
        "Carrara-style marble top on a powder-coated steel base, seats four.",
        [
            ("MARB-TBL-WHT", "White Marble", "white", "4-Seat", 159900, "120 x 120 x 75 cm", 40, 5),
        ],
        ["https://images.unsplash.com/photo-1577140917170-285929fb55b7"],
    ),
    (
        "Ergonomic Lounge Chair", "ergonomic-lounge-chair", "chairs", "Living Room", "Leather",
        "Mid-century lounge chair with full-grain leather and walnut shell.",
        [
            ("ERGO-CHR-TAN", "Tan Leather", "brown", "Standard", 74900, "80 x 85 x 90 cm", 25, 15),
            ("ERGO-CHR-BLK", "Black Leather", "black", "Standard", 74900, "80 x 85 x 90 cm", 25, 0),
        ],
        ["https://images.unsplash.com/photo-1567538096630-e0c55bd6374c"],
    ),
    (
        "Modular Bookshelf", "modular-bookshelf", "storage", "Study", "Wood",
        "Five-tier modular bookshelf in engineered oak.",
        [
            ("MOD-SHELF-OAK", "Oak", "brown", "5-Tier", 44900, "80 x 30 x 180 cm", 35, 20),
        ],
        ["https://images.unsplash.com/photo-1594620302200-9a762244a156"],
    ),
]


def run() -> None:
    # Dev convenience: ensure tables exist. In staging/prod use Alembic instead.
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        # Admin user
        if db.scalar(select(User).where(User.email == ADMIN_EMAIL)) is None:
            db.add(
                User(
                    email=ADMIN_EMAIL,
                    hashed_password=hash_password(ADMIN_PASSWORD),
                    full_name="Store Admin",
                    is_admin=True,
                )
            )
            log.info("Created admin user %s / %s", ADMIN_EMAIL, ADMIN_PASSWORD)

        cat_by_slug: dict[str, Category] = {}
        for name, slug, desc in CATEGORIES:
            cat = db.scalar(select(Category).where(Category.slug == slug))
            if cat is None:
                cat = Category(name=name, slug=slug, description=desc)
                db.add(cat)
                db.flush()
            cat_by_slug[slug] = cat

        for (name, slug, cat_slug, room, material, desc, variants, images) in PRODUCTS:
            if db.scalar(select(Product).where(Product.slug == slug)):
                continue
            product = Product(
                name=name, slug=slug, description=desc,
                category_id=cat_by_slug[cat_slug].id,
                room_type=room, material=material,
            )
            db.add(product)
            db.flush()
            for pos, url in enumerate(images):
                db.add(ProductImage(product_id=product.id, url=url, alt=name, position=pos))
            for sku, vname, color, size, price, dims, weight, stock in variants:
                variant = ProductVariant(
                    product_id=product.id, sku=sku, name=vname, color=color,
                    size=size, price_cents=price, currency=settings.CURRENCY,
                    dimensions=dims, weight_kg=weight,
                )
                db.add(variant)
                db.flush()
                db.add(Inventory(variant_id=variant.id, quantity=stock))
            log.info("Seeded product %s", name)

        db.commit()
    log.info("Seeding complete.")


if __name__ == "__main__":
    run()
