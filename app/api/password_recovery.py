import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import DomainError
from app.core.security import hash_password, verify_password
from app.db.session import get_db
from app.models import AuthSession, Company, NotificationOutbox, PasswordResetToken, User
from app.password_recovery_schemas import PasswordRecoveryConfirm, PasswordRecoveryRequest

router = APIRouter(prefix="/auth", tags=["authentication"])
RECOVERY_MESSAGE = "If an account exists for this email, password reset instructions will be sent."
INVALID_TOKEN_MESSAGE = "The password reset token is invalid or expired."


def utc_value(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


@router.post("/forgot-password", status_code=202)
def request_password_recovery(
    payload: PasswordRecoveryRequest,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Enqueue a reset email without revealing whether an account exists."""
    settings = get_settings()
    now = datetime.now(UTC)
    email = str(payload.email).lower()
    user = db.scalar(
        select(User)
        .where(User.email == email)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if user is None or not user.is_active:
        return {"message": RECOVERY_MESSAGE}
    company = db.get(Company, user.company_id)
    if company is None or not company.is_active:
        return {"message": RECOVERY_MESSAGE}

    cooldown_start = now - timedelta(seconds=max(0, settings.password_reset_cooldown_seconds))
    recent_request = db.scalar(
        select(PasswordResetToken.id)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.created_at >= cooldown_start,
        )
        .limit(1)
    )
    if recent_request is not None:
        return {"message": RECOVERY_MESSAGE}

    current_tokens = db.scalars(
        select(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.revoked_at.is_(None),
        )
        .with_for_update()
    ).all()
    for old_token in current_tokens:
        old_token.revoked_at = now

    raw_token = secrets.token_urlsafe(32)
    expiry = now + timedelta(minutes=max(1, settings.password_reset_token_minutes))
    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
        expires_at=expiry,
    )
    db.add(reset_token)
    db.flush()

    separator = "&" if "?" in settings.password_reset_url else "?"
    reset_url = f"{settings.password_reset_url}{separator}{urlencode({'token': raw_token})}"
    subject = "Reset your Service Agreement Manager password"
    body = (
        "A password reset was requested for your account.\n\n"
        f"Use this link within {max(1, settings.password_reset_token_minutes)} minutes:\n"
        f"{reset_url}\n\n"
        "If you did not request this change, you can ignore this email."
    )
    notification_payload = {
        "purpose": "password_reset",
        "reset_token_id": str(reset_token.id),
        "expires_at": expiry.isoformat(),
    }
    fingerprint_source = json.dumps(
        {"subject": subject, "body": body, "payload": notification_payload},
        sort_keys=True,
        separators=(",", ":"),
    )
    db.add(NotificationOutbox(
        company_id=user.company_id,
        created_by_user_id=None,
        event_type="auth.password_reset",
        channel="email",
        recipient_email=user.email,
        subject=subject,
        body=body,
        payload=notification_payload,
        idempotency_key=f"password-reset:{reset_token.id}",
        request_fingerprint=hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest(),
        status="queued",
        scheduled_at=now,
        next_attempt_at=now,
        attempt_count=0,
        max_attempts=settings.notification_default_max_attempts,
    ))
    db.commit()
    return {"message": RECOVERY_MESSAGE}


@router.post("/reset-password", status_code=204)
def complete_password_recovery(
    payload: PasswordRecoveryConfirm,
    db: Session = Depends(get_db),
) -> Response:
    digest = hashlib.sha256(payload.token.encode("utf-8")).hexdigest()
    token_hint = db.scalar(
        select(PasswordResetToken)
        .where(PasswordResetToken.token_hash == digest)
        .limit(1)
    )
    if token_hint is None:
        raise DomainError(400, "invalid_reset_token", INVALID_TOKEN_MESSAGE)

    # Lock in a consistent order (user, then reset token, then sessions) to
    # serialize concurrent recovery requests and avoid lock-order deadlocks.
    user = db.scalar(
        select(User)
        .where(User.id == token_hint.user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if user is None or not user.is_active:
        raise DomainError(400, "invalid_reset_token", INVALID_TOKEN_MESSAGE)
    company = db.get(Company, user.company_id)
    if company is None or not company.is_active:
        raise DomainError(400, "invalid_reset_token", INVALID_TOKEN_MESSAGE)

    reset_token = db.scalar(
        select(PasswordResetToken)
        .where(
            PasswordResetToken.id == token_hint.id,
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.token_hash == digest,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    now = datetime.now(UTC)
    if (
        reset_token is None
        or reset_token.used_at is not None
        or reset_token.revoked_at is not None
        or utc_value(reset_token.expires_at) <= now
    ):
        raise DomainError(400, "invalid_reset_token", INVALID_TOKEN_MESSAGE)
    if verify_password(payload.new_password, user.password_hash):
        raise DomainError(409, "password_unchanged", "New password must differ from the current password")

    user.password_hash = hash_password(payload.new_password)
    reset_token.used_at = now
    other_tokens = db.scalars(
        select(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.id != reset_token.id,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.revoked_at.is_(None),
        )
        .with_for_update()
    ).all()
    for other_token in other_tokens:
        other_token.revoked_at = now

    sessions = db.scalars(
        select(AuthSession)
        .where(
            AuthSession.user_id == user.id,
            AuthSession.revoked_at.is_(None),
        )
        .with_for_update()
    ).all()
    for session in sessions:
        session.revoked_at = now
    db.commit()
    return Response(status_code=204)
