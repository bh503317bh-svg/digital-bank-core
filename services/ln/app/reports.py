
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from app.store import STORE


def portfolio_summary() -> dict[str, Any]:
    loans = STORE.list_loans()
    by_status = Counter(l.status for l in loans)
    outstanding = sum(l.outstanding_principal_cents for l in loans if l.status in {"active", "overdue"})
    overdue = sum(l.outstanding_principal_cents for l in loans if l.status == "overdue")
    by_product: dict[str, int] = defaultdict(int)
    for l in loans:
        by_product[l.product_id] += l.outstanding_principal_cents
    apps = STORE.list_applications()
    app_status = Counter(a.status for a in apps)
    reps = STORE.list_repayments()
    repaid = sum(r.amount_cents for r in reps)
    return {
        "loan_count": len(loans),
        "application_count": len(apps),
        "repayment_count": len(reps),
        "outstanding_principal": f"{outstanding / 100:.2f}",
        "overdue_principal": f"{overdue / 100:.2f}",
        "repaid_total": f"{repaid / 100:.2f}",
        "loans_by_status": dict(by_status),
        "applications_by_status": dict(app_status),
        "top_products": sorted(
            [{"product_id": k, "outstanding": f"{v / 100:.2f}"} for k, v in by_product.items()],
            key=lambda x: float(x["outstanding"]),
            reverse=True,
        )[:20],
    }


def user_loan_dashboard(user_id: int) -> dict[str, Any]:
    loans = STORE.list_loans(user_id=user_id)
    apps = STORE.list_applications(user_id=user_id)
    outstanding = sum(l.outstanding_principal_cents for l in loans if l.status in {"active", "overdue"})
    return {
        "user_id": user_id,
        "active_loans": sum(1 for l in loans if l.status in {"active", "overdue"}),
        "outstanding_principal": f"{outstanding / 100:.2f}",
        "applications": len(apps),
        "loans": [l.to_dict(include_schedule=False) for l in loans[:50]],
        "recent_applications": [a.to_dict() for a in apps[:20]],
    }
