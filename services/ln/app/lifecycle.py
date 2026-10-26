
from __future__ import annotations

APPLICATION_TRANSITIONS = {
    "draft": {"submitted", "cancelled"},
    "submitted": {"underwriting", "cancelled"},
    "underwriting": {"approved", "rejected", "manual_review"},
    "manual_review": {"approved", "rejected", "cancelled"},
    "approved": {"disbursed", "cancelled"},
    "rejected": set(),
    "disbursed": set(),
    "cancelled": set(),
}

LOAN_TRANSITIONS = {
    "active": {"overdue", "closed", "written_off"},
    "overdue": {"active", "closed", "written_off"},
    "closed": set(),
    "written_off": set(),
}


class InvalidTransition(Exception):
    pass


def assert_app_transition(current: str, target: str) -> None:
    allowed = APPLICATION_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise InvalidTransition(f"application {current} -> {target} not allowed")


def assert_loan_transition(current: str, target: str) -> None:
    allowed = LOAN_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise InvalidTransition(f"loan {current} -> {target} not allowed")
