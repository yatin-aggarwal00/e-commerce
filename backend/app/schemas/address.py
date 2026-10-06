from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AddressBase(BaseModel):
    label: str = Field(default="Home", max_length=50)
    full_name: str = Field(max_length=255)
    phone: str = Field(default="", max_length=32)
    line1: str = Field(max_length=255)
    line2: str = Field(default="", max_length=255)
    city: str = Field(max_length=128)
    state: str = Field(default="", max_length=128)
    postal_code: str = Field(max_length=32)
    country: str = Field(default="US", max_length=2)
    is_default: bool = False


class AddressCreate(AddressBase):
    pass


class AddressUpdate(BaseModel):
    label: str | None = None
    full_name: str | None = None
    phone: str | None = None
    line1: str | None = None
    line2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None
    is_default: bool | None = None


class AddressOut(AddressBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
