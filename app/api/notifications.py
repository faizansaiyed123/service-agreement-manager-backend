import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.config import get_settings
from app.core.errors import DomainError
from app.db.session import get_db
from app.models import NotificationAttempt, NotificationOutbox, User
from app.notification_schemas import NotificationAttemptRead, NotificationCreate, NotificationRead

router = APIRouter(prefix="/notifications", tags=["notifications"])
MANAGER_ROLES = ("owner", "admin", "manager", "staff")


def fingerprint(payload: NotificationCreate) -> str:
    canonical = json.dumps(payload.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def scoped_notification(db: Session, company_id: UUID, notification_id: UUID) -> NotificationOutbox:
    record = db.scalar(select(NotificationOutbox).where(
        NotificationOutbox.id == notification_id,
        NotificationOutbox.company_id == company_id,
    ))
    if record is None or record.event_type == "auth.password_reset":
        raise DomainError(404, "notification_not_found", "Notification not found")
    return record


def find_by_key(db: Session, company_id: UUID, key: str, digest: str) -> NotificationOutbox | None:
    record = db.scalar(select(NotificationOutbox).where(
        NotificationOutbox.company_id == company_id,
        NotificationOutbox.idempotency_key == key,
    ))
    if record and record.request_fingerprint != digest:
        raise DomainError(409, "idempotency_key_reused", "This Idempotency-Key was used for different notification content")
    return record


@router.post("", response_model=NotificationRead, status_code=201)
def enqueue_notification(
    payload: NotificationCreate,
    response: Response,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=128),
    user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: Session = Depends(get_db),
) -> NotificationOutbox:
    digest = fingerprint(payload)
    existing = find_by_key(db, user.company_id, idempotency_key, digest)
    if existing is not None:
        response.status_code = 200
        return existing
    now = datetime.now(UTC)
    scheduled = payload.scheduled_at.astimezone(UTC) if payload.scheduled_at else now
    record = NotificationOutbox(
        company_id=user.company_id, created_by_user_id=user.id, event_type=payload.event_type,
        channel="email", recipient_email=str(payload.recipient_email).lower(),
        subject=payload.subject, body=payload.body, payload=payload.payload,
        idempotency_key=idempotency_key, request_fingerprint=digest, status="queued",
        scheduled_at=scheduled, next_attempt_at=max(scheduled, now), attempt_count=0,
        max_attempts=get_settings().notification_default_max_attempts,
    )
    db.add(record)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = find_by_key(db, user.company_id, idempotency_key, digest)
        if existing is not None:
            response.status_code = 200
            return existing
        raise DomainError(409, "notification_conflict", "Notification conflicted with another write; retry with the same key") from None
    db.refresh(record)
    return record


@router.get("", response_model=list[NotificationRead])
def list_notifications(
    status: str | None = Query(default=None, pattern="^(queued|processing|sent|dead)$"),
    event_type: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[NotificationOutbox]:
    stmt = select(NotificationOutbox).where(
        NotificationOutbox.company_id == user.company_id,
        NotificationOutbox.event_type != "auth.password_reset",
    )
    if status:
        stmt = stmt.where(NotificationOutbox.status == status)
    if event_type:
        stmt = stmt.where(NotificationOutbox.event_type == event_type)
    return list(db.scalars(stmt.order_by(NotificationOutbox.created_at.desc(), NotificationOutbox.id).limit(limit).offset(offset)).all())


@router.get("/{notification_id}", response_model=NotificationRead)
def get_notification(
    notification_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> NotificationOutbox:
    return scoped_notification(db, user.company_id, notification_id)


@router.get("/{notification_id}/attempts", response_model=list[NotificationAttemptRead])
def list_attempts(
    notification_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[NotificationAttempt]:
    notification = scoped_notification(db, user.company_id, notification_id)
    return list(db.scalars(select(NotificationAttempt).where(
        NotificationAttempt.notification_id == notification.id
    ).order_by(NotificationAttempt.attempt_number)).all())


@router.post("/{notification_id}/retry", response_model=NotificationRead)
def retry_dead_notification(
    notification_id: UUID,
    user: User = Depends(require_roles("owner", "admin", "manager")),
    db: Session = Depends(get_db),
) -> NotificationOutbox:
    record = db.scalar(select(NotificationOutbox).where(
        NotificationOutbox.id == notification_id,
        NotificationOutbox.company_id == user.company_id,
        NotificationOutbox.event_type != "auth.password_reset",
    ).with_for_update())
    if record is None:
        raise DomainError(404, "notification_not_found", "Notification not found")
    if record.status != "dead":
        raise DomainError(409, "notification_not_dead", "Only dead-letter notifications can be retried")
    if record.attempt_count >= 10:
        raise DomainError(409, "notification_retry_limit", "Maximum lifetime attempts have been reached")
    record.max_attempts = min(10, max(record.max_attempts, record.attempt_count + 3))
    record.status = "queued"
    record.next_attempt_at = datetime.now(UTC)
    record.locked_until = None
    db.commit()
    db.refresh(record)
    return record
