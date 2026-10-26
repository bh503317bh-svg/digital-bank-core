
from __future__ import annotations

from typing import Any

from app import underwriting_rules as R
from app.config import settings


def run_underwriting(ctx: dict[str, Any]) -> dict[str, Any]:
    """Run full rule stack; return score + decision."""
    results = [
        R.rule_age(int(ctx.get("age", 30))),
        R.rule_income(int(ctx.get("monthly_income_cents", 0)), int(ctx.get("amount_cents", 0))),
        R.rule_credit_history(int(ctx.get("delinquencies_24m", 0)), int(ctx.get("inquiries_6m", 0))),
        R.rule_employment(int(ctx.get("months_employed", 12)), str(ctx.get("employment_type", "employed"))),
        R.rule_amount_vs_product(
            int(ctx.get("amount_cents", 0)),
            int(ctx.get("min_amount_cents", 0)),
            int(ctx.get("max_amount_cents", 10**12)),
        ),
        R.rule_industry(str(ctx.get("industry", "OTHER"))),
        R.rule_city(str(ctx.get("city_tier", "T2"))),
        R.rule_purpose(str(ctx.get("purpose", "other"))),
        R.rule_existing_exposure(
            int(ctx.get("active_loans", 0)),
            int(ctx.get("exposure_cents", 0)),
            settings.max_active_loans_per_user,
            settings.max_exposure_cents,
        ),
        R.rule_blacklist(list(ctx.get("flags", []))),
        R.rule_device_risk(int(ctx.get("device_score", 70))),
        R.rule_relation_graph(int(ctx.get("shared_devices", 0)), int(ctx.get("shared_contacts", 0))),
    ]
    hard_fails = [r for r in results if not r.passed]
    score = 600 + sum(r.score_delta for r in results)
    score = max(300, min(900, score))
    if hard_fails:
        decision = "rejected"
        reason = "; ".join(f"{r.code}:{r.message}" for r in hard_fails[:3])
    elif score >= 650:
        decision = "approved"
        reason = "auto-approved"
    elif score >= 580:
        decision = "manual_review"
        reason = "borderline score"
    else:
        decision = "rejected"
        reason = "score too low"
    return {
        "score": score,
        "decision": decision,
        "reason": reason,
        "rules": [
            {
                "code": r.code,
                "passed": r.passed,
                "score_delta": r.score_delta,
                "message": r.message,
            }
            for r in results
        ],
    }
