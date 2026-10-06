from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import Timestamps, UUIDPrimaryKey

if TYPE_CHECKING:
    from app.models.payment import Payment
    from app.models.user import User


class OrderStatus(enum.StrEnum):
    PENDING = "pending"          # created, awaiting payment
    PAID = "paid"                # payment confirmed
    PROCESSING = "processing"    # being prepared
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    FAILED = "failed"            # payment failed / abandoned


class PaymentStatus(enum.StrEnum):
    UNPAID = "unpaid"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"


class Order(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "orders"

    order_number: Mapped[str] = mapped_column(
        String(20), unique=True, index=True, nullable=False
    )
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)

    status: Mapped[str] = mapped_column(
        String(20), default=OrderStatus.PENDING.value, index=True
    )
    payment_status: Mapped[str] = mapped_column(
        String(20), default=PaymentStatus.UNPAID.value, index=True
    )

    # Money in minor units.
    subtotal_cents: Mapped[int] = mapped_column(Integer, default=0)
    shipping_cents: Mapped[int] = mapped_column(Integer, default=0)
    total_cents: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="usd")

    delivery_option: Mapped[str] = mapped_column(String(32), default="standard")
    # JSON-serialised snapshot of the shipping address at purchase time.
    shipping_address: Mapped[str] = mapped_column(Text, default="{}")

    user: Mapped[User | None] = relationship(back_populates="orders")
    items: Mapped[list[OrderItem]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    payments: Mapped[list[Payment]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class OrderItem(UUIDPrimaryKey, Base):
    __tablename__ = "order_items"

    order_id: Mapped[str] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), index=True, nullable=False
    )
    variant_id: Mapped[str | None] = mapped_column(
        ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True
    )
    # Denormalised snapshots so order history survives product edits/deletes.
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    variant_name: Mapped[str] = mapped_column(String(255), default="")
    sku: Mapped[str] = mapped_column(String(64), default="")
    unit_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    order: Mapped[Order] = relationship(back_populates="items")

    @property
    def line_total_cents(self) -> int:
        return self.unit_price_cents * self.quantity
