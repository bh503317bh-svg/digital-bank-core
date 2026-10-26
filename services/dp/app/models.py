from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_no: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    customer_id: Mapped[int] = mapped_column(Integer, index=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    balance_cents: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[str] = mapped_column(String(16), default="active")
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Txn(Base):
    __tablename__ = "txns"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_txn_idem"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    txn_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    txn_code: Mapped[str] = mapped_column(String(16))
    txn_type: Mapped[str] = mapped_column(String(16))
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    account_no: Mapped[str] = mapped_column(String(32), index=True)
    contra_account_no: Mapped[str] = mapped_column(String(32), default="")
    customer_id: Mapped[int] = mapped_column(Integer, default=0)
    idempotency_key: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="success")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Ledger(Base):
    __tablename__ = "ledgers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_no: Mapped[str] = mapped_column(String(32), index=True)
    txn_id: Mapped[str] = mapped_column(String(64), index=True)
    direction: Mapped[str] = mapped_column(String(8))
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    balance_after: Mapped[int] = mapped_column(BigInteger)
    remark: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
