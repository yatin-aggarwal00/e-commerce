from tests.conftest import auth
from tests.helpers import create_category, create_product


def test_non_admin_cannot_access_admin(client, user_token):
    r = client.get("/api/v1/admin/stats", headers=auth(user_token))
    assert r.status_code == 403


def test_admin_requires_auth(client):
    assert client.get("/api/v1/admin/stats").status_code == 401


def test_admin_product_crud_and_inventory(client, admin_token):
    cat = create_category(client, admin_token)
    product = create_product(client, admin_token, category_id=cat["id"])
    pid = product["id"]
    vid = product["variants"][0]["id"]

    # Update
    r = client.patch(
        f"/api/v1/admin/products/{pid}",
        headers=auth(admin_token),
        json={"name": "Renamed Sofa"},
    )
    assert r.status_code == 200 and r.json()["name"] == "Renamed Sofa"

    # Set inventory
    r = client.put(
        f"/api/v1/admin/variants/{vid}/inventory",
        headers=auth(admin_token),
        json={"quantity": 99},
    )
    assert r.status_code == 200 and r.json()["quantity"] == 99

    # Deactivate (soft delete) hides it from the storefront.
    r = client.delete(f"/api/v1/admin/products/{pid}", headers=auth(admin_token))
    assert r.status_code == 200
    assert client.get("/api/v1/catalog/products").json()["total"] == 0
    assert client.get(f"/api/v1/catalog/products/{product['slug']}").status_code == 404


def test_admin_stats(client, admin_token):
    cat = create_category(client, admin_token)
    create_product(client, admin_token, category_id=cat["id"])
    r = client.get("/api/v1/admin/stats", headers=auth(admin_token))
    assert r.status_code == 200
    body = r.json()
    assert body["products"] == 1
    assert body["active_products"] == 1


def test_admin_order_status_update(client, admin_token):
    # Build and pay an order, then advance its fulfilment status.
    from tests.test_orders import _checkout_one, _webhook

    res = _checkout_one(client, admin_token, sku="ADM1", price_cents=60000, quantity=5)
    _webhook(client, "payment.succeeded", res["payment_intent_id"])
    r = client.patch(
        f"/api/v1/admin/orders/{res['order']['order_number']}/status",
        headers=auth(admin_token),
        json={"status": "shipped"},
    )
    assert r.status_code == 200 and r.json()["status"] == "shipped"

    # Invalid status is rejected.
    bad = client.patch(
        f"/api/v1/admin/orders/{res['order']['order_number']}/status",
        headers=auth(admin_token),
        json={"status": "teleported"},
    )
    assert bad.status_code == 422
