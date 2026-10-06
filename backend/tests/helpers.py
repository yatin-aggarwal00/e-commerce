"""Shared test helpers for building catalog data via the admin API."""
from __future__ import annotations

from tests.conftest import auth


def create_category(client, admin_token, slug="sofas", name="Sofas") -> dict:
    r = client.post(
        "/api/v1/admin/categories",
        headers=auth(admin_token),
        json={"name": name, "slug": slug, "description": ""},
    )
    assert r.status_code == 201, r.text
    return r.json()


def create_product(
    client,
    admin_token,
    *,
    category_id: str,
    slug="test-sofa",
    name="Test Sofa",
    price_cents=50000,
    quantity=10,
    sku="TEST-SKU-1",
    color="grey",
    room_type="Living Room",
    material="Fabric",
) -> dict:
    r = client.post(
        "/api/v1/admin/products",
        headers=auth(admin_token),
        json={
            "name": name,
            "slug": slug,
            "description": "A nice test sofa",
            "category_id": category_id,
            "room_type": room_type,
            "material": material,
            "is_active": True,
            "images": [{"url": "https://example.com/sofa.jpg", "alt": name, "position": 0}],
            "variants": [
                {
                    "sku": sku,
                    "name": "Default",
                    "color": color,
                    "size": "Standard",
                    "price_cents": price_cents,
                    "currency": "usd",
                    "dimensions": "200 x 90 x 85 cm",
                    "weight_kg": 40,
                    "quantity": quantity,
                }
            ],
        },
    )
    assert r.status_code == 201, r.text
    return r.json()
