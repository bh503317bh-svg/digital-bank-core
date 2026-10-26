from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class AcEvent(Base):
    __tablename__ = "events"
    __table_args__ = (UniqueConstraint("event_id", name="uq_event_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(64))
    txn_id: Mapped[str] = mapped_column(String(64), index=True)
    txn_type: Mapped[str] = mapped_column(String(16))
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    txn_code: Mapped[str] = mapped_column(String(16), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AcEntry(Base):
    __tablename__ = "entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(64), index=True)
    txn_id: Mapped[str] = mapped_column(String(64), index=True)
    side: Mapped[str] = mapped_column(String(8))
    account_code: Mapped[str] = mapped_column(String(64))
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class EventSum(Base):
    __tablename__ = "event_sum"
    __table_args__ = (UniqueConstraint("biz_date", "account_code", "side", name="uq_sum"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    biz_date: Mapped[str] = mapped_column(String(10))
    account_code: Mapped[str] = mapped_column(String(64))
    side: Mapped[str] = mapped_column(String(8))
    amount_cents: Mapped[int] = mapped_column(BigInteger, default=0)
