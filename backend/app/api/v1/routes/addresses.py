from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models.address import Address
from app.schemas.address import AddressCreate, AddressOut, AddressUpdate
from app.schemas.common import Message

router = APIRouter(prefix="/addresses", tags=["addresses"])


def _clear_other_defaults(db: DbSession, user_id: str, keep_id: str | None) -> None:
    others = db.scalars(
        select(Address).where(Address.user_id == user_id, Address.is_default.is_(True))
    ).all()
    for addr in others:
        if addr.id != keep_id:
            addr.is_default = False


@router.get("", response_model=list[AddressOut])
def list_addresses(db: DbSession, user: CurrentUser) -> list[Address]:
    return list(
        db.scalars(
            select(Address)
            .where(Address.user_id == user.id)
            .order_by(Address.is_default.desc(), Address.created_at.desc())
        ).all()
    )


@router.post("", response_model=AddressOut, status_code=status.HTTP_201_CREATED)
def create_address(payload: AddressCreate, db: DbSession, user: CurrentUser) -> Address:
    addr = Address(user_id=user.id, **payload.model_dump())
    db.add(addr)
    db.flush()
    if addr.is_default:
        _clear_other_defaults(db, user.id, addr.id)
    db.commit()
    db.refresh(addr)
    return addr


@router.patch("/{address_id}", response_model=AddressOut)
def update_address(
    address_id: str, payload: AddressUpdate, db: DbSession, user: CurrentUser
) -> Address:
    addr = db.get(Address, address_id)
    if addr is None or addr.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Address not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(addr, field, value)
    if addr.is_default:
        _clear_other_defaults(db, user.id, addr.id)
    db.commit()
    db.refresh(addr)
    return addr


@router.delete("/{address_id}", response_model=Message)
def delete_address(address_id: str, db: DbSession, user: CurrentUser) -> Message:
    addr = db.get(Address, address_id)
    if addr is None or addr.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Address not found")
    db.delete(addr)
    db.commit()
    return Message(detail="Address deleted")
