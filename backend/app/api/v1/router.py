from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routes import (
    addresses,
    admin,
    auth,
    cart,
    catalog,
    health,
    orders,
    payments,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(catalog.router)
api_router.include_router(cart.router)
api_router.include_router(addresses.router)
api_router.include_router(orders.router)
api_router.include_router(payments.router)
api_router.include_router(admin.router)
