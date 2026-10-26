
"""Amortization and interest pricing for consumer loans."""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import List

from app.models import Installment
from app.money import bps_to_monthly_rate, round_cents


def equal_principal_and_interest_schedule(
    principal_cents: int,
    annual_rate_bps: int,
    term_months: int,
    start: datetime | None = None,
) -> List[Installment]:
    """Standard EMI schedule (equal principal+interest)."""
    if term_months <= 0 or principal_cents <= 0:
        return []
    start = start or datetime.utcnow()
    r = bps_to_monthly_rate(annual_rate_bps)
    p = Decimal(principal_cents)
    if r == 0:
        base = principal_cents // term_months
        rem = principal_cents - base * term_months
        out: List[Installment] = []
        for i in range(1, term_months + 1):
            prin = base + (rem if i == term_months else 0)
            due = (start + timedelta(days=30 * i)).strftime("%Y-%m-%d")
            out.append(Installment(seq=i, due_date=due, principal_cents=prin, interest_cents=0))
        return out

    # EMI = P * r * (1+r)^n / ((1+r)^n - 1)
    one = Decimal(1)
    factor = (one + r) ** term_months
    emi = round_cents(p * r * factor / (factor - one))
    balance = p
    out = []
    for i in range(1, term_months + 1):
        interest = round_cents(balance * r)
        if i == term_months:
            principal = int(balance)
            # last installment absorbs rounding
            interest = max(0, emi - principal) if emi > principal else interest
            principal = int(balance)
        else:
            principal = min(int(balance), emi - interest)
            if principal < 0:
                principal = 0
        balance -= Decimal(principal)
        due = (start + timedelta(days=30 * i)).strftime("%Y-%m-%d")
        out.append(
            Installment(
                seq=i,
                due_date=due,
                principal_cents=principal,
                interest_cents=interest,
            )
        )
    return out


def equal_principal_schedule(
    principal_cents: int,
    annual_rate_bps: int,
    term_months: int,
    start: datetime | None = None,
) -> List[Installment]:
    """equal principal."""
    start = start or datetime.utcnow()
    r = bps_to_monthly_rate(annual_rate_bps)
    base = principal_cents // term_months
    rem = principal_cents - base * term_months
    balance = Decimal(principal_cents)
    out: List[Installment] = []
    for i in range(1, term_months + 1):
        principal = base + (rem if i == term_months else 0)
        interest = round_cents(balance * r)
        balance -= Decimal(principal)
        due = (start + timedelta(days=30 * i)).strftime("%Y-%m-%d")
        out.append(Installment(seq=i, due_date=due, principal_cents=principal, interest_cents=interest))
    return out


def total_interest(schedule: List[Installment]) -> int:
    return sum(i.interest_cents for i in schedule)


def apr_estimate(principal_cents: int, schedule: List[Installment], term_months: int) -> float:
    if principal_cents <= 0 or term_months <= 0:
        return 0.0
    interest = total_interest(schedule)
    return float(interest) / float(principal_cents) * (12.0 / term_months) * 100.0


def apply_late_fee(installment: Installment, overdue_days: int, bps_per_day: int) -> int:
    if overdue_days <= 0:
        return 0
    base = installment.remaining_cents
    fee = round_cents(Decimal(base) * Decimal(bps_per_day) * Decimal(overdue_days) / Decimal(10000))
    installment.fee_cents += fee
    return fee
