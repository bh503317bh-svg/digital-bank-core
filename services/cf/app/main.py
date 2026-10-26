from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from bank_common import ErrorCode, decode_token, fail, ok

from app.config import settings
from app.db import Base, SessionLocal, engine, get_db
from app.models import Agreement, Customer


class CreateCustomer(BaseModel):
    name: str
    id_no: str = Field(default="", max_length=32)
    mobile: str = ""


def mask_id(id_no: str) -> str:
    if len(id_no) < 8:
        return id_no[:2] + "****" if id_no else ""
    return id_no[:4] + "**********" + id_no[-4:]


def seed_customer() -> None:
    db = SessionLocal()
    try:
        if not db.query(Customer).filter(Customer.user_id == 1).first():
            c = Customer(
                user_id=1,
                name="Aku User",
                id_no_masked="1101**********1234",
                kyc_status="verified",
                mobile="13800000001",
            )
            db.add(c)
            db.commit()
            db.refresh(c)
            db.add(Agreement(customer_id=c.id, agree_type="deposit_account"))
            db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    seed_customer()
    yield


app = FastAPI(title="bank-cf", lifespan=lifespan)


def auth_uid(authorization: str | None = Header(default=None)) -> int | dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        return fail(ErrorCode.UNAUTHORIZED, "missing token")
    token = authorization.split(" ", 1)[1]
    try:
        payload = decode_token(token, secret=settings.jwt_secret)
        return int(payload["uid"])
    except Exception:
        return fail(ErrorCode.UNAUTHORIZED, "invalid token")


@app.get("/health")
def health():
    return ok({"service": settings.service_name, "status": "up"})


@app.post("/api/cf/customers")
def create_customer(
    body: CreateCustomer,
    uid=Depends(auth_uid),
    db: Session = Depends(get_db),
):
    if isinstance(uid, dict):
        return uid
    existing = db.query(Customer).filter(Customer.user_id == uid).first()
    if existing:
        return fail(ErrorCode.CONFLICT, "customer already exists", {"id": existing.id})
    c = Customer(
        user_id=uid,
        name=body.name,
        id_no_masked=mask_id(body.id_no),
        kyc_status="verified",
        mobile=body.mobile,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    db.add(Agreement(customer_id=c.id))
    db.commit()
    return ok(
        {
            "id": c.id,
            "user_id": c.user_id,
            "name": c.name,
            "id_no_masked": c.id_no_masked,
            "kyc_status": c.kyc_status,
            "mobile": c.mobile,
        }
    )


@app.get("/api/cf/customers/me")
def my_customer(uid=Depends(auth_uid), db: Session = Depends(get_db)):
    if isinstance(uid, dict):
        return uid
    c = db.query(Customer).filter(Customer.user_id == uid).first()
    if not c:
        return fail(ErrorCode.NOT_FOUND, "customer not found")
    return ok(
        {
            "id": c.id,
            "user_id": c.user_id,
            "name": c.name,
            "id_no_masked": c.id_no_masked,
            "kyc_status": c.kyc_status,
            "mobile": c.mobile,
        }
    )


@app.get("/api/cf/customers")
def list_customers(db: Session = Depends(get_db), authorization: str | None = Header(default=None)):
    auth = auth_uid(authorization)
    if isinstance(auth, dict):
        return auth
    rows = db.query(Customer).order_by(Customer.id.desc()).limit(100).all()
    return ok(
        [
            {
                "id": c.id,
                "user_id": c.user_id,
                "name": c.name,
                "id_no_masked": c.id_no_masked,
                "kyc_status": c.kyc_status,
                "mobile": c.mobile,
            }
            for c in rows
        ]
    )


@app.get("/api/cf/customers/{customer_id}")
def get_customer(customer_id: int, db: Session = Depends(get_db)):
    c = db.query(Customer).filter(Customer.id == customer_id).first()
    if not c:
        return fail(ErrorCode.NOT_FOUND, "customer not found")
    return ok(
        {
            "id": c.id,
            "user_id": c.user_id,
            "name": c.name,
            "id_no_masked": c.id_no_masked,
            "kyc_status": c.kyc_status,
            "mobile": c.mobile,
        }
    )
