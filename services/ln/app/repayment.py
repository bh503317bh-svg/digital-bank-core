
from __future__ import annotations

from dataclasses import dataclass

from app.models import Installment, Loan, Repayment, new_id, now_iso
from app.lifecycle import InvalidTransition, assert_loan_transition


@dataclass
class Allocation:
    principal: int = 0
    interest: int = 0
    fee: int = 0


def allocate_waterfall(loan: Loan, amount_cents: int) -> Allocation:
    """Fee -> interest -> principal across installments in order."""
    remaining = amount_cents
    alloc = Allocation()
    for inst in sorted(loan.installments, key=lambda x: x.seq):
        if remaining <= 0:
            break
        if inst.status == "paid":
            continue
        # fee
        fee_due = inst.fee_cents - inst.paid_fee_cents
        take = min(remaining, fee_due)
        inst.paid_fee_cents += take
        alloc.fee += take
        remaining -= take
        # interest
        int_due = inst.interest_cents - inst.paid_interest_cents
        take = min(remaining, int_due)
        inst.paid_interest_cents += take
        alloc.interest += take
        remaining -= take
        # principal
        prin_due = inst.principal_cents - inst.paid_principal_cents
        take = min(remaining, prin_due)
        inst.paid_principal_cents += take
        alloc.principal += take
        remaining -= take
        if inst.remaining_cents <= 0:
            inst.status = "paid"
        elif inst.paid_principal_cents or inst.paid_interest_cents or inst.paid_fee_cents:
            inst.status = "partial"
    loan.outstanding_principal_cents = max(0, loan.outstanding_principal_cents - alloc.principal)
    loan.outstanding_interest_cents = max(0, loan.outstanding_interest_cents - alloc.interest)
    loan.updated_at = now_iso()
    if loan.outstanding_principal_cents == 0 and all(i.status == "paid" for i in loan.installments):
        if loan.status != "closed":
            assert_loan_transition(loan.status, "closed")
            loan.status = "closed"
    return alloc


def apply_repayment(loan: Loan, user_id: int, amount_cents: int, channel: str = "app") -> Repayment:
    if amount_cents <= 0:
        raise ValueError("amount must be positive")
    if loan.user_id != user_id:
        raise PermissionError("not your loan")
    if loan.status not in {"active", "overdue"}:
        raise InvalidTransition(f"cannot repay loan in status {loan.status}")
    alloc = allocate_waterfall(loan, amount_cents)
    rep = Repayment(
        repayment_id=new_id("rp"),
        loan_id=loan.loan_id,
        user_id=user_id,
        amount_cents=amount_cents,
        allocated_principal_cents=alloc.principal,
        allocated_interest_cents=alloc.interest,
        allocated_fee_cents=alloc.fee,
        channel=channel,
        remark=f"waterfall p={alloc.principal} i={alloc.interest} f={alloc.fee}",
    )
    return rep
