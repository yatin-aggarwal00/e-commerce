from __future__ import annotations

from pydantic import BaseModel, Field


class CartItemAdd(BaseModel):
    variant_id: str
    quantity: int = Field(default=1, ge=1, le=99)


class CartItemUpdate(BaseModel):
    quantity: int = Field(ge=0, le=99)  # 0 removes the line


class CartItemOut(BaseModel):
    id: str
    variant_id: str
    product_id: str
    product_name: str
    product_slug: str
    variant_name: str
    sku: str
    thumbnail: str | None = None
    unit_price_cents: int
    currency: str
    quantity: int
    line_total_cents: int
    available: int
    in_stock: bool


class CartOut(BaseModel):
    id: str
    token: str
    items: list[CartItemOut]
    subtotal_cents: int
    currency: str
    item_count: int
