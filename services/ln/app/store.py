
from __future__ import annotations

import threading
from typing import Optional

from app.models import AuditLog, Loan, LoanApplication, Repayment
from app.products import PRODUCTS


class LoanStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.applications: dict[str, LoanApplication] = {}
        self.loans: dict[str, Loan] = {}
        self.repayments: dict[str, Repayment] = {}
        self.audits: list[AuditLog] = []
        self.products = {p.product_id: p for p in PRODUCTS}

    def add_audit(self, log: AuditLog) -> None:
        with self._lock:
            self.audits.append(log)
            if len(self.audits) > 5000:
                self.audits = self.audits[-4000:]

    def save_application(self, app: LoanApplication) -> None:
        with self._lock:
            self.applications[app.application_id] = app

    def get_application(self, application_id: str) -> Optional[LoanApplication]:
        with self._lock:
            return self.applications.get(application_id)

    def list_applications(self, user_id: int | None = None, status: str | None = None) -> list[LoanApplication]:
        with self._lock:
            rows = list(self.applications.values())
        if user_id is not None:
            rows = [r for r in rows if r.user_id == user_id]
        if status:
            rows = [r for r in rows if r.status == status]
        rows.sort(key=lambda x: x.created_at, reverse=True)
        return rows

    def save_loan(self, loan: Loan) -> None:
        with self._lock:
            self.loans[loan.loan_id] = loan

    def get_loan(self, loan_id: str) -> Optional[Loan]:
        with self._lock:
            return self.loans.get(loan_id)

    def list_loans(self, user_id: int | None = None, status: str | None = None) -> list[Loan]:
        with self._lock:
            rows = list(self.loans.values())
        if user_id is not None:
            rows = [r for r in rows if r.user_id == user_id]
        if status:
            rows = [r for r in rows if r.status == status]
        rows.sort(key=lambda x: x.created_at, reverse=True)
        return rows

    def save_repayment(self, rep: Repayment) -> None:
        with self._lock:
            self.repayments[rep.repayment_id] = rep

    def list_repayments(self, loan_id: str | None = None, user_id: int | None = None) -> list[Repayment]:
        with self._lock:
            rows = list(self.repayments.values())
        if loan_id:
            rows = [r for r in rows if r.loan_id == loan_id]
        if user_id is not None:
            rows = [r for r in rows if r.user_id == user_id]
        rows.sort(key=lambda x: x.created_at, reverse=True)
        return rows

    def user_exposure_cents(self, user_id: int) -> int:
        with self._lock:
            return sum(
                l.outstanding_principal_cents
                for l in self.loans.values()
                if l.user_id == user_id and l.status in {"active", "overdue"}
            )

    def user_active_loan_count(self, user_id: int) -> int:
        with self._lock:
            return sum(1 for l in self.loans.values() if l.user_id == user_id and l.status in {"active", "overdue"})


STORE = LoanStore()
