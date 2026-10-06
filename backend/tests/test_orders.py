import hashlib
import hmac
import json

from sqlalchemy import select

from app.models.inventory import Inventory
from app.models.product import ProductVariant
from tests.helpers import create_category, create_product


def _sign(body: bytes) -> str:
    return hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()


def _webhook(client, event_type: str, payment_intent_id: str):
    body = json.dumps(
        {"type": event_type, "payment_intent_id": payment_intent_id}
    ).encode()
    return client.post(
        "/api/v1/payments/webhook",
        content=body,
        headers={"Stripe-Signature": _sign(body), "Content-Type": "application/json"},
    )


def _inventory(db, sku: str) -> Inventory:
    variant = db.scalar(select(ProductVariant).where(ProductVariant.sku == sku))
    return db.get(Inventory, variant.id)


def _checkout_one(client, admin_token, *, sku, price_cents, quantity):
    cat = create_category(client, admin_token, slug=f"cat-{sku}")
    product = create_product(
        client, admin_token, category_id=cat["id"], slug=f"prod-{sku}",
        name=f"Prod {sku}", sku=sku, price_cents=price_cents, quantity=quantity,
    )
    vid = product["variants"][0]["id"]
    cart = client.post("/api/v1/cart/items", json={"variant_id": vid, "quantity": 1}).json()
    r = client.post(
        "/api/v1/checkout",
        json={
            "cart_token": cart["token"],
            "email": "buyer@example.com",
            "shipping_address": {
                "full_name": "Buyer", "line1": "1 Main St", "city": "Town",
                "postal_code": "12345", "country": "US",
            },
            "delivery_option": "standard",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_checkout_creates_pending_order_and_reserves_stock(client, admin_token, db):
    res = _checkout_one(client, admin_token, sku="CK1", price_cents=40000, quantity=5)
    order = res["order"]
    assert order["status"] == "pending"
    assert order["payment_status"] == "unpaid"
    # subtotal 40000 < free-shipping threshold -> standard shipping applies.
    assert order["subtotal_cents"] == 40000
    assert order["shipping_cents"] == 4999
    assert order["total_cents"] == 44999
    assert res["provider"] == "fake"
    assert res["payment_client_secret"]

    inv = _inventory(db, "CK1")
    assert inv.quantity == 5 and inv.reserved == 1  # reserved, not yet sold


def test_successful_payment_marks_paid_and_sells_stock(client, admin_token, db):
    res = _checkout_one(client, admin_token, sku="CK2", price_cents=60000, quantity=5)
    pid = res["payment_intent_id"]

    r = _webhook(client, "payment.succeeded", pid)
    assert r.status_code == 200 and r.json()["handled"] is True

    order = client.get(
        f"/api/v1/orders/{res['order']['order_number']}",
        params={"email": "buyer@example.com"},
    ).json()
    assert order["status"] == "paid"
    assert order["payment_status"] == "paid"

    inv = _inventory(db, "CK2")
    assert inv.quantity == 4 and inv.reserved == 0  # one unit sold, reservation cleared


def test_webhook_is_idempotent(client, admin_token, db):
    res = _checkout_one(client, admin_token, sku="CK3", price_cents=60000, quantity=5)
    pid = res["payment_intent_id"]

    assert _webhook(client, "payment.succeeded", pid).status_code == 200
    second = _webhook(client, "payment.succeeded", pid)
    assert second.json().get("idempotent") is True

    inv = _inventory(db, "CK3")
    # Stock decremented exactly once despite the duplicate event.
    assert inv.quantity == 4 and inv.reserved == 0


def test_failed_payment_releases_stock_and_never_marks_paid(client, admin_token, db):
    res = _checkout_one(client, admin_token, sku="CK4", price_cents=60000, quantity=5)
    pid = res["payment_intent_id"]

    r = _webhook(client, "payment.failed", pid)
    assert r.status_code == 200

    order = client.get(
        f"/api/v1/orders/{res['order']['order_number']}",
        params={"email": "buyer@example.com"},
    ).json()
    assert order["status"] == "failed"
    assert order["payment_status"] == "failed"

    inv = _inventory(db, "CK4")
    assert inv.quantity == 5 and inv.reserved == 0  # reservation released, nothing sold


def test_invalid_webhook_signature_rejected(client, admin_token):
    res = _checkout_one(client, admin_token, sku="CK5", price_cents=60000, quantity=5)
    body = json.dumps(
        {"type": "payment.succeeded", "payment_intent_id": res["payment_intent_id"]}
    ).encode()
    r = client.post(
        "/api/v1/payments/webhook",
        content=body,
        headers={"Stripe-Signature": "deadbeef", "Content-Type": "application/json"},
    )
    assert r.status_code == 400


def test_checkout_empty_cart_rejected(client):
    r = client.post(
        "/api/v1/checkout",
        json={
            "cart_token": "nonexistent",
            "email": "x@example.com",
            "shipping_address": {
                "full_name": "X", "line1": "1 St", "city": "T",
                "postal_code": "1", "country": "US",
            },
        },
    )
    assert r.status_code == 400
