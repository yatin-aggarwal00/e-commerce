"""Payment config endpoint + extra webhook safety assertions."""
from __future__ import annotations

from tests.test_orders import _checkout_one, _webhook


def test_payment_config_exposes_provider_and_publishable_key(client):
    r = client.get("/api/v1/payments/config")
    assert r.status_code == 200
    body = r.json()
    # The test suite runs with the fake provider and no publishable key.
    assert body["provider"] == "fake"
    assert body["publishable_key"] == ""


def test_late_failure_never_unpays_a_paid_order(client, admin_token):
    """A failed-event replay arriving after success must not flip the order."""
    res = _checkout_one(client, admin_token, sku="PAYLATE", price_cents=10000, quantity=3)
    intent = res["payment_intent_id"]
    assert _webhook(client, "payment.succeeded", intent).json()["handled"] is True

    late = _webhook(client, "payment.failed", intent)
    assert late.json().get("idempotent") is True

    order = client.get(
        f"/api/v1/orders/{res['order']['order_number']}",
        params={"email": res["order"]["email"]},
    ).json()
    assert order["payment_status"] == "paid"
    assert order["status"] == "paid"
