from __future__ import annotations

from pydantic import BaseModel, Field


class InventoryUpdate(BaseModel):
    quantity: int = Field(ge=0)


class VariantInventoryOut(BaseModel):
    variant_id: str
    sku: str
    quantity: int
    reserved: int
    available: int


class AdminStats(BaseModel):
    products: int
    active_products: int
    orders: int
    pending_orders: int
    paid_orders: int
    revenue_cents: int
    low_stock: int


class UploadResult(BaseModel):
    """Public URL of a stored product image, ready to attach to a product."""

    url: str
