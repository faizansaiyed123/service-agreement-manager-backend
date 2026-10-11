from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import WebhookDelivery, WebhookEndpoint


def publish_webhook_event(
    db: Session,
    company_id: UUID,
    event_type: str,
    payload: dict,
    *,
    event_id: UUID | None = None,
    max_attempts: int | None = None,
) -> UUID:
    resolved_event_id = event_id or uuid4()
    endpoints = list(db.scalars(select(WebhookEndpoint).where(
        WebhookEndpoint.company_id == company_id,
        WebhookEndpoint.is_active.is_(True),
    )).all())
    now = datetime.now(UTC)
    resolved_max_attempts = max_attempts or get_settings().webhook_default_max_attempts
    for endpoint in endpoints:
        if event_type not in endpoint.subscribed_events:
            continue
        existing = db.scalar(select(WebhookDelivery.id).where(
            WebhookDelivery.endpoint_id == endpoint.id,
            WebhookDelivery.event_id == resolved_event_id,
        ))
        if existing is not None:
            continue
        try:
            with db.begin_nested():
                db.add(WebhookDelivery(
                    company_id=company_id,
                    endpoint_id=endpoint.id,
                    event_id=resolved_event_id,
                    event_type=event_type,
                    payload=payload,
                    status="queued",
                    scheduled_at=now,
                    next_attempt_at=now,
                    max_attempts=max(1, min(resolved_max_attempts, 20)),
                ))
                db.flush()
        except IntegrityError:
            continue
    return resolved_event_id
