from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

import httpx
from fastapi import Depends, FastAPI, Header
from pydantic import BaseModel, Field
from sqlalchemy import case
from sqlalchemy.orm import Session

from bank_common import AccountingEvent, ErrorCode, decode_token, fail, ok, verify_pay_password_sync

from app.config import settings
from app.db import Base, SessionLocal, engine, get_db
from app.models import Account, Ledger, Txn
from app.mq import publish_accounting_event


def yuan_to_cents(amount: str | float | Decimal) -> int:
    d = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int(d * 100)


def cents_to_yuan(cents: int) -> str:
    return f"{Decimal(cents) / 100:.2f}"


def require_pay(authorization: str | None, pay_password: str | None) -> dict | None:
    """Return error dict if pay password invalid; else None."""
    result = verify_pay_password_sync(
        authorization, pay_password, us_url=settings.us_base_url
    )
    if result.get("code") != 0:
        return result
    return None


class OpenAccountReq(BaseModel):
    customer_id: int | None = None


class AmountReq(BaseModel):
    account_no: str
    amount: str = Field(description="yuan, e.g. 100.00")
    pay_password: str = Field(min_length=4, max_length=12)


class TransferReq(BaseModel):
    from_account_no: str
    to_account_no: str
    amount: str
    pay_password: str = Field(min_length=4, max_length=12)
    # International / wire remittance fields
    beneficiary_name: str = ""
    swift_code: str = ""
    bank_name: str = ""
    bank_country: str = "US"
    bank_address: str = ""
    remittance_info: str = ""
    transfer_type: str = "internal"  # internal | wire


class WealthBuyReq(BaseModel):
    account_no: str
    amount: str = Field(description="yuan, e.g. 100.00")
    product_id: str
    product_name: str = ""
    pay_password: str = Field(min_length=4, max_length=12)


def auth_payload(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        return fail(ErrorCode.UNAUTHORIZED, "missing token")
    token = authorization.split(" ", 1)[1]
    try:
        return decode_token(token, secret=settings.jwt_secret)
    except Exception:
        return fail(ErrorCode.UNAUTHORIZED, "invalid token")


def account_out(a: Account) -> dict:
    return {
        "id": a.id,
        "account_no": a.account_no,
        "customer_id": a.customer_id,
        "user_id": a.user_id,
        "balance_cents": a.balance_cents,
        "balance": cents_to_yuan(a.balance_cents),
        "status": a.status,
        "currency": a.currency,
    }


# Demo balances in minor units. JPY is still stored with 2 decimals.
EXTRA_CCY = (
    ("EUR", 326080, "11"),
    ("HKD", 1850000, "12"),
    ("JPY", 18640000, "13"),
    ("SGD", 428050, "14"),
    ("CNY", 1280000, "15"),
)


def seed_account() -> None:
    db = SessionLocal()
    try:
        seeds = [
            ("6222000000000001", 1, 1, 100000, "USD"),
            ("6222000000000002", 1, 1, 50000, "USD"),
        ]
        for account_no, customer_id, user_id, balance, currency in seeds:
            if not db.query(Account).filter(Account.account_no == account_no).first():
                db.add(
                    Account(
                        account_no=account_no,
                        customer_id=customer_id,
                        user_id=user_id,
                        balance_cents=balance,
                        status="active",
                        currency=currency,
                    )
                )
        db.flush()
        owners = db.query(Account.user_id, Account.customer_id).all()
        seen: set[int] = set()
        for user_id, customer_id in owners:
            if user_id in seen:
                continue
            seen.add(user_id)
            for currency, cents, suffix in EXTRA_CCY:
                held = (
                    db.query(Account)
                    .filter(Account.user_id == user_id, Account.currency == currency)
                    .first()
                )
                if held:
                    continue
                account_no = f"6222{int(user_id):06d}{suffix}"
                if db.query(Account).filter(Account.account_no == account_no).first():
                    continue
                db.add(
                    Account(
                        account_no=account_no,
                        customer_id=customer_id,
                        user_id=user_id,
                        balance_cents=cents,
                        status="active",
                        currency=currency,
                    )
                )
        db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    seed_account()
    yield


app = FastAPI(title="bank-dp", lifespan=lifespan)


@app.get("/health")
def health():
    return ok({"service": settings.service_name, "status": "up"})


async def resolve_customer_id(user_id: int, token: str) -> int | None:
    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.get(
            f"{settings.cf_base_url}/api/cf/customers/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        data = r.json()
        if data.get("code") == 0 and data.get("data"):
            return data["data"]["id"]
    return None


@app.post("/api/dp/accounts")
async def open_account(
    body: OpenAccountReq,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    payload = auth_payload(authorization)
    if "code" in payload and payload.get("code") != 0:
        return payload
    user_id = int(payload["uid"])
    token = authorization.split(" ", 1)[1]
    customer_id = body.customer_id or await resolve_customer_id(user_id, token)
    if not customer_id:
        return fail(ErrorCode.NOT_FOUND, "customer profile required")
    existing = db.query(Account).filter(Account.user_id == user_id, Account.status == "active").first()
    if existing:
        return ok(account_out(existing))
    account_no = f"6222{datetime.utcnow().strftime('%H%M%S')}{user_id:04d}{uuid4().hex[:4]}"
    a = Account(account_no=account_no, customer_id=customer_id, user_id=user_id, balance_cents=0)
    db.add(a)
    db.commit()
    db.refresh(a)
    return ok(account_out(a))


@app.get("/api/dp/accounts")
def list_accounts(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
    all: bool = False,
):
    payload = auth_payload(authorization)
    if "code" in payload and payload.get("code") != 0:
        return payload
    q = db.query(Account)
    if not all or payload.get("role") != "admin":
        q = q.filter(Account.user_id == int(payload["uid"]))
    rows = (
        q.order_by(case((Account.currency == "USD", 0), else_=1), Account.id.desc())
        .limit(100)
        .all()
    )
    return ok([account_out(a) for a in rows])


@app.get("/api/dp/accounts/{account_no}")
def get_account(account_no: str, db: Session = Depends(get_db)):
    a = db.query(Account).filter(Account.account_no == account_no).first()
    if not a:
        return fail(ErrorCode.NOT_FOUND, "account not found")
    return ok(account_out(a))


@app.get("/api/dp/accounts/{account_no}/ledgers")
def list_ledgers(account_no: str, db: Session = Depends(get_db)):
    rows = (
        db.query(Ledger)
        .filter(Ledger.account_no == account_no)
        .order_by(Ledger.id.desc())
        .limit(100)
        .all()
    )
    return ok(
        [
            {
                "id": r.id,
                "account_no": r.account_no,
                "txn_id": r.txn_id,
                "direction": r.direction,
                "amount_cents": r.amount_cents,
                "amount": cents_to_yuan(r.amount_cents),
                "balance_after": cents_to_yuan(r.balance_after),
                "remark": r.remark,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
    )


def check_idempotency(db: Session, key: str | None):
    if not key:
        return None
    existing = db.query(Txn).filter(Txn.idempotency_key == key).first()
    if existing:
        return ok({"txn_id": existing.txn_id, "status": existing.status, "idempotent": True})
    return None


def record_and_publish(
    db: Session,
    *,
    txn_type: str,
    txn_code: str,
    amount_cents: int,
    account_no: str,
    contra: str,
    customer_id: int,
    idem_key: str,
    debit_no: str | None,
    credit_no: str | None,
):
    txn_id = uuid4().hex
    txn = Txn(
        txn_id=txn_id,
        txn_code=txn_code,
        txn_type=txn_type,
        amount_cents=amount_cents,
        account_no=account_no,
        contra_account_no=contra,
        customer_id=customer_id,
        idempotency_key=idem_key or txn_id,
        status="success",
    )
    db.add(txn)
    db.commit()
    event = AccountingEvent(
        event_id=uuid4().hex,
        txn_id=txn_id,
        txn_type=txn_type,  # type: ignore
        amount_cents=amount_cents,
        debit_account_no=debit_no,
        credit_account_no=credit_no,
        customer_id=customer_id,
        txn_code=txn_code,
    )
    publish_accounting_event(event)
    return txn_id


@app.post("/api/dp/txns/deposit")
def deposit(
    body: AmountReq,
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
):
    payload = auth_payload(authorization)
    if "code" in payload and payload.get("code") != 0:
        return payload
    pay_err = require_pay(authorization, body.pay_password)
    if pay_err:
        return pay_err
    cached = check_idempotency(db, idempotency_key)
    if cached:
        return cached
    cents = yuan_to_cents(body.amount)
    if cents <= 0:
        return fail(ErrorCode.VALIDATION, "amount must be positive")
    a = db.query(Account).filter(Account.account_no == body.account_no).with_for_update().first()
    if not a:
        return fail(ErrorCode.NOT_FOUND, "account not found")
    if a.status != "active":
        return fail(ErrorCode.ACCOUNT_FROZEN, "account not active")
    a.balance_cents += cents
    db.add(
        Ledger(
            account_no=a.account_no,
            txn_id="pending",
            direction="in",
            amount_cents=cents,
            balance_after=a.balance_cents,
            remark="deposit",
        )
    )
    db.flush()
    txn_id = record_and_publish(
        db,
        txn_type="deposit",
        txn_code="dp2020",
        amount_cents=cents,
        account_no=a.account_no,
        contra="",
        customer_id=a.customer_id,
        idem_key=idempotency_key or "",
        debit_no="1001",
        credit_no=a.account_no,
    )
    led = db.query(Ledger).filter(Ledger.account_no == a.account_no, Ledger.txn_id == "pending").order_by(Ledger.id.desc()).first()
    if led:
        led.txn_id = txn_id
        db.commit()
    return ok({"txn_id": txn_id, "balance": cents_to_yuan(a.balance_cents), "txn_code": "dp2020"})


@app.post("/api/dp/txns/withdraw")
def withdraw(
    body: AmountReq,
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
):
    payload = auth_payload(authorization)
    if "code" in payload and payload.get("code") != 0:
        return payload
    pay_err = require_pay(authorization, body.pay_password)
    if pay_err:
        return pay_err
    cached = check_idempotency(db, idempotency_key)
    if cached:
        return cached
    cents = yuan_to_cents(body.amount)
    if cents <= 0:
        return fail(ErrorCode.VALIDATION, "amount must be positive")
    a = db.query(Account).filter(Account.account_no == body.account_no).with_for_update().first()
    if not a:
        return fail(ErrorCode.NOT_FOUND, "account not found")
    if a.status != "active":
        return fail(ErrorCode.ACCOUNT_FROZEN, "account not active")
    if a.balance_cents < cents:
        return fail(ErrorCode.INSUFFICIENT_BALANCE, "insufficient balance")
    a.balance_cents -= cents
    db.add(
        Ledger(
            account_no=a.account_no,
            txn_id="pending",
            direction="out",
            amount_cents=cents,
            balance_after=a.balance_cents,
            remark="withdraw",
        )
    )
    db.flush()
    txn_id = record_and_publish(
        db,
        txn_type="withdraw",
        txn_code="dp2020",
        amount_cents=cents,
        account_no=a.account_no,
        contra="",
        customer_id=a.customer_id,
        idem_key=idempotency_key or "",
        debit_no=a.account_no,
        credit_no="1001",
    )
    led = db.query(Ledger).filter(Ledger.account_no == a.account_no, Ledger.txn_id == "pending").order_by(Ledger.id.desc()).first()
    if led:
        led.txn_id = txn_id
        db.commit()
    return ok({"txn_id": txn_id, "balance": cents_to_yuan(a.balance_cents), "txn_code": "dp2020"})


@app.post("/api/dp/txns/transfer")
def transfer(
    body: TransferReq,
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
):
    payload = auth_payload(authorization)
    if "code" in payload and payload.get("code") != 0:
        return payload
    pay_err = require_pay(authorization, body.pay_password)
    if pay_err:
        return pay_err
    cached = check_idempotency(db, idempotency_key)
    if cached:
        return cached
    cents = yuan_to_cents(body.amount)
    if cents <= 0:
        return fail(ErrorCode.VALIDATION, "amount must be positive")
    if body.from_account_no == body.to_account_no:
        return fail(ErrorCode.VALIDATION, "same account")

    is_wire = (body.transfer_type or "").lower() == "wire" or bool(body.swift_code.strip())
    if is_wire:
        if not body.beneficiary_name.strip():
            return fail(ErrorCode.VALIDATION, "beneficiary_name required for wire")
        if not body.swift_code.strip():
            return fail(ErrorCode.VALIDATION, "swift_code required for wire")
        if len(body.swift_code.strip()) < 8:
            return fail(ErrorCode.VALIDATION, "invalid swift_code")
        src = (
            db.query(Account)
            .filter(Account.account_no == body.from_account_no)
            .with_for_update()
            .first()
        )
        if not src:
            return fail(ErrorCode.NOT_FOUND, "account not found")
        if src.user_id != int(payload["uid"]):
            return fail(ErrorCode.FORBIDDEN, "account not owned by user")
        if src.status != "active":
            return fail(ErrorCode.ACCOUNT_FROZEN, "account not active")
        if src.balance_cents < cents:
            return fail(ErrorCode.INSUFFICIENT_BALANCE, "insufficient balance")
        src.balance_cents -= cents
        remark = (
            f"wire to {body.beneficiary_name}/{body.to_account_no} "
            f"SWIFT {body.swift_code.strip().upper()} @ {body.bank_name or 'N/A'}"
        )
        if body.remittance_info:
            remark += f" | {body.remittance_info[:80]}"
        db.add(
            Ledger(
                account_no=src.account_no,
                txn_id="pending",
                direction="out",
                amount_cents=cents,
                balance_after=src.balance_cents,
                remark=remark[:240],
            )
        )
        db.flush()
        txn_id = record_and_publish(
            db,
            txn_type="withdraw",
            txn_code="dp2090",
            amount_cents=cents,
            account_no=src.account_no,
            contra=body.to_account_no,
            customer_id=src.customer_id,
            idem_key=idempotency_key or "",
            debit_no=src.account_no,
            credit_no="1001",
        )
        led = (
            db.query(Ledger)
            .filter(Ledger.account_no == src.account_no, Ledger.txn_id == "pending")
            .order_by(Ledger.id.desc())
            .first()
        )
        if led:
            led.txn_id = txn_id
        db.commit()
        return ok(
            {
                "txn_id": txn_id,
                "from_balance": cents_to_yuan(src.balance_cents),
                "txn_code": "dp2090",
                "transfer_type": "wire",
                "beneficiary_name": body.beneficiary_name,
                "swift_code": body.swift_code.strip().upper(),
                "bank_name": body.bank_name,
                "bank_country": body.bank_country,
                "to_account_no": body.to_account_no,
            }
        )

    nos = sorted([body.from_account_no, body.to_account_no])
    accounts = (
        db.query(Account)
        .filter(Account.account_no.in_(nos))
        .with_for_update()
        .all()
    )
    by_no = {a.account_no: a for a in accounts}
    src = by_no.get(body.from_account_no)
    dst = by_no.get(body.to_account_no)
    if not src or not dst:
        return fail(ErrorCode.NOT_FOUND, "account not found (use wire + SWIFT for external)")
    if src.status != "active" or dst.status != "active":
        return fail(ErrorCode.ACCOUNT_FROZEN, "account not active")
    if src.balance_cents < cents:
        return fail(ErrorCode.INSUFFICIENT_BALANCE, "insufficient balance")
    src.balance_cents -= cents
    dst.balance_cents += cents
    ben = body.beneficiary_name.strip()
    out_remark = f"transfer to {dst.account_no}" + (f" ({ben})" if ben else "")
    in_remark = f"transfer from {src.account_no}" + (f" ({ben})" if ben else "")
    db.add(
        Ledger(
            account_no=src.account_no,
            txn_id="pending",
            direction="out",
            amount_cents=cents,
            balance_after=src.balance_cents,
            remark=out_remark[:240],
        )
    )
    db.add(
        Ledger(
            account_no=dst.account_no,
            txn_id="pending",
            direction="in",
            amount_cents=cents,
            balance_after=dst.balance_cents,
            remark=in_remark[:240],
        )
    )
    db.flush()
    txn_id = record_and_publish(
        db,
        txn_type="transfer",
        txn_code="dp2050",
        amount_cents=cents,
        account_no=src.account_no,
        contra=dst.account_no,
        customer_id=src.customer_id,
        idem_key=idempotency_key or "",
        debit_no=src.account_no,
        credit_no=dst.account_no,
    )
    for led in db.query(Ledger).filter(Ledger.txn_id == "pending").all():
        led.txn_id = txn_id
    db.commit()
    return ok(
        {
            "txn_id": txn_id,
            "from_balance": cents_to_yuan(src.balance_cents),
            "to_balance": cents_to_yuan(dst.balance_cents),
            "txn_code": "dp2050",
            "transfer_type": "internal",
            "beneficiary_name": ben,
        }
    )


@app.post("/api/dp/txns/wealth-buy")
def wealth_buy(
    body: WealthBuyReq,
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
):
    payload = auth_payload(authorization)
    if "code" in payload and payload.get("code") != 0:
        return payload
    pay_err = require_pay(authorization, body.pay_password)
    if pay_err:
        return pay_err
    cached = check_idempotency(db, idempotency_key)
    if cached:
        return cached
    cents = yuan_to_cents(body.amount)
    if cents <= 0:
        return fail(ErrorCode.VALIDATION, "amount must be positive")
    if not body.product_id:
        return fail(ErrorCode.VALIDATION, "product_id required")
    a = db.query(Account).filter(Account.account_no == body.account_no).with_for_update().first()
    if not a:
        return fail(ErrorCode.NOT_FOUND, "account not found")
    if a.user_id != int(payload["uid"]):
        return fail(ErrorCode.FORBIDDEN, "account not owned by user")
    if a.status != "active":
        return fail(ErrorCode.ACCOUNT_FROZEN, "account not active")
    if a.balance_cents < cents:
        return fail(ErrorCode.INSUFFICIENT_BALANCE, "insufficient balance")
    product_name = (body.product_name or body.product_id).strip()[:64]
    remark = f"wealth-buy:{body.product_id}:{product_name}"
    a.balance_cents -= cents
    db.add(
        Ledger(
            account_no=a.account_no,
            txn_id="pending",
            direction="out",
            amount_cents=cents,
            balance_after=a.balance_cents,
            remark=remark,
        )
    )
    db.flush()
    txn_id = record_and_publish(
        db,
        txn_type="wealth_buy",
        txn_code="dp3010",
        amount_cents=cents,
        account_no=a.account_no,
        contra="1301",
        customer_id=a.customer_id,
        idem_key=idempotency_key or "",
        debit_no="1301",
        credit_no=a.account_no,
    )
    led = (
        db.query(Ledger)
        .filter(Ledger.account_no == a.account_no, Ledger.txn_id == "pending")
        .order_by(Ledger.id.desc())
        .first()
    )
    if led:
        led.txn_id = txn_id
        db.commit()
    return ok(
        {
            "txn_id": txn_id,
            "balance": cents_to_yuan(a.balance_cents),
            "txn_code": "dp3010",
            "product_id": body.product_id,
            "product_name": product_name,
        }
    )
