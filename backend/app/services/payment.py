"""Pluggable payment provider abstraction.

V1 ships two providers:

* ``stripe``  - real Stripe PaymentIntents (sandbox keys). Card data never
  touches our servers; the frontend uses Stripe's hosted Payment Element, so
  PCI scope is minimised.
* ``fake``    - a deterministic, network-free provider used by local dev and
  the test suite. It mimics the client-secret + webhook-event contract.

Swap ``PAYMENT_PROVIDER`` in the environment to switch. A Razorpay provider can
be added by implementing the same ``PaymentProvider`` interface.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any, Protocol

from app.core.config import settings


@dataclass
class PaymentIntent:
    id: str
    client_secret: str
    amount_cents: int
    currency: str
    status: str


@dataclass
class WebhookEvent:
    type: str              # e.g. "payment.succeeded" / "payment.failed"
    payment_intent_id: str
    raw: dict[str, Any]


class PaymentError(Exception):
    """Raised when a payment operation or webhook verification fails."""


class PaymentProvider(Protocol):
    name: str

    def create_payment_intent(
        self, amount_cents: int, currency: str, metadata: dict[str, Any]
    ) -> PaymentIntent: ...

    def verify_and_parse_webhook(self, payload: bytes, signature: str) -> WebhookEvent: ...


# --------------------------------------------------------------------------
# Fake provider (default for tests / offline dev)
# --------------------------------------------------------------------------
class FakePaymentProvider:
    name = "fake"

    def create_payment_intent(self, amount_cents, currency, metadata):
        # Non-cryptographic: just a stable fake id derived from the metadata.
        pid = "pi_fake_" + hashlib.sha1(
            json.dumps(metadata, sort_keys=True).encode(), usedforsecurity=False
        ).hexdigest()[:20]
        return PaymentIntent(
            id=pid,
            client_secret=f"{pid}_secret",
            amount_cents=amount_cents,
            currency=currency,
            status="requires_payment_method",
        )

    def verify_and_parse_webhook(self, payload, signature):
        # The fake provider "signs" with a plain HMAC of the body so tests can
        # exercise the real verification path.
        expected = hmac.new(
            settings.STRIPE_WEBHOOK_SECRET.encode() or b"test-secret",
            payload,
            hashlib.sha256,
        ).hexdigest()
        if signature and not hmac.compare_digest(signature, expected):
            raise PaymentError("invalid signature")
        data = json.loads(payload.decode() or "{}")
        return WebhookEvent(
            type=data.get("type", "payment.succeeded"),
            payment_intent_id=data.get("payment_intent_id", ""),
            raw=data,
        )


# --------------------------------------------------------------------------
# Stripe provider
# --------------------------------------------------------------------------
class StripePaymentProvider:
    name = "stripe"

    def __init__(self) -> None:
        import stripe  # imported lazily so the test env need not install keys

        self._stripe = stripe
        self._stripe.api_key = settings.STRIPE_SECRET_KEY

    def create_payment_intent(self, amount_cents, currency, metadata):
        intent = self._stripe.PaymentIntent.create(
            amount=amount_cents,
            currency=currency,
            metadata=metadata,
            automatic_payment_methods={"enabled": True},
        )
        return PaymentIntent(
            id=intent.id,
            client_secret=intent.client_secret,
            amount_cents=amount_cents,
            currency=currency,
            status=intent.status,
        )

    def verify_and_parse_webhook(self, payload, signature):
        try:
            event = self._stripe.Webhook.construct_event(
                payload, signature, settings.STRIPE_WEBHOOK_SECRET
            )
        except Exception as exc:  # stripe.error.SignatureVerificationError etc.
            raise PaymentError(str(exc)) from exc

        type_map = {
            "payment_intent.succeeded": "payment.succeeded",
            "payment_intent.payment_failed": "payment.failed",
            "payment_intent.canceled": "payment.failed",
        }
        obj = event["data"]["object"]
        return WebhookEvent(
            type=type_map.get(event["type"], event["type"]),
            payment_intent_id=obj.get("id", ""),
            raw=dict(event),
        )


def get_payment_provider() -> PaymentProvider:
    provider = settings.PAYMENT_PROVIDER.lower()
    if provider == "stripe" and settings.STRIPE_SECRET_KEY:
        return StripePaymentProvider()
    # Fall back to the fake provider when Stripe isn't configured so local dev
    # and CI work out of the box.
    return FakePaymentProvider()
