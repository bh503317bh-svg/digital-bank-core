from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from bank_common import AccountingEvent

from app.models import AcEntry, AcEvent, EventSum


def apply_event(db: Session, event: AccountingEvent) -> bool:
    """Apply accounting event. Returns False if already applied (idempotent)."""
    if db.query(AcEvent).filter(AcEvent.event_id == event.event_id).first():
        return False
    db.add(
        AcEvent(
            event_id=event.event_id,
            txn_id=event.txn_id,
            txn_type=event.txn_type,
            amount_cents=event.amount_cents,
            txn_code=event.txn_code,
        )
    )
    pairs: list[tuple[str, str]] = []
    if event.txn_type == "deposit":
        pairs = [("debit", event.debit_account_no or "1001"), ("credit", event.credit_account_no or "2001")]
    elif event.txn_type == "withdraw":
        pairs = [("debit", event.debit_account_no or "2001"), ("credit", event.credit_account_no or "1001")]
    elif event.txn_type == "wealth_buy":
        # Dr wealth asset 1301; Cr customer deposit liability (account_no)
        pairs = [
            ("debit", event.debit_account_no or "1301"),
            ("credit", event.credit_account_no or "2001"),
        ]
    else:
        pairs = [("debit", event.debit_account_no or ""), ("credit", event.credit_account_no or "")]

    biz_date = datetime.utcnow().strftime("%Y-%m-%d")
    for side, code in pairs:
        if not code:
            continue
        db.add(
            AcEntry(
                event_id=event.event_id,
                txn_id=event.txn_id,
                side=side,
                account_code=code,
                amount_cents=event.amount_cents,
            )
        )
        row = (
            db.query(EventSum)
            .filter(
                EventSum.biz_date == biz_date,
                EventSum.account_code == code,
                EventSum.side == side,
            )
            .first()
        )
        if row:
            row.amount_cents += event.amount_cents
        else:
            db.add(
                EventSum(
                    biz_date=biz_date,
                    account_code=code,
                    side=side,
                    amount_cents=event.amount_cents,
                )
            )
    db.commit()
    return True
