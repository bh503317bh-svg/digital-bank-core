import logging

import httpx

from bank_common import AccountingEvent

from app.config import settings

logger = logging.getLogger(__name__)


def publish_accounting_event(event: AccountingEvent) -> None:
    """Sync push accounting event to bank-ac over HTTP (no RabbitMQ)."""
    url = f"{settings.ac_base_url.rstrip('/')}/api/ac/events"
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(url, json=event.model_dump(mode="json"))
            if resp.status_code >= 400:
                logger.error("ac event rejected: %s %s", resp.status_code, resp.text)
    except Exception as exc:
        logger.exception("publish accounting event failed: %s", exc)
