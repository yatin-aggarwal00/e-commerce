"""Order pricing rules (shipping, totals). Centralised so checkout and tests
agree on the numbers."""
from __future__ import annotations

# Flat-rate shipping by delivery option, in minor units. Free standard shipping
# over the threshold.
SHIPPING_RATES_CENTS = {
    "standard": 4999,
    "express": 9999,
    "white_glove": 19999,
}
FREE_SHIPPING_THRESHOLD_CENTS = 50000  # $500


def shipping_cents(subtotal_cents: int, delivery_option: str) -> int:
    base = SHIPPING_RATES_CENTS.get(delivery_option, SHIPPING_RATES_CENTS["standard"])
    if delivery_option == "standard" and subtotal_cents >= FREE_SHIPPING_THRESHOLD_CENTS:
        return 0
    return base


def order_total_cents(subtotal_cents: int, delivery_option: str) -> tuple[int, int]:
    """Return ``(shipping, total)`` for a given subtotal + delivery option."""
    ship = shipping_cents(subtotal_cents, delivery_option)
    return ship, subtotal_cents + ship
