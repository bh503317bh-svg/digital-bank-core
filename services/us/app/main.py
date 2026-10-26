from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.orm import Session

from bank_common import (
    ErrorCode,
    create_access_token,
    decode_token,
    fail,
    hash_password,
    ok,
    verify_password,
)

from app.config import settings
from app.db import Base, SessionLocal, engine, get_db
from app.models import DEFAULT_PAY_PASSWORD, User
from app.schemas import (
    LoginRequest,
    PayPasswordSet,
    PayPasswordVerify,
    RegisterRequest,
    TokenData,
    UserOut,
)

security = HTTPBearer(auto_error=False)


def ensure_schema() -> None:
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN pay_password_hash VARCHAR(255) NULL"))
        except Exception:
            pass


def seed_users() -> None:
    db = SessionLocal()
    try:
        seeds = [
            ("13800000001", "Passw0rd!", "customer", "Aku User"),
            ("+12025550179", "Welcome1!", "customer", "Jordan Lee"),
            ("13900000001", "Admin123!", "admin", "Aku Admin"),
        ]
        default_pay = hash_password(DEFAULT_PAY_PASSWORD)
        for mobile, password, role, name in seeds:
            user = db.query(User).filter(User.mobile == mobile).first()
            if not user:
                db.add(
                    User(
                        mobile=mobile,
                        password_hash=hash_password(password),
                        pay_password_hash=default_pay,
                        role=role,
                        display_name=name,
                    )
                )
            elif not getattr(user, "pay_password_hash", None):
                user.pay_password_hash = default_pay
        # backfill any other users missing pay password
        for user in db.query(User).all():
            if not user.pay_password_hash:
                user.pay_password_hash = default_pay
        db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_schema()
    seed_users()
    yield


app = FastAPI(title="bank-us", lifespan=lifespan)


@app.get("/health")
def health():
    return ok({"service": settings.service_name, "status": "up"})


@app.post("/api/auth/register")
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.mobile == body.mobile).first():
        return fail(ErrorCode.CONFLICT, "mobile already registered")
    role = body.role if body.role in ("customer", "admin") else "customer"
    user = User(
        mobile=body.mobile,
        password_hash=hash_password(body.password),
        pay_password_hash=hash_password(body.pay_password or DEFAULT_PAY_PASSWORD),
        role=role,
        display_name=body.display_name or body.mobile,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return ok(UserOut.model_validate(user).model_dump())


@app.post("/api/auth/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.mobile == body.mobile).first()
    if not user or not verify_password(body.password, user.password_hash):
        return fail(ErrorCode.UNAUTHORIZED, "invalid mobile or password")
    if not user.pay_password_hash:
        user.pay_password_hash = hash_password(DEFAULT_PAY_PASSWORD)
        db.commit()
    token = create_access_token(
        user.mobile,
        role=user.role,
        user_id=user.id,
        secret=settings.jwt_secret,
    )
    data = TokenData(
        access_token=token,
        role=user.role,
        user_id=user.id,
        mobile=user.mobile,
        display_name=user.display_name,
    )
    return ok(data.model_dump())


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User | dict:
    token = None
    if credentials:
        token = credentials.credentials
    elif authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1]
    if not token:
        return fail(ErrorCode.UNAUTHORIZED, "missing token")
    try:
        payload = decode_token(token, secret=settings.jwt_secret)
    except Exception:
        return fail(ErrorCode.UNAUTHORIZED, "invalid token")
    user = db.query(User).filter(User.id == payload.get("uid")).first()
    if not user:
        return fail(ErrorCode.UNAUTHORIZED, "user not found")
    return user


@app.get("/api/auth/me")
def me(user=Depends(current_user)):
    if isinstance(user, dict):
        return user
    data = UserOut.model_validate(user).model_dump()
    data["has_pay_password"] = bool(user.pay_password_hash)
    return ok(data)


@app.post("/api/auth/verify-pay-password")
def verify_pay(body: PayPasswordVerify, user=Depends(current_user), db: Session = Depends(get_db)):
    if isinstance(user, dict):
        return user
    if not user.pay_password_hash:
        user.pay_password_hash = hash_password(DEFAULT_PAY_PASSWORD)
        db.commit()
    if not verify_password(body.pay_password, user.pay_password_hash):
        return fail(ErrorCode.PAY_PASSWORD_INVALID, "invalid payment password")
    return ok({"verified": True})


@app.post("/api/auth/set-pay-password")
def set_pay(body: PayPasswordSet, user=Depends(current_user), db: Session = Depends(get_db)):
    if isinstance(user, dict):
        return user
    if not verify_password(body.login_password, user.password_hash):
        return fail(ErrorCode.UNAUTHORIZED, "invalid login password")
    user.pay_password_hash = hash_password(body.new_pay_password)
    db.commit()
    return ok({"updated": True})


@app.get("/api/auth/users/{user_id}")
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return fail(ErrorCode.NOT_FOUND, "user not found")
    return ok(UserOut.model_validate(user).model_dump())
