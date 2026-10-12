import logging
import time
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import InvoiceEvent, RecurringInvoiceSchedule
from app.services.billing import create_scheduled_invoice, next_recurring_date
from app.webhook_service import publish_webhook_event

logger = logging.getLogger(__name__)


def run_once(session_factory: type[Session] = SessionLocal, *, batch_size: int = 20) -> int:
    db = session_factory()
    created = 0
    now = datetime.now(UTC)
    try:
        schedules = list(db.scalars(select(RecurringInvoiceSchedule).where(
            RecurringInvoiceSchedule.is_active.is_(True),
            RecurringInvoiceSchedule.next_invoice_date <= now.date(),
        ).order_by(
            RecurringInvoiceSchedule.next_invoice_date,
            RecurringInvoiceSchedule.id,
        ).with_for_update(skip_locked=True).limit(batch_size)).all())
        for schedule in schedules:
            try:
                invoice = create_scheduled_invoice(db, schedule)
                if schedule.auto_issue:
                    invoice.status = "issued"
                    invoice.issued_at = now
                schedule.last_invoice_id = invoice.id
                schedule.last_run_at = now
                schedule.last_run_error = None
                schedule.next_invoice_date = next_recurring_date(schedule.next_invoice_date, schedule.frequency)
                db.add(InvoiceEvent(
                    invoice_id=invoice.id,
                    actor_user_id=schedule.created_by_user_id,
                    event_type="invoice.recurring_generated",
                    from_status=None,
                    to_status=invoice.status,
                    detail={"recurring_schedule_id": str(schedule.id)},
                ))
                publish_webhook_event(db, schedule.company_id, "invoice.created", {
                    "invoice_id": str(invoice.id),
                    "source": "recurring_invoice",
                    "recurring_schedule_id": str(schedule.id),
                    "invoice_number": invoice.invoice_number,
                })
                created += 1
            except Exception as exc:
                schedule.last_run_error = f"{type(exc).__name__}: {exc}"[:1000]
                logger.exception("Recurring invoice generation failed schedule=%s", schedule.id)
        db.commit()
    finally:
        db.close()
    return created


def run_forever(poll_seconds: int | None = None) -> None:
    interval = poll_seconds or get_settings().billing_poll_seconds
    while True:
        try:
            run_once()
        except KeyboardInterrupt:
            return
        except Exception:
            logger.exception("Recurring invoice worker iteration failed")
        time.sleep(interval)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_forever()
