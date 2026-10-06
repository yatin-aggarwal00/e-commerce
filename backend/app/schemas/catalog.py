from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


# --- Categories ---------------------------------------------------------
class CategoryBase(BaseModel):
    name: str = Field(max_length=128)
    slug: str = Field(max_length=160)
    description: str = ""
    image_url: str = ""
    parent_id: str | None = None


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    description: str | None = None
    image_url: str | None = None
    parent_id: str | None = None


class CategoryOut(CategoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: str


# --- Variants -----------------------------------------------------------
class VariantBase(BaseModel):
    sku: str = Field(max_length=64)
    name: str = Field(default="Default", max_length=255)
    color: str = ""
    size: str = ""
    price_cents: int = Field(ge=0)
    currency: str = "usd"
    dimensions: str = ""
    weight_kg: int = 0


class VariantCreate(VariantBase):
    quantity: int = Field(default=0, ge=0)


class VariantOut(VariantBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    in_stock: bool = False
    available: int = 0


# --- Images -------------------------------------------------------------
class ImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    url: str
    alt: str
    position: int


class ImageCreate(BaseModel):
    url: str = Field(max_length=1024)
    alt: str = ""
    position: int = 0


# --- Products -----------------------------------------------------------
class ProductBase(BaseModel):
    name: str = Field(max_length=255)
    slug: str = Field(max_length=280)
    description: str = ""
    category_id: str
    room_type: str = ""
    material: str = ""
    is_active: bool = True


class ProductCreate(ProductBase):
    images: list[ImageCreate] = []
    variants: list[VariantCreate] = []


class ProductUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    description: str | None = None
    category_id: str | None = None
    room_type: str | None = None
    material: str | None = None
    is_active: bool | None = None


class ProductListItem(BaseModel):
    """Compact shape for listing/search grids."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    room_type: str
    material: str
    category_id: str
    thumbnail: str | None = None
    min_price_cents: int | None = None
    currency: str = "usd"
    in_stock: bool = False


class ProductDetail(ProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    category: CategoryOut | None = None
    images: list[ImageOut] = []
    variants: list[VariantOut] = []


class AutocompleteItem(BaseModel):
    name: str
    slug: str
