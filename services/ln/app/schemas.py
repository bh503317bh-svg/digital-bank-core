
from __future__ import annotations

from pydantic import BaseModel, Field


class ApplyReq(BaseModel):
    product_id: str
    amount: str = Field(description="yuan")
    term_months: int
    purpose: str = "other"
    customer_id: int = 1
    age: int = 30
    monthly_income: str = "15000"
    delinquencies_24m: int = 0
    inquiries_6m: int = 1
    months_employed: int = 24
    employment_type: str = "employed"
    industry: str = "IT"
    city_tier: str = "T2"
    device_score: int = 75
    shared_devices: int = 0
    shared_contacts: int = 0
    flags: list[str] = []
    pay_password: str = Field(min_length=4, max_length=12)


class RepayReq(BaseModel):
    loan_id: str
    amount: str
    channel: str = "app"
    pay_password: str = Field(min_length=4, max_length=12)


class ReviewReq(BaseModel):
    application_id: str
    decision: str  # approved / rejected
    reason: str = ""
