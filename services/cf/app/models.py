from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(64))
    id_no_masked: Mapped[str] = mapped_column(String(32), default="")
    kyc_status: Mapped[str] = mapped_column(String(32), default="pending")
    mobile: Mapped[str] = mapped_column(String(20), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Agreement(Base):
    __tablename__ = "agreements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(Integer, index=True)
    agree_type: Mapped[str] = mapped_column(String(64), default="deposit_account")
    status: Mapped[str] = mapped_column(String(32), default="signed")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
