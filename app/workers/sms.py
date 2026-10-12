import logging
import random
import time
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import SmsAttempt, SmsOutbox

logger = logging.getLogger(__name__)


class SmsDeliveryError(RuntimeError):
    pass


def send_sms(sms: SmsOutbox) -> str:
    settings = get_settings()
    if settings.sms_provider != "http" or not settings.sms_api_url or not settings.sms_from:
        raise SmsDeliveryError("SMS HTTP provider is not configured")
    headers = {"Content-Type": "application/json"}
    if settings.sms_api_token:
        headers["Authorization"] = f"Bearer {settings.sms_api_token}"
    response = httpx.post(
        settings.sms_api_url,
        json={
            "to": sms.recipient_phone,
            "from": settings.sms_from,
            "body": sms.body,
        },
        headers=headers,
        timeout=settings.sms_timeout_seconds,
    )
    if not 200 <= response.status_code < 300:
        raise SmsDeliveryError(f"SMS provider returned HTTP {response.status_code}: {response.text[:1000]}")
    body = response.json() if response.content else {}
    return str(body.get("id") or body.get("message_id") or "")


def run_once(session_factory=SessionLocal, *, sender=send_sms, batch_size: int = 10) -> int:
    db: Session = session_factory()
    now = datetime.now(UTC)
    claimed: list[tuple[SmsOutbox, SmsAttempt]] = []
    try:
        rows = list(db.scalars(select(SmsOutbox).where(or_(
            and_(SmsOutbox.status == "queued", SmsOutbox.next_attempt_at <= now),
            and_(SmsOutbox.status == "processing", SmsOutbox.locked_until <= now),
        )).order_by(SmsOutbox.next_attempt_at, SmsOutbox.created_at).with_for_update(skip_locked=True).limit(batch_size)).all())
        for sms in rows:
            if sms.attempt_count >= sms.max_attempts:
                sms.status = "dead"
                continue
            sms.attempt_count += 1
            sms.status = "processing"
            sms.locked_until = now + timedelta(seconds=get_settings().notification_lease_seconds)
            attempt = SmsAttempt(sms_id=sms.id, attempt_number=sms.attempt_count, status="started", started_at=now)
            db.add(attempt)
            db.flush()
            claimed.append((sms, attempt))
        db.commit()
    finally:
        db.close()

    for sms, attempt in claimed:
        try:
            message_id = sender(sms)
        except Exception as exc:
            db = session_factory()
            try:
                current = db.scalar(select(SmsOutbox).where(SmsOutbox.id == sms.id).with_for_update())
                current_attempt = db.get(SmsAttempt, attempt.id)
                if current is None or current_attempt is None:
                    return len(claimed)
                now = datetime.now(UTC)
                current_attempt.status = "failed"
                current_attempt.error_message = f"{type(exc).__name__}: {exc}"[:1000]
                current_attempt.finished_at = now
                current.last_error = current_attempt.error_message
                current.locked_until = None
                if current.attempt_count >= current.max_attempts:
                    current.status = "dead"
                else:
                    delay = min(3600, 30 * (2 ** (current.attempt_count - 1)))
                    current.status = "queued"
                    current.next_attempt_at = now + timedelta(seconds=max(1, int(delay * random.uniform(.8,1.2))))
                db.commit()
            finally:
                db.close()
            continue

        db = session_factory()
        try:
            current = db.scalar(select(SmsOutbox).where(SmsOutbox.id == sms.id).with_for_update())
            current_attempt = db.get(SmsAttempt, attempt.id)
            if current is None or current_attempt is None:
                continue
            now = datetime.now(UTC)
            current.status = "sent"
            current.sent_at = now
            current.provider_message_id = message_id or None
            current.locked_until = None
            current.last_error = None
            current_attempt.status = "sent"
            current_attempt.provider_message_id = message_id or None
            current_attempt.finished_at = now
            db.commit()
        finally:
            db.close()

    return len(claimed)


def run_forever() -> None:
    while True:
        try:
            run_once()
        except KeyboardInterrupt:
            return
        except Exception:
            logger.exception("SMS worker iteration failed")
        time.sleep(get_settings().notification_poll_seconds)
