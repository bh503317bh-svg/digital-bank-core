"""One process for login, customers, deposits, accounting, and loans."""

from __future__ import annotations

import importlib
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

ROOT = Path(__file__).resolve().parent
SELF = "http://127.0.0.1:8001"
SKIP = {"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc", "/health"}


def database_url(name: str) -> str:
    user = os.environ.get("MYSQL_USER", "wecode")
    password = os.environ.get("MYSQL_PASSWORD", "wecode_pass")
    host = os.environ.get("MYSQL_HOST", "mysql")
    return f"mysql+pymysql://{user}:{password}@{host}:3306/{name}"


def load_service(name: str, env: dict[str, str]):
    for key, value in env.items():
        os.environ[key] = value
    for key in list(sys.modules):
        if key == "app" or key.startswith("app."):
            del sys.modules[key]
    service_dir = str(ROOT / "services" / name)
    sys.path.insert(0, service_dir)
    try:
        module = importlib.import_module("app.main")
        application = module.app
    finally:
        sys.path.remove(service_dir)
    prefix = f"_svc_{name}"
    for key in list(sys.modules):
        if key == "app" or key.startswith("app."):
            sys.modules[f"{prefix}.{key}"] = sys.modules.pop(key)
    return application


def build():
    os.environ.setdefault("JWT_SECRET", "wecode-bank-demo-secret-change-me")
    services = [
        load_service("us", {"DATABASE_URL": database_url("bank_us")}),
        load_service("cf", {"DATABASE_URL": database_url("bank_cf")}),
        load_service(
            "dp",
            {
                "DATABASE_URL": database_url("bank_dp"),
                "CF_BASE_URL": SELF,
                "AC_BASE_URL": SELF,
                "US_BASE_URL": SELF,
            },
        ),
        load_service("ac", {"DATABASE_URL": database_url("bank_ac")}),
        load_service("ln", {"US_BASE_URL": SELF}),
    ]

    @asynccontextmanager
    async def lifespan(_app):
        contexts = []
        for sub in services:
            ctx = sub.router.lifespan_context(sub)
            await ctx.__aenter__()
            contexts.append(ctx)
        try:
            yield
        finally:
            for ctx in reversed(contexts):
                await ctx.__aexit__(None, None, None)

    app = FastAPI(title="digital-bank-core", lifespan=lifespan)

    @app.get("/health")
    def health():
        return {"code": 0, "message": "ok", "data": {"service": "digital-bank-core", "status": "up"}}

    for sub in services:
        for route in list(sub.router.routes):
            path = getattr(route, "path", "") or ""
            if path in SKIP:
                continue
            app.router.routes.append(route)
    return app


app = build()
