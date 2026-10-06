from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import Timestamps

if TYPE_CHECKING:
    from app.models.product import ProductVariant


class Inventory(Timestamps, Base):
    """Stock level per variant.

    ``available`` = ``quantity`` - ``reserved``. Reservations are held while an
    order is pending payment so two shoppers cannot buy the last unit.
    """

    __tablename__ = "inventory"

    variant_id: Mapped[str] = mapped_column(
        ForeignKey("product_variants.id", ondelete="CASCADE"),
        primary_key=True,
    )
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    reserved: Mapped[int] = mapped_column(Integer, default=0)
    # Low-level SKU location, optional for V1.
    warehouse: Mapped[str] = mapped_column(String(64), default="main")

    variant: Mapped[ProductVariant] = relationship(back_populates="inventory")

    @property
    def available(self) -> int:
        return max(self.quantity - self.reserved, 0)
