import logging
import random
import smtplib
import ssl
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from email.utils import make_msgid
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import NotificationAttempt, NotificationOutbox

logger = logging.getLogger(__name__)
SessionFactory = Callable[[], Session]
Sender = Callable[[NotificationOutbox], str | None]


class DeliveryConfigurationError(RuntimeError):
    pass


def send_smtp_notification(notification: NotificationOutbox) -> str:
    settings = get_settings()
    if not settings.smtp_host or not settings.smtp_from_email:
        raise DeliveryConfigurationError("SMTP_HOST and SMTP_FROM_EMAIL must be configured")
    if settings.smtp_username and not settings.smtp_password:
        raise DeliveryConfigurationError("SMTP_PASSWORD is required when SMTP_USERNAME is configured")

    message = EmailMessage()
    message["Subject"] = notification.subject
    message["From"] = settings.smtp_from_email
    message["To"] = notification.recipient_email
    message["Message-ID"] = make_msgid()
    message.set_content(notification.body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds) as smtp:
        if settings.smtp_starttls:
            smtp.starttls(context=ssl.create_default_context())
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password or "")
        refused = smtp.send_message(message)
        if refused:
            raise RuntimeError("SMTP refused one or more recipients")
    return str(message["Message-ID"])


def safe_error(exc: Exception) -> str:
    settings = get_settings()
    result = f"{type(exc).__name__}: {exc}"
    for secret in (settings.smtp_password, settings.smtp_username):
        if secret:
            result = result.replace(secret, "[redacted]")
    return result[:1000]


def claim_due_notifications(db: Session, *, batch_size: int = 10) -> list[tuple[UUID, UUID]]:
    now = datetime.now(UTC)
    lease_seconds = get_settings().notification_lease_seconds
    stmt = select(NotificationOutbox).where(or_(
        and_(NotificationOutbox.status == "queued", NotificationOutbox.next_attempt_at <= now),
        and_(
            NotificationOutbox.status == "processing",
            NotificationOutbox.locked_until.is_not(None),
            NotificationOutbox.locked_until <= now,
        ),
    )).order_by(
        NotificationOutbox.next_attempt_at, NotificationOutbox.created_at
    ).with_for_update(skip_locked=True).limit(batch_size)
    records = list(db.scalars(stmt).all())
    claimed: list[tuple[UUID, UUID]] = []
    for record in records:
        if record.status == "processing":
            previous = db.scalar(select(NotificationAttempt).where(
                NotificationAttempt.notification_id == record.id,
                NotificationAttempt.attempt_number == record.attempt_count,
            ))
            if previous is not None and previous.status == "started":
                previous.status = "failed"
                previous.error_message = "Worker lease expired; delivery outcome is unknown"
                previous.finished_at = now
        if record.attempt_count >= record.max_attempts:
            record.status = "dead"
            record.locked_until = None
            record.last_error = record.last_error or "Maximum delivery attempts reached"
            continue
        record.attempt_count += 1
        record.status = "processing"
        record.locked_until = now + timedelta(seconds=lease_seconds)
        attempt = NotificationAttempt(
            notification_id=record.id, attempt_number=record.attempt_count,
            status="started", provider="smtp", started_at=now,
        )
        db.add(attempt)
        db.flush()
        claimed.append((record.id, attempt.id))
    db.commit()
    return claimed


def deliver_claimed(
    session_factory: SessionFactory, notification_id: UUID, attempt_id: UUID,
    sender: Sender = send_smtp_notification,
) -> None:
    read_db = session_factory()
    try:
        notification = read_db.get(NotificationOutbox, notification_id)
        attempt = read_db.get(NotificationAttempt, attempt_id)
        if notification is None or attempt is None or notification.status != "processing" or attempt.status != "started":
            return
        read_db.expunge(notification)
    finally:
        read_db.close()

    try:
        provider_id = sender(notification)
    except Exception as exc:
        now = datetime.now(UTC)
        error_text = safe_error(exc)
        db = session_factory()
        try:
            record = db.scalar(select(NotificationOutbox).where(
                NotificationOutbox.id == notification_id
            ).with_for_update())
            attempt = db.get(NotificationAttempt, attempt_id)
            if record is None or attempt is None or record.status != "processing" or attempt.status != "started":
                return
            attempt.status = "failed"
            attempt.error_message = error_text
            attempt.finished_at = now
            record.last_error = error_text
            record.locked_until = None
            if record.attempt_count >= record.max_attempts:
                record.status = "dead"
            else:
                backoff = min(3600, 30 * (2 ** (attempt.attempt_number - 1)))
                delay = max(1, int(backoff * random.uniform(0.8, 1.2)))
                record.status = "queued"
                record.next_attempt_at = now + timedelta(seconds=delay)
            db.commit()
        finally:
            db.close()
        return

    now = datetime.now(UTC)
    db = session_factory()
    try:
        record = db.scalar(select(NotificationOutbox).where(
            NotificationOutbox.id == notification_id
        ).with_for_update())
        attempt = db.get(NotificationAttempt, attempt_id)
        if record is None or attempt is None or record.status != "processing" or attempt.status != "started":
            return
        record.status = "sent"
        record.sent_at = now
        record.provider_message_id = provider_id
        record.locked_until = None
        record.last_error = None
        attempt.status = "sent"
        attempt.provider_message_id = provider_id
        attempt.finished_at = now
        db.commit()
    finally:
        db.close()


def run_once(
    session_factory: SessionFactory = SessionLocal,
    *,
    sender: Sender = send_smtp_notification,
    batch_size: int = 10,
) -> int:
    db = session_factory()
    try:
        claimed = claim_due_notifications(db, batch_size=batch_size)
    finally:
        db.close()
    for notification_id, attempt_id in claimed:
        deliver_claimed(session_factory, notification_id, attempt_id, sender)
    return len(claimed)


def run_forever(poll_seconds: int | None = None) -> None:
    interval = poll_seconds or get_settings().notification_poll_seconds
    while True:
        try:
            if run_once() == 0:
                time.sleep(interval)
        except KeyboardInterrupt:
            logger.info("Notification worker shutting down")
            return
        except Exception:
            logger.exception("Notification worker iteration failed")
            time.sleep(interval)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_forever()
