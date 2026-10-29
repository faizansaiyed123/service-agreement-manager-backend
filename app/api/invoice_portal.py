import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_roles
from app.core.config import get_settings
from app.core.errors import DomainError
from app.core.rate_limit import enforce_rate_limit
from app.db.session import get_db
from app.models import (
    Company,
    Contact,
    Customer,
    Invoice,
    InvoicePortalToken,
    NotificationOutbox,
    User,
)
from app.schemas.invoice_portal import (
    InvoicePortalPaymentConfirm,
    InvoicePortalPaymentIntentRead,
    InvoicePortalPaymentIntentRequest,
    InvoicePortalRead,
    InvoicePortalSend,
    InvoicePortalSendRead,
)

router = APIRouter(prefix="/invoice-portal", tags=["invoice-portal"])


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def portal_url(raw_token: str) -> str:
    base = get_settings().invoice_portal_url.rstrip("/")
    return f"{base}/{quote(raw_token, safe='')}"


def now_utc() -> datetime:
    return datetime.now(UTC)


def utc_datetime(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return utc_datetime(value).isoformat()


def private_response(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"


def lookup_token(db: Session, raw_token: str, *, for_update: bool = False):
    token_hash = hash_token(raw_token)
    stmt = (
        select(InvoicePortalToken, Invoice, Company, Customer)
        .join(Invoice, InvoicePortalToken.invoice_id == Invoice.id)
        .join(Company, InvoicePortalToken.company_id == Company.id)
        .join(Customer, Invoice.customer_id == Customer.id)
        .options(selectinload(Invoice.lines))
        .where(
            InvoicePortalToken.token_hash == token_hash,
            Invoice.company_id == InvoicePortalToken.company_id,
            Customer.company_id == Invoice.company_id,
        )
    )
    if for_update:
        stmt = stmt.with_for_update()
    return db.execute(stmt).first()


def require_invoice_token(
    db: Session,
    raw_token: str,
    request: Request,
    *,
    for_update: bool = False,
):
    # Apply an IP limit before lookup as well, including for invalid token guesses.
    enforce_rate_limit(
        request,
        scope="invoice-portal-public-ip",
        limit=120,
        window_seconds=300,
    )
    row = lookup_token(db, raw_token, for_update=for_update)
    if row is None:
        raise DomainError(404, "invoice_link_not_found", "This invoice link is invalid or unavailable")

    token, invoice, company, customer = row
    token_hash = hash_token(raw_token)
    is_read = request.method == "GET"
    enforce_rate_limit(
        request,
        scope="invoice-portal-public",
        limit=60 if is_read else 8,
        window_seconds=300 if is_read else 900,
        subject=token_hash,
    )

    if not company.is_active:
        raise DomainError(404, "invoice_link_not_found", "This invoice link is invalid or unavailable")

    now = now_utc()
    if utc_datetime(token.expires_at) <= now:
        if token.status not in {"revoked", "expired"}:
            token.status = "expired"
            token.used_at = now
            db.commit()
        raise DomainError(
            410,
            "invoice_link_expired",
            "This invoice payment link has expired. Contact the service provider for a new link.",
        )
    if token.status in {"revoked", "expired"}:
        raise DomainError(410, "invoice_link_unavailable", "This invoice payment link is no longer available")
    if token.status not in {"pending", "paid"}:
        raise DomainError(410, "invoice_link_unavailable", "This invoice payment link is no longer available")
    return token, invoice, company, customer


def invoice_portal_view(
    db: Session,
    token: InvoicePortalToken,
    invoice: Invoice,
    company: Company,
    customer: Customer,
) -> InvoicePortalRead:
    from app.api.billing import invoice_response

    summary = invoice_response(db, invoice)
    return InvoicePortalRead(
        invoice_number=invoice.invoice_number,
        company_name=company.name,
        customer_name=customer.name,
        recipient_name=token.recipient_name,
        recipient_email=token.recipient_email,
        invoice_date=invoice.invoice_date.isoformat(),
        due_date=invoice.due_date.isoformat(),
        issued_at=iso(invoice.issued_at),
        currency=invoice.currency,
        status=invoice.status,
        subtotal=str(summary.subtotal),
        discount_amount=str(summary.discount_amount),
        tax_amount=str(summary.tax_amount),
        total_amount=str(summary.total_amount),
        amount_paid=str(summary.amount_paid),
        amount_refunded=str(summary.amount_refunded),
        credits_applied=str(summary.credits_applied),
        balance_due=str(summary.balance_due),
        notes=invoice.notes,
        expires_at=iso(token.expires_at) or "",
        portal_status="paid" if token.status == "paid" or summary.balance_due <= Decimal("0.00") else "payable",
        lines=[
            {
                "service_code": line.service_code,
                "description": line.description,
                "details": line.details,
                "quantity": str(line.quantity),
                "unit_price": str(line.unit_price),
                "line_total": str(line.line_total),
            }
            for line in invoice.lines
        ],
    )


def build_email_body(
    *,
    company_name: str,
    invoice: Invoice,
    recipient_name: str,
    recipient_email: str,
    balance_due: Decimal,
    url: str,
    expires_at: datetime,
) -> str:
    return (
        f"Hello {recipient_name},\n\n"
        f"{company_name} has sent you invoice {invoice.invoice_number}.\n\n"
        f"Invoice date: {invoice.invoice_date.isoformat()}\n"
        f"Due date: {invoice.due_date.isoformat()}\n"
        f"Outstanding balance: {invoice.currency} {balance_due:,.2f}\n"
        f"Billing contact: {recipient_email}\n\n"
        f"Review the invoice and pay securely by card using this link:\n{url}\n\n"
        f"This secure payment link expires at {iso(expires_at)}.\n"
        "Do not forward the link. If you were not expecting this invoice, contact the service provider.\n"
    )


@router.post("/invoices/{invoice_id}/send", response_model=InvoicePortalSendRead)
def send_invoice_portal(
    invoice_id: UUID,
    payload: InvoicePortalSend,
    request: Request,
    user: User = Depends(require_roles("owner", "admin", "manager", "billing")),
    db: Session = Depends(get_db),
) -> InvoicePortalSendRead:
    enforce_rate_limit(
        request,
        scope="invoice-portal-send",
        limit=5,
        window_seconds=3600,
        subject=f"{user.id}:{invoice_id}",
    )

    invoice = db.scalar(
        select(Invoice)
        .options(selectinload(Invoice.lines))
        .where(Invoice.id == invoice_id, Invoice.company_id == user.company_id)
        .with_for_update()
    )
    if invoice is None:
        raise DomainError(404, "invoice_not_found", "Invoice not found")
    if invoice.status not in {"issued", "partially_paid"}:
        raise DomainError(
            409,
            "invoice_not_payable",
            "Only issued invoices with an outstanding balance can be sent for payment",
        )

    from app.api.billing import event, invoice_response

    summary = invoice_response(db, invoice)
    if summary.balance_due <= Decimal("0.00"):
        raise DomainError(409, "invoice_balance_zero", "This invoice has no outstanding balance")

    customer = db.scalar(
        select(Customer).where(
            Customer.id == invoice.customer_id,
            Customer.company_id == user.company_id,
            Customer.status == "active",
        )
    )
    company = db.scalar(
        select(Company).where(Company.id == user.company_id, Company.is_active.is_(True))
    )
    if customer is None or company is None:
        raise DomainError(409, "invoice_relationship_invalid", "The invoice customer or company is no longer available")

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
        raise DomainError(
            422,
            "recipient_email_missing",
            "Add an email address to the customer or select a billing contact with an email address",
        )

    now = now_utc()
    settings = get_settings()
    existing = db.scalar(
        select(InvoicePortalToken)
        .where(
            InvoicePortalToken.invoice_id == invoice.id,
            InvoicePortalToken.status == "pending",
            InvoicePortalToken.expires_at > now,
        )
        .order_by(InvoicePortalToken.sent_at.desc())
    )
    if existing is not None and (
        now - utc_datetime(existing.sent_at)
    ).total_seconds() < settings.invoice_portal_send_cooldown_seconds:
        notification = db.get(NotificationOutbox, existing.notification_id) if existing.notification_id else None
        same_recipient = (
            existing.recipient_email == str(recipient_email).lower()
            and existing.recipient_name == recipient_name.strip()
        )
        same_balance = str((notification.payload or {}).get("balance_due")) == str(summary.balance_due) if notification else False
        if notification is not None and notification.status != "dead" and same_recipient and same_balance:
            return InvoicePortalSendRead(
                notification_id=notification.id,
                notification_status=notification.status,
                recipient_name=existing.recipient_name,
                recipient_email=existing.recipient_email,
                balance_due=str(summary.balance_due),
                expires_at=iso(existing.expires_at) or "",
            )

    db.execute(
        update(InvoicePortalToken)
        .where(
            InvoicePortalToken.invoice_id == invoice.id,
            InvoicePortalToken.status == "pending",
        )
        .values(status="revoked", used_at=now)
    )

    raw_token = secrets.token_urlsafe(48)
    token_record = InvoicePortalToken(
        company_id=user.company_id,
        invoice_id=invoice.id,
        recipient_name=recipient_name.strip(),
        recipient_email=str(recipient_email).lower(),
        token_hash=hash_token(raw_token),
        status="pending",
        expires_at=now + timedelta(minutes=settings.invoice_portal_token_minutes),
        sent_at=now,
    )
    db.add(token_record)
    db.flush()

    notification = NotificationOutbox(
        company_id=user.company_id,
        created_by_user_id=user.id,
        event_type="invoice.ready_for_payment",
        channel="email",
        recipient_email=token_record.recipient_email,
        subject=f"Invoice {invoice.invoice_number} is ready for payment",
        body=build_email_body(
            company_name=company.name,
            invoice=invoice,
            recipient_name=token_record.recipient_name,
            recipient_email=token_record.recipient_email,
            balance_due=summary.balance_due,
            url=portal_url(raw_token),
            expires_at=token_record.expires_at,
        ),
        payload={
            "invoice_id": str(invoice.id),
            "invoice_number": invoice.invoice_number,
            "invoice_portal_token_id": str(token_record.id),
            "balance_due": str(summary.balance_due),
        },
        idempotency_key=f"invoice-portal:{token_record.id}",
        request_fingerprint=hashlib.sha256(
            f"{invoice.id}:{token_record.id}:{token_record.recipient_email}".encode()
        ).hexdigest(),
        status="queued",
        scheduled_at=now,
        next_attempt_at=now,
        attempt_count=0,
        max_attempts=settings.notification_default_max_attempts,
    )
    db.add(notification)
    db.flush()
    token_record.notification_id = notification.id
    event(
        db,
        invoice,
        user.id,
        "invoice.payment_link_sent",
        invoice.status,
        {
            "recipient_email": token_record.recipient_email,
            "invoice_portal_token_id": str(token_record.id),
            "notification_id": str(notification.id),
        },
    )
    db.commit()

    return InvoicePortalSendRead(
        notification_id=notification.id,
        notification_status=notification.status,
        recipient_name=token_record.recipient_name,
        recipient_email=token_record.recipient_email,
        balance_due=str(summary.balance_due),
        expires_at=iso(token_record.expires_at) or "",
    )


@router.get("/public/{raw_token}", response_model=InvoicePortalRead)
def get_public_invoice(
    raw_token: str,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> InvoicePortalRead:
    private_response(response)
    token, invoice, company, customer = require_invoice_token(
        db, raw_token, request, for_update=True
    )

    from app.api.billing import invoice_response

    summary = invoice_response(db, invoice)
    if invoice.status in {"void", "draft"}:
        token.status = "revoked"
        token.used_at = now_utc()
        db.commit()
        raise DomainError(410, "invoice_no_longer_payable", "This invoice is no longer available through this link")

    if summary.balance_due <= Decimal("0.00"):
        if token.status == "pending":
            token.status = "paid"
            token.used_at = now_utc()
    elif token.status == "paid":
        # A later refund can reopen the balance, but this spent link must not become
        # payable again. The admin must send a fresh link for the remaining balance.
        raise DomainError(
            410,
            "invoice_link_balance_changed",
            "This invoice balance changed after the payment link was used. Contact the service provider for a new link.",
        )
    elif invoice.status not in {"issued", "partially_paid"}:
        token.status = "revoked"
        token.used_at = now_utc()
        db.commit()
        raise DomainError(410, "invoice_no_longer_payable", "This invoice is no longer available through this link")

    token.last_viewed_at = now_utc()
    db.commit()
    return invoice_portal_view(db, token, invoice, company, customer)


@router.post(
    "/public/{raw_token}/payment-intent",
    response_model=InvoicePortalPaymentIntentRead,
)
def create_public_payment_intent(
    raw_token: str,
    payload: InvoicePortalPaymentIntentRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> InvoicePortalPaymentIntentRead:
    private_response(response)
    token, invoice, company, _ = require_invoice_token(
        db, raw_token, request, for_update=True
    )
    if token.status != "pending":
        raise DomainError(409, "invoice_not_payable", "This invoice no longer has an active payment link")

    invoice = db.scalar(
        select(Invoice)
        .options(selectinload(Invoice.lines))
        .where(Invoice.id == invoice.id, Invoice.company_id == token.company_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if invoice is None:
        raise DomainError(404, "invoice_not_found", "Invoice not found")
    if invoice.status not in {"issued", "partially_paid"}:
        raise DomainError(409, "invoice_not_payable", "Only issued invoices with outstanding balances can accept payments")

    from app.api.billing import invoice_response
    from app.services.stripe_service import create_payment_intent, stripe_enabled

    if not stripe_enabled():
        raise DomainError(503, "stripe_not_configured", "Stripe online payments are not configured")

    balance_due = invoice_response(db, invoice).balance_due
    if balance_due <= Decimal("0.00"):
        token.status = "paid"
        token.used_at = now_utc()
        db.commit()
        raise DomainError(409, "invoice_balance_zero", "This invoice has no outstanding balance")

    invoice_version = invoice.updated_at.isoformat() if invoice.updated_at else "initial"
    key_suffix = hashlib.sha256(
        f"{token.id}:{invoice_version}:{balance_due}".encode()
    ).hexdigest()[:32]
    intent = create_payment_intent(
        invoice,
        amount_due=balance_due,
        idempotency_key=f"invoice-portal:{token.id}:{key_suffix}",
        invoice_portal_token_id=str(token.id),
    )
    return InvoicePortalPaymentIntentRead(**intent)


@router.post(
    "/public/{raw_token}/confirm",
    response_model=InvoicePortalRead,
)
def confirm_public_payment(
    raw_token: str,
    payload: InvoicePortalPaymentConfirm,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> InvoicePortalRead:
    private_response(response)
    token, invoice, company, customer = require_invoice_token(
        db, raw_token, request, for_update=True
    )

    from app.services.stripe_service import _client, record_stripe_payment

    client = _client()
    try:
        intent = client.PaymentIntent.retrieve(payload.payment_intent_id)
    except Exception as exc:
        raise DomainError(502, "stripe_verification_failed", "Unable to verify the payment with Stripe") from exc

    metadata = intent.get("metadata", {}) or {}
    if (
        metadata.get("invoice_id") != str(invoice.id)
        or metadata.get("company_id") != str(invoice.company_id)
        or metadata.get("invoice_portal_token_id") != str(token.id)
    ):
        raise DomainError(404, "payment_intent_not_found", "This payment does not belong to the invoice link")

    if token.status != "pending":
        from app.api.billing import invoice_response

        if invoice_response(db, invoice).balance_due <= Decimal("0.00"):
            return invoice_portal_view(db, token, invoice, company, customer)
        raise DomainError(409, "invoice_not_payable", "This invoice payment link is no longer active")

    record_stripe_payment(
        db,
        invoice,
        payload.payment_intent_id,
        idempotency_key=f"stripe:{payload.payment_intent_id}",
        intent_data=intent,
    )
    token = db.scalar(
        select(InvoicePortalToken)
        .where(InvoicePortalToken.id == token.id)
        .execution_options(populate_existing=True)
    )
    invoice = db.scalar(
        select(Invoice)
        .options(selectinload(Invoice.lines))
        .where(Invoice.id == invoice.id, Invoice.company_id == company.id)
        .execution_options(populate_existing=True)
    )
    if token is None or invoice is None:
        raise DomainError(404, "invoice_link_not_found", "This invoice link is invalid or unavailable")
    return invoice_portal_view(db, token, invoice, company, customer)
