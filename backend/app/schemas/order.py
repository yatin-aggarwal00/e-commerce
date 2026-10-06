from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.address import AddressBase


class CheckoutRequest(BaseModel):
    """Create an order from the caller's cart and start a payment."""

    cart_token: str
    email: EmailStr
    # Either reference a saved address id (authenticated) or supply one inline.
    address_id: str | None = None
    shipping_address: AddressBase | None = None
    delivery_option: str = Field(default="standard")


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    product_name: str
    variant_name: str
    sku: str
    unit_price_cents: int
    quantity: int
    line_total_cents: int


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    order_number: str
    email: EmailStr
    status: str
    payment_status: str
    subtotal_cents: int
    shipping_cents: int
    total_cents: int
    currency: str
    delivery_option: str
    created_at: datetime
    items: list[OrderItemOut] = []


class CheckoutResponse(BaseModel):
    order: OrderOut
    # Opaque client secret / token the frontend hands to the payment element.
    payment_client_secret: str
    payment_intent_id: str
    provider: str


class OrderStatusUpdate(BaseModel):
    status: str
