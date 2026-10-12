import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.config import get_settings
from app.core.errors import DomainError
from app.db.session import get_db
from app.models import SmsOutbox, User
from app.sms_schemas import SmsCreate, SmsRead

router = APIRouter(prefix="/sms", tags=["sms"])
ROLES = ("owner", "admin", "manager", "staff")


def fingerprint(payload: SmsCreate) -> str:
    canonical = json.dumps(payload.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@router.post("", response_model=SmsRead, status_code=201)
def enqueue_sms(
    payload: SmsCreate,
    response: Response,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=128),
    user: User = Depends(require_roles(*ROLES)),
    db: Session = Depends(get_db),
) -> SmsOutbox:
    settings = get_settings()
    if settings.sms_provider == "disabled":
        raise DomainError(503, "sms_provider_disabled", "SMS delivery is not configured")
    digest = fingerprint(payload)
    existing = db.scalar(select(SmsOutbox).where(
        SmsOutbox.company_id == user.company_id,
        SmsOutbox.idempotency_key == idempotency_key,
    ))
    if existing is not None:
        if existing.request_fingerprint != digest:
            raise DomainError(409, "idempotency_key_reused", "This Idempotency-Key was used for different SMS content")
        response.status_code = 200
        return existing
    now = datetime.now(UTC)
    scheduled = payload.scheduled_at.astimezone(UTC) if payload.scheduled_at else now
    row = SmsOutbox(
        company_id=user.company_id,
        created_by_user_id=user.id,
        event_type=payload.event_type,
        recipient_phone=payload.recipient_phone.strip(),
        body=payload.body,
        payload=payload.payload,
        idempotency_key=idempotency_key,
        request_fingerprint=digest,
        status="queued",
        scheduled_at=scheduled,
        next_attempt_at=max(scheduled, now),
        max_attempts=settings.notification_default_max_attempts,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        existing = db.scalar(select(SmsOutbox).where(
            SmsOutbox.company_id == user.company_id,
            SmsOutbox.idempotency_key == idempotency_key,
        ))
        if existing is not None and existing.request_fingerprint == digest:
            response.status_code = 200
            return existing
        raise DomainError(409, "sms_conflict", "SMS enqueue conflicted with another write") from exc
    db.refresh(row)
    return row


@router.get("", response_model=list[SmsRead])
def list_sms(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SmsOutbox]:
    return list(db.scalars(select(SmsOutbox).where(
        SmsOutbox.company_id == user.company_id
    ).order_by(SmsOutbox.created_at.desc(), SmsOutbox.id).limit(100)).all())
