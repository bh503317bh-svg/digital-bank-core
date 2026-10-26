from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4


def now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


@dataclass
class LoanProduct:
    product_id: str
    name: str
    category: str  # consumer / business / credit_card_cash
    min_amount_cents: int
    max_amount_cents: int
    term_months_options: list[int]
    annual_rate_bps: int  # basis points, 600 = 6.00%
    risk_level: str
    description: str
    active: bool = True

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["min_amount"] = f"{self.min_amount_cents / 100:.2f}"
        d["max_amount"] = f"{self.max_amount_cents / 100:.2f}"
        d["annual_rate"] = f"{self.annual_rate_bps / 100:.2f}%"
        return d


@dataclass
class Installment:
    seq: int
    due_date: str
    principal_cents: int
    interest_cents: int
    fee_cents: int = 0
    paid_principal_cents: int = 0
    paid_interest_cents: int = 0
    paid_fee_cents: int = 0
    status: str = "pending"  # pending / partial / paid / overdue

    @property
    def total_due_cents(self) -> int:
        return self.principal_cents + self.interest_cents + self.fee_cents

    @property
    def remaining_cents(self) -> int:
        return (
            self.principal_cents
            - self.paid_principal_cents
            + self.interest_cents
            - self.paid_interest_cents
            + self.fee_cents
            - self.paid_fee_cents
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "due_date": self.due_date,
            "principal": f"{self.principal_cents / 100:.2f}",
            "interest": f"{self.interest_cents / 100:.2f}",
            "fee": f"{self.fee_cents / 100:.2f}",
            "paid_principal": f"{self.paid_principal_cents / 100:.2f}",
            "paid_interest": f"{self.paid_interest_cents / 100:.2f}",
            "paid_fee": f"{self.paid_fee_cents / 100:.2f}",
            "remaining": f"{self.remaining_cents / 100:.2f}",
            "status": self.status,
        }


@dataclass
class LoanApplication:
    application_id: str
    user_id: int
    customer_id: int
    product_id: str
    amount_cents: int
    term_months: int
    purpose: str
    status: str  # draft / submitted / underwriting / approved / rejected / disbursed / cancelled
    score: int = 0
    decision_reason: str = ""
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "application_id": self.application_id,
            "user_id": self.user_id,
            "customer_id": self.customer_id,
            "product_id": self.product_id,
            "amount": f"{self.amount_cents / 100:.2f}",
            "amount_cents": self.amount_cents,
            "term_months": self.term_months,
            "purpose": self.purpose,
            "status": self.status,
            "score": self.score,
            "decision_reason": self.decision_reason,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "meta": self.meta,
        }


@dataclass
class Loan:
    loan_id: str
    application_id: str
    user_id: int
    customer_id: int
    product_id: str
    principal_cents: int
    outstanding_principal_cents: int
    outstanding_interest_cents: int
    annual_rate_bps: int
    term_months: int
    status: str  # active / overdue / closed / written_off
    disbursed_at: str
    installments: list[Installment] = field(default_factory=list)
    overdue_days: int = 0
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self, include_schedule: bool = True) -> dict[str, Any]:
        d = {
            "loan_id": self.loan_id,
            "application_id": self.application_id,
            "user_id": self.user_id,
            "customer_id": self.customer_id,
            "product_id": self.product_id,
            "principal": f"{self.principal_cents / 100:.2f}",
            "outstanding_principal": f"{self.outstanding_principal_cents / 100:.2f}",
            "outstanding_interest": f"{self.outstanding_interest_cents / 100:.2f}",
            "annual_rate": f"{self.annual_rate_bps / 100:.2f}%",
            "term_months": self.term_months,
            "status": self.status,
            "disbursed_at": self.disbursed_at,
            "overdue_days": self.overdue_days,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if include_schedule:
            d["installments"] = [i.to_dict() for i in self.installments]
        return d


@dataclass
class Repayment:
    repayment_id: str
    loan_id: str
    user_id: int
    amount_cents: int
    allocated_principal_cents: int
    allocated_interest_cents: int
    allocated_fee_cents: int
    channel: str
    created_at: str = field(default_factory=now_iso)
    remark: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "repayment_id": self.repayment_id,
            "loan_id": self.loan_id,
            "user_id": self.user_id,
            "amount": f"{self.amount_cents / 100:.2f}",
            "allocated_principal": f"{self.allocated_principal_cents / 100:.2f}",
            "allocated_interest": f"{self.allocated_interest_cents / 100:.2f}",
            "allocated_fee": f"{self.allocated_fee_cents / 100:.2f}",
            "channel": self.channel,
            "created_at": self.created_at,
            "remark": self.remark,
        }


@dataclass
class AuditLog:
    id: str
    entity_type: str
    entity_id: str
    action: str
    actor_user_id: int
    detail: dict[str, Any]
    created_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:16]}"
