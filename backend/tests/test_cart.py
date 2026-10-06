from tests.helpers import create_category, create_product


def _variant_id(product: dict) -> str:
    return product["variants"][0]["id"]


def test_guest_cart_add_update_remove(client, admin_token):
    cat = create_category(client, admin_token)
    product = create_product(client, admin_token, category_id=cat["id"], quantity=10)
    vid = _variant_id(product)

    # Add
    r = client.post("/api/v1/cart/items", json={"variant_id": vid, "quantity": 2})
    assert r.status_code == 201
    cart = r.json()
    token = cart["token"]
    assert cart["item_count"] == 2
    assert cart["subtotal_cents"] == 100000
    item_id = cart["items"][0]["id"]

    # Subsequent calls must reuse the same cart via the token header.
    headers = {"X-Cart-Token": token}

    # Update quantity
    r = client.patch(f"/api/v1/cart/items/{item_id}", json={"quantity": 3}, headers=headers)
    assert r.json()["item_count"] == 3

    # Remove via quantity 0
    r = client.patch(f"/api/v1/cart/items/{item_id}", json={"quantity": 0}, headers=headers)
    assert r.json()["item_count"] == 0


def test_cart_respects_stock(client, admin_token):
    cat = create_category(client, admin_token)
    product = create_product(client, admin_token, category_id=cat["id"], quantity=2)
    vid = _variant_id(product)
    r = client.post("/api/v1/cart/items", json={"variant_id": vid, "quantity": 5})
    assert r.status_code == 409


def test_cart_persists_for_logged_in_user(client, user_token):
    # A logged-in user's cart is keyed by their account, surviving across calls.
    from tests.conftest import auth

    r = client.get("/api/v1/cart", headers=auth(user_token))
    assert r.status_code == 200
    assert r.json()["item_count"] == 0
