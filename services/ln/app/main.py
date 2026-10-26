
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, Query

from bank_common import ErrorCode, fail, ok, verify_pay_password_sync

from app.auth import is_error, require_admin, require_user
from app.config import settings
from app.reports import portfolio_summary, user_loan_dashboard
from app.schemas import ApplyReq, RepayReq, ReviewReq
from app.seed import seed_demo
from app import services
from app.store import STORE


@asynccontextmanager
async def lifespan(_: FastAPI):
    seed_demo()
    yield


app = FastAPI(title="bank-ln", lifespan=lifespan)


@app.get("/health")
def health():
    return ok({"service": "bank-ln", "status": "up", "mode": "full", "products": len(STORE.products)})


@app.get("/api/ln/ping")
def ping():
    return ok({"domain": "ln", "message": "loan domain ready"})


@app.get("/api/ln/products")
def products(
    category: str | None = None,
    risk_level: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
):
    rows = services.list_catalog(category, risk_level)[:limit]
    return ok({"items": rows, "total": len(rows)})


@app.post("/api/ln/applications")
def create_application(body: ApplyReq, authorization: str | None = Header(default=None)):
    payload = require_user(authorization)
    if is_error(payload):
        return payload
    pay = verify_pay_password_sync(authorization, body.pay_password, us_url=settings.us_base_url)
    if pay.get("code") != 0:
        return pay
    try:
        data = services.submit_application(int(payload["uid"]), body.model_dump())
    except services.ServiceError as exc:
        code = ErrorCode.NOT_FOUND if exc.code == "NOT_FOUND" else ErrorCode.VALIDATION
        return fail(code, exc.message)
    return ok(data)


@app.get("/api/ln/applications")
def my_applications(authorization: str | None = Header(default=None), status: str | None = None):
    payload = require_user(authorization)
    if is_error(payload):
        return payload
    uid = None if payload.get("role") == "admin" else int(payload["uid"])
    rows = STORE.list_applications(user_id=uid, status=status)
    return ok([a.to_dict() for a in rows])


@app.get("/api/ln/loans")
def my_loans(authorization: str | None = Header(default=None), status: str | None = None):
    payload = require_user(authorization)
    if is_error(payload):
        return payload
    uid = None if payload.get("role") == "admin" else int(payload["uid"])
    rows = STORE.list_loans(user_id=uid, status=status)
    return ok([l.to_dict(include_schedule=False) for l in rows])


@app.get("/api/ln/loans/{loan_id}")
def loan_detail(loan_id: str, authorization: str | None = Header(default=None)):
    payload = require_user(authorization)
    if is_error(payload):
        return payload
    loan = STORE.get_loan(loan_id)
    if not loan:
        return fail(ErrorCode.NOT_FOUND, "loan not found")
    if payload.get("role") != "admin" and loan.user_id != int(payload["uid"]):
        return fail(ErrorCode.FORBIDDEN, "not your loan")
    return ok(loan.to_dict(include_schedule=True))


@app.post("/api/ln/repayments")
def repay(body: RepayReq, authorization: str | None = Header(default=None)):
    payload = require_user(authorization)
    if is_error(payload):
        return payload
    pay = verify_pay_password_sync(authorization, body.pay_password, us_url=settings.us_base_url)
    if pay.get("code") != 0:
        return pay
    try:
        data = services.repay(int(payload["uid"]), body.loan_id, body.amount, body.channel)
    except services.ServiceError as exc:
        code = ErrorCode.NOT_FOUND if exc.code == "NOT_FOUND" else ErrorCode.VALIDATION
        return fail(code, exc.message)
    return ok(data)


@app.get("/api/ln/repayments")
def list_repayments(authorization: str | None = Header(default=None), loan_id: str | None = None):
    payload = require_user(authorization)
    if is_error(payload):
        return payload
    uid = None if payload.get("role") == "admin" else int(payload["uid"])
    rows = STORE.list_repayments(loan_id=loan_id, user_id=uid)
    return ok([r.to_dict() for r in rows])


@app.get("/api/ln/me/dashboard")
def dashboard(authorization: str | None = Header(default=None)):
    payload = require_user(authorization)
    if is_error(payload):
        return payload
    return ok(user_loan_dashboard(int(payload["uid"])))


@app.get("/api/ln/admin/portfolio")
def admin_portfolio(authorization: str | None = Header(default=None)):
    payload = require_admin(authorization)
    if is_error(payload):
        return payload
    return ok(portfolio_summary())


@app.post("/api/ln/admin/review")
def admin_review(body: ReviewReq, authorization: str | None = Header(default=None)):
    payload = require_admin(authorization)
    if is_error(payload):
        return payload
    try:
        data = services.manual_review(body.application_id, body.decision, body.reason, int(payload["uid"]))
    except services.ServiceError as exc:
        return fail(ErrorCode.VALIDATION, exc.message)
    return ok(data)


@app.post("/api/ln/admin/jobs/mark-overdue")
def job_overdue(authorization: str | None = Header(default=None)):
    payload = require_admin(authorization)
    if is_error(payload):
        return payload
    return ok(services.mark_overdue_job())


@app.get("/api/ln/admin/audits")
def audits(authorization: str | None = Header(default=None), limit: int = 100):
    payload = require_admin(authorization)
    if is_error(payload):
        return payload
    rows = STORE.audits[-limit:]
    rows = list(reversed(rows))
    return ok([a.to_dict() for a in rows])
