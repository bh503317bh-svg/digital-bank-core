
from __future__ import annotations

from app.services import submit_application
from app.store import STORE


def seed_demo() -> None:
    if STORE.list_applications():
        return
    # seed a few applications for user 1
    demos = [
        {
            "product_id": "LN-CON-01-R1",
            "amount": "5000",
            "term_months": 6,
            "purpose": "electronics",
            "monthly_income": "12000",
            "industry": "IT",
            "city_tier": "T1",
        },
        {
            "product_id": "LN-CON-02-R2",
            "amount": "8000",
            "term_months": 12,
            "purpose": "education",
            "monthly_income": "18000",
            "industry": "EDU",
            "city_tier": "T2",
        },
    ]
    for d in demos:
        try:
            submit_application(1, d)
        except Exception:
            pass
