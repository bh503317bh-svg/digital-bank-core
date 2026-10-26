
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP


def yuan_to_cents(amount: str | float | Decimal | int) -> int:
    d = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int(d * 100)


def cents_to_yuan(cents: int) -> str:
    return f"{Decimal(cents) / 100:.2f}"


def bps_to_monthly_rate(annual_bps: int) -> Decimal:
    return Decimal(annual_bps) / Decimal(120000)


def round_cents(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
