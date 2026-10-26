from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class RuleResult:
    code: str
    passed: bool
    score_delta: int
    message: str


INDUSTRY_RISK = {
    "IT": 20,
    "FINANCE": 15,
    "EDU": 10,
    "HEALTH": 12,
    "MANUFACTURING": 5,
    "RETAIL": 0,
    "LOGISTICS": 3,
    "REAL_ESTATE": -15,
    "GAMBLING": -80,
    "CRYPTO": -40,
    "GOVERNMENT": 25,
    "ENERGY": 8,
    "AGRI": -5,
    "MEDIA": 2,
    "LEGAL": 10,
    "CONSULTING": 8,
    "HOSPITALITY": -8,
    "TRANSPORT": 0,
    "CONSTRUCTION": -10,
    "MINING": -12,
}

CITY_TIER_SCORE = {
    "T1": 30,
    "T1.5": 25,
    "T2": 20,
    "T3": 15,
    "T4": 10,
    "T5": 5,
    "COUNTY": 0,
}

PURPOSE_SCORE = {
    "education": 15,
    "medical": 12,
    "home_renovation": 8,
    "wedding": 5,
    "travel": -5,
    "electronics": 0,
    "business_turnover": 10,
    "debt_consolidation": -20,
    "car": 5,
    "other": 0,
}


def rule_age(age: int) -> RuleResult:
    if age < 18:
        return RuleResult("AGE_MIN", False, -1000, "under 18")
    if age > 65:
        return RuleResult("AGE_MAX", False, -1000, "over 65")
    if 25 <= age <= 45:
        return RuleResult("AGE_SWEET", True, 20, "prime age")
    if 18 <= age < 25:
        return RuleResult("AGE_YOUNG", True, 5, "young adult")
    return RuleResult("AGE_SENIOR", True, 0, "senior ok")


def rule_income(monthly_income_cents: int, amount_cents: int) -> RuleResult:
    if monthly_income_cents <= 0:
        return RuleResult("INCOME_MISSING", False, -200, "income required")
    # DTI rough: monthly payment approx amount/12
    est_payment = amount_cents // 12
    if est_payment > monthly_income_cents * 6 // 10:
        return RuleResult("DTI_HIGH", False, -80, "debt to income too high")
    if monthly_income_cents >= 3000000:  # 30k
        return RuleResult("INCOME_HIGH", True, 25, "high income")
    if monthly_income_cents >= 1000000:
        return RuleResult("INCOME_MID", True, 10, "mid income")
    return RuleResult("INCOME_LOW", True, -10, "low income")


def rule_credit_history(delinquencies_24m: int, inquiries_6m: int) -> RuleResult:
    if delinquencies_24m >= 3:
        return RuleResult("DLQ_SEVERE", False, -500, "too many delinquencies")
    if delinquencies_24m == 2:
        return RuleResult("DLQ_2", True, -40, "two delinquencies")
    if delinquencies_24m == 1:
        return RuleResult("DLQ_1", True, -15, "one delinquency")
    if inquiries_6m >= 8:
        return RuleResult("INQUIRY_FLOOD", True, -25, "many credit inquiries")
    return RuleResult("CLEAN_HISTORY", True, 30, "clean history")


def rule_employment(months_employed: int, employment_type: str) -> RuleResult:
    if employment_type in {"unemployed", "student"} and months_employed < 6:
        return RuleResult("EMP_WEAK", False, -100, "unstable employment")
    if employment_type == "civil_servant":
        return RuleResult("EMP_GOV", True, 25, "civil servant")
    if months_employed >= 36:
        return RuleResult("EMP_STABLE", True, 15, "stable employment")
    if months_employed >= 12:
        return RuleResult("EMP_OK", True, 5, "employed 1y+")
    return RuleResult("EMP_NEW", True, -5, "new job")


def rule_amount_vs_product(amount_cents: int, min_cents: int, max_cents: int) -> RuleResult:
    if amount_cents < min_cents:
        return RuleResult("AMT_LOW", False, -1000, "below product min")
    if amount_cents > max_cents:
        return RuleResult("AMT_HIGH", False, -1000, "above product max")
    ratio = amount_cents / max_cents
    if ratio > 0.9:
        return RuleResult("AMT_NEAR_MAX", True, -10, "near max limit")
    return RuleResult("AMT_OK", True, 5, "amount ok")


def rule_industry(industry: str) -> RuleResult:
    delta = INDUSTRY_RISK.get(industry.upper(), -5)
    return RuleResult("INDUSTRY", delta >= 0 or delta > -50, delta, f"industry {industry}")


def rule_city(city_tier: str) -> RuleResult:
    delta = CITY_TIER_SCORE.get(city_tier.upper(), 0)
    return RuleResult("CITY", True, delta, f"city {city_tier}")


def rule_purpose(purpose: str) -> RuleResult:
    delta = PURPOSE_SCORE.get(purpose, 0)
    hard_fail = purpose == "debt_consolidation" and delta <= -20
    return RuleResult("PURPOSE", not hard_fail, delta, f"purpose {purpose}")


def rule_existing_exposure(active_loans: int, exposure_cents: int, max_loans: int, max_exposure: int) -> RuleResult:
    if active_loans >= max_loans:
        return RuleResult("EXPOSURE_COUNT", False, -1000, "too many active loans")
    if exposure_cents >= max_exposure:
        return RuleResult("EXPOSURE_AMT", False, -1000, "exposure limit")
    if exposure_cents > max_exposure * 7 // 10:
        return RuleResult("EXPOSURE_WARN", True, -20, "high exposure")
    return RuleResult("EXPOSURE_OK", True, 10, "exposure ok")


def rule_blacklist(flags: list[str]) -> RuleResult:
    if "fraud" in flags or "aml_hit" in flags:
        return RuleResult("BLACKLIST", False, -1000, "blacklist hit")
    if "watchlist" in flags:
        return RuleResult("WATCHLIST", True, -30, "on watchlist")
    return RuleResult("BL_CLEAR", True, 5, "clear")


def rule_device_risk(device_score: int) -> RuleResult:
    if device_score < 20:
        return RuleResult("DEVICE_BAD", False, -200, "risky device")
    if device_score < 50:
        return RuleResult("DEVICE_WEAK", True, -15, "weak device trust")
    if device_score >= 80:
        return RuleResult("DEVICE_GOOD", True, 10, "trusted device")
    return RuleResult("DEVICE_OK", True, 0, "device ok")


def rule_relation_graph(shared_devices: int, shared_contacts: int) -> RuleResult:
    if shared_devices >= 5:
        return RuleResult("GRAPH_DEVICE", False, -300, "device sharing ring")
    if shared_contacts >= 10:
        return RuleResult("GRAPH_CONTACT", True, -20, "dense contact graph")
    return RuleResult("GRAPH_OK", True, 5, "graph ok")
