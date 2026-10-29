import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal
from urllib.parse import quote
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, require_roles
from app.core.config import get_settings
from app.core.errors import DomainError
from app.core.rate_limit import enforce_rate_limit
from app.db.session import get_db
from app.models import Agreement, AgreementEvent, AgreementPortalToken, Company, Contact, Customer, NotificationOutbox, ServiceLocation, User
from app.schemas.agreement_portal import AgreementPortalRead, AgreementPortalResponse, AgreementPortalSend, AgreementPortalSendRead

router = APIRouter(prefix="/agreement-portal", tags=["agreement-portal"])


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def portal_url(raw_token: str) -> str:
    base = get_settings().agreement_portal_url.rstrip("/")
    return f"{base}/{quote(raw_token, safe='')}"


def now_utc() -> datetime:
    return datetime.now(UTC)


def iso(value: datetime | None) -> str | None:
    return value.astimezone(UTC).isoformat() if value else None


def agreement_portal_view(
    token: AgreementPortalToken,
    agreement: Agreement,
    company: Company,
    customer: Customer,
    location: ServiceLocation,
) -> AgreementPortalRead:
    if token.status in {"accepted", "rejected"}:
        portal_status = token.status
    elif agreement.status == "proposed" and agreement.version_number == token.agreement_version:
        portal_status = "pending"
    else:
        portal_status = "unavailable"

    return AgreementPortalRead(
        agreement_number=agreement.agreement_number,
        title=agreement.title,
        company_name=company.name,
        customer_name=customer.name,
        recipient_name=token.recipient_name,
        recipient_email=token.recipient_email,
        service_location_name=location.name,
        service_location_city=location.city,
        service_location_region=location.region,
        service_location_country=location.country_code,
        start_date=agreement.start_date.isoformat(),
        end_date=agreement.end_date.isoformat(),
        billing_frequency=agreement.billing_frequency,
        currency=agreement.currency,
        auto_renew=agreement.auto_renew,
        terms_text=agreement.terms_text,
        total_amount=str(agreement.total_amount),
        version_number=token.agreement_version,
        expires_at=token.expires_at.astimezone(UTC).isoformat(),
        portal_status=portal_status,
        accepted_at=iso(agreement.accepted_at),
        rejected_at=iso(agreement.rejected_at),
        rejection_reason=agreement.rejection_reason,
        lines=[
            {
                "service_code": line.service_code,
                "name": line.name,
                "description": line.description,
                "quantity": str(line.quantity),
                "unit_price": str(line.unit_price),
                "line_total": str(line.line_total),
            }
            for line in agreement.lines
        ],
    )


def lookup_token(db: Session, raw_token: str, *, for_update: bool = False):
    token_hash = hash_token(raw_token)
    stmt = (
        select(AgreementPortalToken, Agreement, Company, Customer, ServiceLocation)
        .join(Agreement, AgreementPortalToken.agreement_id == Agreement.id)
        .join(Company, AgreementPortalToken.company_id == Company.id)
        .join(Customer, Agreement.customer_id == Customer.id)
        .join(ServiceLocation, Agreement.service_location_id == ServiceLocation.id)
        .options(selectinload(Agreement.lines))
        .where(AgreementPortalToken.token_hash == token_hash)
    )
    if for_update:
        stmt = stmt.with_for_update()
    row = db.execute(stmt).first()
    return row, token_hash


def require_pending_token(
    db: Session, raw_token: str, request: Request, *, for_update: bool = False
):
    row, token_hash = lookup_token(db, raw_token, for_update=for_update)
    if row is None:
        raise DomainError(404, "agreement_link_not_found", "This agreement link is invalid or unavailable")
    token, agreement, company, customer, location = row
    enforce_rate_limit(
        request,
        scope="agreement-portal",
        limit=60 if request.method == "GET" else 10,
        window_seconds=300 if request.method == "GET" else 900,
        subject=token_hash,
    )
    now = now_utc()
    if token.status == "pending" and token.expires_at <= now:
        token.status = "expired"
        db.commit()
        raise DomainError(410, "agreement_link_expired", "This agreement link has expired. Ask the provider to send a new link.")
    if token.status == "revoked":
        raise DomainError(410, "agreement_link_revoked", "This agreement link is no longer available")
    return token, agreement, company, customer, location, token_hash


def build_email_body(
    *,
    company_name: str,
    customer_name: str,
    recipient_name: str,
    agreement: Agreement,
    url: str,
    expires_at: datetime,
) -> str:
    amount = f"{agreement.currency} {Decimal(agreement.total_amount):,.2f}"
    return (
        f"Hello {recipient_name},\n\n"
        f"{company_name} has sent {customer_name} a service agreement for your review.\n\n"
        f"Agreement: {agreement.agreement_number}\n"
        f"Title: {agreement.title}\n"
        f"Term: {agreement.start_date.isoformat()} to {agreement.end_date.isoformat()}\n"
        f"Value: {amount}\n"
        f"Billing: {agreement.billing_frequency.replace('_', ' ')}\n\n"
        f"Review and respond to the agreement here:\n{url}\n\n"
        f"This secure link expires at {expires_at.astimezone(UTC).isoformat()}.\n"
        f"Do not forward the link. If you were not expecting this agreement, contact the service provider.\n"
    )


@router.post("/agreements/{agreement_id}/send", response_model=AgreementPortalSendRead)
def send_agreement(
    agreement_id: UUID,
    payload: AgreementPortalSend,
    request: Request,
    user: User = Depends(require_roles("owner", "admin", "manager", "staff")),
    db: Session = Depends(get_db),
) -> AgreementPortalSendRead:
    enforce_rate_limit(
        request,
        scope="agreement-portal-send",
        limit=5,
        window_seconds=3600,
        subject=f"{user.id}:{agreement_id}",
    )
    agreement = db.scalar(
        select(Agreement)
        .options(selectinload(Agreement.lines))
        .where(Agreement.id == agreement_id, Agreement.company_id == user.company_id)
        .with_for_update()
    )
    if agreement is None:
        raise DomainError(404, "agreement_not_found", "Agreement not found")
    if agreement.status != "proposed":
        raise DomainError(409, "agreement_not_proposed", "Only proposed agreements can be sent for electronic acceptance")
    if agreement.version_number <= 0:
        raise DomainError(409, "agreement_version_missing", "The proposed agreement has no saved version")

    customer = db.scalar(
        select(Customer).where(Customer.id == agreement.customer_id, Customer.company_id == user.company_id)
    )
    company = db.get(Company, user.company_id)
    location = db.scalar(
        select(ServiceLocation).where(
            ServiceLocation.id == agreement.service_location_id,
            ServiceLocation.customer_id == agreement.customer_id,
            ServiceLocation.company_id == user.company_id,
        )
    )
    if customer is None or company is None or location is None:
        raise DomainError(409, "agreement_relationship_invalid", "The agreement customer or service location is no longer available")

    recipient_name = customer.name
    recipient_email = customer.email
    if payload.contact_id is not None:
        contact = db.scalar(
            select(Contact).where(
                Contact.id == payload.contact_id,
                Contact.customer_id == customer.id,
                Contact.company_id == user.company_id,
            )
        )
        if contact is None:
            raise DomainError(404, "contact_not_found", "Customer contact not found")
        if not contact.email:
            raise DomainError(422, "contact_email_missing", "The selected customer contact has no email address")
        recipient_name = contact.full_name
        recipient_email = contact.email
    if not recipient_email:
        raise DomainError(422, "recipient_email_missing", "Add an email address to the customer or select a contact with an email address")

    now = now_utc()
    cooldown = get_settings().agreement_portal_send_cooldown_seconds
    existing = db.scalar(
        select(AgreementPortalToken)
        .where(
            AgreementPortalToken.agreement_id == agreement.id,
            AgreementPortalToken.agreement_version == agreement.version_number,
            AgreementPortalToken.status == "pending",
            AgreementPortalToken.expires_at > now,
        )
        .order_by(AgreementPortalToken.sent_at.desc())
    )
    if existing is not None and (now - existing.sent_at).total_seconds() < cooldown:
        notification = db.get(NotificationOutbox, existing.notification_id) if existing.notification_id else None
        if notification is not None and notification.status != "dead":
            return AgreementPortalSendRead(
                notification_id=notification.id,
                notification_status=notification.status,
                recipient_name=existing.recipient_name,
                recipient_email=existing.recipient_email,
                agreement_version=existing.agreement_version,
                expires_at=existing.expires_at.astimezone(UTC).isoformat(),
            )

    db.execute(
        update(AgreementPortalToken)
        .where(
            AgreementPortalToken.agreement_id == agreement.id,
            AgreementPortalToken.status == "pending",
        )
        .values(status="revoked", used_at=now)
    )

    raw_token = secrets.token_urlsafe(48)
    token_record = AgreementPortalToken(
        company_id=user.company_id,
        agreement_id=agreement.id,
        agreement_version=agreement.version_number,
        recipient_name=recipient_name.strip(),
        recipient_email=str(recipient_email).lower(),
        token_hash=hash_token(raw_token),
        status="pending",
        expires_at=now + timedelta(minutes=get_settings().agreement_portal_token_minutes),
        sent_at=now,
    )
    db.add(token_record)
    db.flush()

    destination = portal_url(raw_token)
    notification = NotificationOutbox(
        company_id=user.company_id,
        created_by_user_id=user.id,
        event_type="agreement.proposed_for_acceptance",
        channel="email",
        recipient_email=token_record.recipient_email,
        subject=f"Action required: Service Agreement {agreement.agreement_number}",
        body=build_email_body(
            company_name=company.name,
            customer_name=customer.name,
            recipient_name=token_record.recipient_name,
            agreement=agreement,
            url=destination,
            expires_at=token_record.expires_at,
        ),
        payload={
            "agreement_id": str(agreement.id),
            "agreement_number": agreement.agreement_number,
            "agreement_version": agreement.version_number,
            "portal_token_id": str(token_record.id),
        },
        idempotency_key=f"agreement-portal:{token_record.id}",
        request_fingerprint=hashlib.sha256(
            f"{agreement.id}:{token_record.id}:{token_record.recipient_email}".encode("utf-8")
        ).hexdigest(),
        status="queued",
        scheduled_at=now,
        next_attempt_at=now,
        attempt_count=0,
        max_attempts=get_settings().notification_default_max_attempts,
    )
    db.add(notification)
    db.flush()
    token_record.notification_id = notification.id
    db.add(
        AgreementEvent(
            agreement_id=agreement.id,
            actor_user_id=user.id,
            event_type="agreement.sent_for_acceptance",
            from_status=agreement.status,
            to_status=agreement.status,
            detail={
                "version": agreement.version_number,
                "recipient_email": token_record.recipient_email,
                "portal_token_id": str(token_record.id),
            },
            created_at=now,
        )
    )
    db.commit()

    return AgreementPortalSendRead(
        notification_id=notification.id,
        notification_status=notification.status,
        recipient_name=token_record.recipient_name,
        recipient_email=token_record.recipient_email,
        agreement_version=token_record.agreement_version,
        expires_at=token_record.expires_at.astimezone(UTC).isoformat(),
    )


@router.get("/public/{raw_token}", response_model=AgreementPortalRead)
def get_public_agreement(raw_token: str, request: Request, db: Session = Depends(get_db)) -> AgreementPortalRead:
    token, agreement, company, customer, location, _ = require_pending_token(db, raw_token, request)
    if token.status == "pending":
        if agreement.status != "proposed" or agreement.version_number != token.agreement_version:
            token.status = "revoked"
            token.used_at = now_utc()
            db.commit()
            raise DomainError(410, "agreement_no_longer_actionable", "This agreement is no longer available for response")
        token.last_viewed_at = now_utc()
        db.commit()
    return agreement_portal_view(token, agreement, company, customer, location)


@router.post("/public/{raw_token}/respond", response_model=AgreementPortalRead)
def respond_to_public_agreement(
    raw_token: str,
    payload: AgreementPortalResponse,
    request: Request,
    db: Session = Depends(get_db),
) -> AgreementPortalRead:
    token, agreement, company, customer, location, token_hash = require_pending_token(
        db, raw_token, request, for_update=True
    )
    if token.status == "accepted":
        if payload.decision == "accept":
            return agreement_portal_view(token, agreement, company, customer, location)
        raise DomainError(409, "agreement_already_decided", "This agreement has already been accepted")
    if token.status == "rejected":
        if payload.decision == "reject":
            return agreement_portal_view(token, agreement, company, customer, location)
        raise DomainError(409, "agreement_already_decided", "This agreement has already been rejected")
    if token.status != "pending":
        raise DomainError(410, "agreement_link_unavailable", "This agreement link is no longer available")
    if agreement.status != "proposed" or agreement.version_number != token.agreement_version:
        token.status = "revoked"
        token.used_at = now_utc()
        db.commit()
        raise DomainError(409, "agreement_no_longer_actionable", "This agreement is no longer available for response")

    now = now_utc()
    if payload.decision == "accept":
        agreement.accepted_by_name = token.recipient_name
        agreement.acceptance_method = "electronic"
        agreement.acceptance_reference = f"portal:{token.id}"
        agreement.accepted_at = now
        agreement.status = "active" if agreement.start_date <= now.date() else "accepted"
        event_type = "agreement.accepted"
        detail = {
            "method": "electronic",
            "reference": agreement.acceptance_reference,
            "version": token.agreement_version,
            "recipient_email": token.recipient_email,
            "portal_token_id": str(token.id),
        }
        token.status = "accepted"
    else:
        agreement.status = "rejected"
        agreement.rejected_by_name = token.recipient_name
        agreement.rejected_at = now
        agreement.rejection_reason = payload.rejection_reason
        event_type = "agreement.rejected"
        detail = {
            "method": "electronic",
            "version": token.agreement_version,
            "recipient_email": token.recipient_email,
            "portal_token_id": str(token.id),
            "reason": payload.rejection_reason,
        }
        token.status = "rejected"

    token.used_at = now
    token.decision_ip = request.client.host if request.client else None
    token.decision_user_agent = request.headers.get("user-agent")
    db.execute(
        update(AgreementPortalToken)
        .where(
            AgreementPortalToken.agreement_id == agreement.id,
            AgreementPortalToken.status == "pending",
            AgreementPortalToken.id != token.id,
        )
        .values(status="revoked", used_at=now)
    )
    db.add(
        AgreementEvent(
            agreement_id=agreement.id,
            actor_user_id=None,
            event_type=event_type,
            from_status="proposed",
            to_status=agreement.status,
            detail=detail,
            created_at=now,
        )
    )
    db.commit()
    return agreement_portal_view(token, agreement, company, customer, location)
