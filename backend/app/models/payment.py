from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import Timestamps, UUIDPrimaryKey

if TYPE_CHECKING:
    from app.models.order import Order


class Payment(UUIDPrimaryKey, Timestamps, Base):
    """A payment attempt against an order.

    ``provider_payment_id`` is unique so replayed webhooks cannot create a
    duplicate paid record (idempotency).
    """

    __tablename__ = "payments"

    order_id: Mapped[str] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), index=True, nullable=False
    )
    provider: Mapped[str] = mapped_column(String(32), default="stripe")
    provider_payment_id: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), default="created", index=True)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="usd")
    # Raw provider payload, JSON-encoded, for auditing/debugging.
    raw: Mapped[str] = mapped_column(Text, default="{}")

    order: Mapped[Order] = relationship(back_populates="payments")
