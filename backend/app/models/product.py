from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import Timestamps, UUIDPrimaryKey

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.inventory import Inventory


class Product(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "products"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(280), unique=True, index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    category_id: Mapped[str] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    # Facets used by storefront filters.
    room_type: Mapped[str] = mapped_column(String(64), default="", index=True)
    material: Mapped[str] = mapped_column(String(64), default="", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    category: Mapped[Category] = relationship(back_populates="products")
    images: Mapped[list[ProductImage]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductImage.position",
    )
    variants: Mapped[list[ProductVariant]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )


class ProductImage(UUIDPrimaryKey, Base):
    __tablename__ = "product_images"

    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False
    )
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    alt: Mapped[str] = mapped_column(String(255), default="")
    position: Mapped[int] = mapped_column(Integer, default=0)

    product: Mapped[Product] = relationship(back_populates="images")


class ProductVariant(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "product_variants"

    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False
    )
    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), default="Default")
    color: Mapped[str] = mapped_column(String(64), default="", index=True)
    size: Mapped[str] = mapped_column(String(64), default="")
    # Money is always stored as integer minor units (cents) to avoid floats.
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="usd")
    # Dimensions as a free-form display string, e.g. "200 x 90 x 75 cm".
    dimensions: Mapped[str] = mapped_column(String(255), default="")
    weight_kg: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    product: Mapped[Product] = relationship(back_populates="variants")
    inventory: Mapped[Inventory] = relationship(
        back_populates="variant", uselist=False, cascade="all, delete-orphan"
    )
