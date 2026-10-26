
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.lifecycle import InvalidTransition, assert_app_transition
from app.models import AuditLog, Loan, LoanApplication, new_id, now_iso
from app.money import yuan_to_cents
from app.pricing import equal_principal_and_interest_schedule, total_interest
from app.products import get_product, list_products
from app.repayment import apply_repayment
from app.store import STORE
from app.underwriting import run_underwriting


class ServiceError(Exception):
    def __init__(self, message: str, code: str = "VALIDATION"):
        self.message = message
        self.code = code
        super().__init__(message)


def list_catalog(category: str | None = None, risk_level: str | None = None) -> list[dict]:
    return [p.to_dict() for p in list_products(category, risk_level)]


def submit_application(user_id: int, body: dict[str, Any]) -> dict[str, Any]:
    product = get_product(body["product_id"])
    if not product:
        raise ServiceError("product not found", "NOT_FOUND")
    amount_cents = yuan_to_cents(body["amount"])
    term = int(body["term_months"])
    if term not in product.term_months_options:
        raise ServiceError("invalid term for product")
    app = LoanApplication(
        application_id=new_id("la"),
        user_id=user_id,
        customer_id=int(body.get("customer_id", 1)),
        product_id=product.product_id,
        amount_cents=amount_cents,
        term_months=term,
        purpose=str(body.get("purpose", "other")),
        status="submitted",
    )
    STORE.save_application(app)
    STORE.add_audit(
        AuditLog(
            id=new_id("au"),
            entity_type="application",
            entity_id=app.application_id,
            action="submit",
            actor_user_id=user_id,
            detail={"amount_cents": amount_cents},
        )
    )
    # auto underwriting
    assert_app_transition(app.status, "underwriting")
    app.status = "underwriting"
    app.updated_at = now_iso()
    ctx = {
        "age": body.get("age", 30),
        "monthly_income_cents": yuan_to_cents(body.get("monthly_income", "0")),
        "amount_cents": amount_cents,
        "delinquencies_24m": body.get("delinquencies_24m", 0),
        "inquiries_6m": body.get("inquiries_6m", 0),
        "months_employed": body.get("months_employed", 12),
        "employment_type": body.get("employment_type", "employed"),
        "min_amount_cents": product.min_amount_cents,
        "max_amount_cents": product.max_amount_cents,
        "industry": body.get("industry", "OTHER"),
        "city_tier": body.get("city_tier", "T2"),
        "purpose": body.get("purpose", "other"),
        "active_loans": STORE.user_active_loan_count(user_id),
        "exposure_cents": STORE.user_exposure_cents(user_id),
        "flags": body.get("flags", []),
        "device_score": body.get("device_score", 70),
        "shared_devices": body.get("shared_devices", 0),
        "shared_contacts": body.get("shared_contacts", 0),
    }
    result = run_underwriting(ctx)
    app.score = int(result["score"])
    app.decision_reason = result["reason"]
    app.meta["underwriting"] = result
    decision = result["decision"]
    if decision == "approved":
        assert_app_transition("underwriting", "approved")
        app.status = "approved"
    elif decision == "manual_review":
        assert_app_transition("underwriting", "manual_review")
        app.status = "manual_review"
    else:
        assert_app_transition("underwriting", "rejected")
        app.status = "rejected"
    app.updated_at = now_iso()
    STORE.save_application(app)
    STORE.add_audit(
        AuditLog(
            id=new_id("au"),
            entity_type="application",
            entity_id=app.application_id,
            action=f"uw_{app.status}",
            actor_user_id=0,
            detail={"score": app.score, "reason": app.decision_reason},
        )
    )
    # auto disburse if approved
    if app.status == "approved":
        return disburse(app.application_id, actor_user_id=0)
    return {"application": app.to_dict(), "underwriting": result}


def disburse(application_id: str, actor_user_id: int = 0) -> dict[str, Any]:
    app = STORE.get_application(application_id)
    if not app:
        raise ServiceError("application not found", "NOT_FOUND")
    if app.status != "approved":
        raise ServiceError(f"cannot disburse status={app.status}")
    product = get_product(app.product_id)
    if not product:
        raise ServiceError("product missing", "NOT_FOUND")
    schedule = equal_principal_and_interest_schedule(
        app.amount_cents, product.annual_rate_bps, app.term_months
    )
    loan = Loan(
        loan_id=new_id("ln"),
        application_id=app.application_id,
        user_id=app.user_id,
        customer_id=app.customer_id,
        product_id=app.product_id,
        principal_cents=app.amount_cents,
        outstanding_principal_cents=app.amount_cents,
        outstanding_interest_cents=total_interest(schedule),
        annual_rate_bps=product.annual_rate_bps,
        term_months=app.term_months,
        status="active",
        disbursed_at=now_iso(),
        installments=schedule,
    )
    assert_app_transition(app.status, "disbursed")
    app.status = "disbursed"
    app.updated_at = now_iso()
    STORE.save_application(app)
    STORE.save_loan(loan)
    STORE.add_audit(
        AuditLog(
            id=new_id("au"),
            entity_type="loan",
            entity_id=loan.loan_id,
            action="disburse",
            actor_user_id=actor_user_id,
            detail={"principal": app.amount_cents},
        )
    )
    return {"application": app.to_dict(), "loan": loan.to_dict()}


def manual_review(application_id: str, decision: str, reason: str, admin_uid: int) -> dict[str, Any]:
    app = STORE.get_application(application_id)
    if not app:
        raise ServiceError("application not found", "NOT_FOUND")
    if app.status != "manual_review":
        raise ServiceError("not in manual_review")
    if decision == "approved":
        assert_app_transition(app.status, "approved")
        app.status = "approved"
        app.decision_reason = reason or "manual approved"
        STORE.save_application(app)
        return disburse(application_id, actor_user_id=admin_uid)
    if decision == "rejected":
        assert_app_transition(app.status, "rejected")
        app.status = "rejected"
        app.decision_reason = reason or "manual rejected"
        app.updated_at = now_iso()
        STORE.save_application(app)
        return {"application": app.to_dict()}
    raise ServiceError("decision must be approved or rejected")


def repay(user_id: int, loan_id: str, amount: str, channel: str = "app") -> dict[str, Any]:
    loan = STORE.get_loan(loan_id)
    if not loan:
        raise ServiceError("loan not found", "NOT_FOUND")
    try:
        rep = apply_repayment(loan, user_id, yuan_to_cents(amount), channel)
    except (ValueError, PermissionError, InvalidTransition) as exc:
        raise ServiceError(str(exc)) from exc
    STORE.save_loan(loan)
    STORE.save_repayment(rep)
    STORE.add_audit(
        AuditLog(
            id=new_id("au"),
            entity_type="loan",
            entity_id=loan.loan_id,
            action="repay",
            actor_user_id=user_id,
            detail={"amount": amount, "repayment_id": rep.repayment_id},
        )
    )
    return {"repayment": rep.to_dict(), "loan": loan.to_dict(include_schedule=False)}


def mark_overdue_job() -> dict[str, Any]:
    """Scan installments vs today; mark overdue loans."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    changed = 0
    for loan in STORE.list_loans():
        if loan.status not in {"active", "overdue"}:
            continue
        overdue_days = 0
        for inst in loan.installments:
            if inst.status != "paid" and inst.due_date < today:
                inst.status = "overdue"
                # rough day count
                overdue_days = max(overdue_days, 1)
        if overdue_days and loan.status == "active":
            loan.status = "overdue"
            loan.overdue_days = overdue_days
            loan.updated_at = now_iso()
            STORE.save_loan(loan)
            changed += 1
        elif loan.status == "overdue":
            loan.overdue_days = max(loan.overdue_days, overdue_days)
            STORE.save_loan(loan)
    return {"marked": changed, "as_of": today}
