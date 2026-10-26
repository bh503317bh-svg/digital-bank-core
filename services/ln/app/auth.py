from __future__ import annotations

from fastapi import Header
from bank_common import ErrorCode, decode_token, fail
from app.config import settings


def require_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        return fail(ErrorCode.UNAUTHORIZED, "missing token")
    try:
        return decode_token(authorization.split(" ", 1)[1], secret=settings.jwt_secret)
    except Exception:
        return fail(ErrorCode.UNAUTHORIZED, "invalid token")


def require_admin(authorization: str | None = Header(default=None)) -> dict:
    payload = require_user(authorization)
    if isinstance(payload, dict) and payload.get("code") and payload.get("code") != 0:
        return payload
    if payload.get("role") != "admin":
        return fail(ErrorCode.FORBIDDEN, "admin only")
    return payload


def is_error(payload: dict) -> bool:
    return isinstance(payload, dict) and "code" in payload and payload.get("code") != 0
