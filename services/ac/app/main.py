from contextlib import asynccontextmanager
from decimal import Decimal

from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from bank_common import AccountingEvent, ok

from app.accounting import apply_event
from app.config import settings
from app.db import Base, engine, get_db
from app.models import AcEntry, AcEvent, EventSum


def cents_to_yuan(cents: int) -> str:
    return f"{Decimal(cents) / 100:.2f}"


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="bank-ac", lifespan=lifespan)


@app.get("/health")
def health():
    return ok({"service": settings.service_name, "status": "up"})


@app.post("/api/ac/events")
def create_event(event: AccountingEvent, db: Session = Depends(get_db)):
    created = apply_event(db, event)
    return ok({"event_id": event.event_id, "created": created})


@app.get("/api/ac/events")
def list_events(db: Session = Depends(get_db)):
    rows = db.query(AcEvent).order_by(AcEvent.id.desc()).limit(100).all()
    return ok(
        [
            {
                "id": r.id,
                "event_id": r.event_id,
                "txn_id": r.txn_id,
                "txn_type": r.txn_type,
                "txn_code": r.txn_code,
                "amount": cents_to_yuan(r.amount_cents),
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
    )


@app.get("/api/ac/entries")
def list_entries(db: Session = Depends(get_db)):
    rows = db.query(AcEntry).order_by(AcEntry.id.desc()).limit(200).all()
    return ok(
        [
            {
                "id": r.id,
                "event_id": r.event_id,
                "txn_id": r.txn_id,
                "side": r.side,
                "account_code": r.account_code,
                "amount": cents_to_yuan(r.amount_cents),
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
    )


@app.get("/api/ac/event-sum")
def list_sum(db: Session = Depends(get_db)):
    rows = db.query(EventSum).order_by(EventSum.biz_date.desc()).limit(100).all()
    return ok(
        [
            {
                "biz_date": r.biz_date,
                "account_code": r.account_code,
                "side": r.side,
                "amount": cents_to_yuan(r.amount_cents),
            }
            for r in rows
        ]
    )
