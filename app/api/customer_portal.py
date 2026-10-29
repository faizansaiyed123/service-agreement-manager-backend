import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from urllib.parse import quote
from uuid import UUID, uuid4

import jwt
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_roles
from app.core.auth_cookies import (
    CUSTOMER_ACCESS_COOKIE, CUSTOMER_REFRESH_COOKIE,
    clear_customer_portal_cookies, set_customer_portal_cookies,
)
from app.core.config import get_settings
from app.core.errors import DomainError
from app.core.rate_limit import enforce_rate_limit
from app.core.security import create_token, decode_token, hash_password, verify_password
from app.core.storage import build_storage
from app.db.session import get_db
from app.models import (
    Agreement, Attachment, Company, Customer, CustomerPortalIdentity, CustomerPortalInvitation,
    CustomerPortalMembership, CustomerPortalSession, Equipment, Invoice, Payment, PaymentRefund,
    NotificationOutbox, ServiceLocation, User, WorkOrder,
)
from app.schemas.common import AuthenticatedSession, LoginRequest, TokenPair
from app.schemas.customer_portal import (
    CustomerPortalAccept, CustomerPortalAgreementRead, CustomerPortalEquipmentRead,
    CustomerPortalInviteCreate, CustomerPortalInvitePreview, CustomerPortalInviteRead,
    CustomerPortalAccessRead, CustomerPortalAttachmentRead, CustomerPortalPaymentRead, CustomerPortalRefundRead, CustomerPortalPaymentConfirm, CustomerPortalInvoiceRead, CustomerPortalLocationRead, CustomerPortalMe,
    CustomerPortalMembershipRead, CustomerPortalOverview, CustomerPortalPaymentIntentRead,
    CustomerPortalWorkOrderRead,
)
from app.services.invoice_pdf import render_invoice_pdf


router = APIRouter(prefix="/customer-portal", tags=["customer portal"])
_DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(32))


def _hash_token(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _now() -> datetime:
    return datetime.now(UTC)


def _private_response(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"


def _customer_token_pair(identity: CustomerPortalIdentity, company_id: UUID, session_id: UUID) -> tuple[TokenPair, str, datetime]:
    settings = get_settings()
    access, _ = create_token(
        subject=identity.id, company_id=company_id, token_type="customer_access",
        lifetime=timedelta(minutes=settings.access_token_minutes), session_id=session_id,
    )
    refresh, jti = create_token(
        subject=identity.id, company_id=company_id, token_type="customer_refresh",
        lifetime=timedelta(days=settings.refresh_token_days), session_id=session_id,
    )
    return TokenPair(access_token=access, refresh_token=refresh, expires_in=settings.access_token_minutes * 60), jti, _now() + timedelta(days=settings.refresh_token_days)


def _session_response(request: Request, response: Response, pair: TokenPair):
    if request.headers.get("origin"):
        set_customer_portal_cookies(response, pair.access_token, pair.refresh_token)
        return AuthenticatedSession(expires_in=pair.expires_in)
    return pair


def _has_active_membership(db: Session, identity_id: UUID) -> bool:
    return db.scalar(
        select(CustomerPortalMembership.id)
        .join(Company, Company.id == CustomerPortalMembership.company_id)
        .join(Customer, Customer.id == CustomerPortalMembership.customer_id)
        .where(
            CustomerPortalMembership.portal_user_id == identity_id,
            CustomerPortalMembership.is_active.is_(True),
            Company.is_active.is_(True),
            Customer.status == "active",
        )
        .limit(1)
    ) is not None


def get_customer_identity(request: Request, db: Session = Depends(get_db)) -> CustomerPortalIdentity:
    browser_request = bool(request.headers.get("origin") or request.headers.get("sec-fetch-site"))
    token = request.cookies.get(CUSTOMER_ACCESS_COOKIE)
    if not browser_request and not token:
        # Allow explicit bearer tokens for non-browser API clients; browser requests must use HttpOnly cookies.
        authorization = request.headers.get("authorization", "")
        if authorization.lower().startswith("bearer "):
            token = authorization[7:].strip()
    if not token:
        raise DomainError(401, "customer_login_required", "Sign in to your customer portal to continue")
    try:
        claims = decode_token(token)
        if claims.get("typ") != "customer_access":
            raise ValueError("wrong token type")
        identity_id = UUID(str(claims["sub"]))
        session_id = UUID(str(claims["sid"]))
    except (jwt.PyJWTError, ValueError, KeyError, TypeError):
        raise DomainError(401, "invalid_customer_session", "Your customer portal session is invalid or expired") from None
    session = db.get(CustomerPortalSession, session_id)
    if session is None or session.portal_user_id != identity_id or session.revoked_at is not None:
        raise DomainError(401, "invalid_customer_session", "Your customer portal session is no longer valid")
    if _utc(session.expires_at) <= _now():
        raise DomainError(401, "invalid_customer_session", "Your customer portal session has expired")
    identity = db.get(CustomerPortalIdentity, identity_id)
    if identity is None or not identity.is_active or not _has_active_membership(db, identity.id):
        raise DomainError(401, "invalid_customer_session", "Your customer portal access is no longer active")
    request.state.customer_portal_session_id = session_id
    return identity


def _membership(db: Session, identity: CustomerPortalIdentity, membership_id: UUID):
    row = db.execute(
        select(CustomerPortalMembership, Customer, Company)
        .join(Customer, Customer.id == CustomerPortalMembership.customer_id)
        .join(Company, Company.id == CustomerPortalMembership.company_id)
        .where(
            CustomerPortalMembership.id == membership_id,
            CustomerPortalMembership.portal_user_id == identity.id,
            CustomerPortalMembership.is_active.is_(True),
            Customer.status == "active",
            Company.is_active.is_(True),
            Customer.company_id == Company.id,
        )
    ).first()
    if row is None:
        raise DomainError(404, "customer_portal_resource_not_found", "The requested customer portal resource was not found")
    return row[0], row[1], row[2]


def _portal_invoice(db: Session, invoice: Invoice) -> CustomerPortalInvoiceRead:
    from app.api.billing import invoice_response

    summary = invoice_response(db, invoice)
    return CustomerPortalInvoiceRead(
        id=invoice.id,
        invoice_number=invoice.invoice_number,
        status=invoice.status,
        invoice_date=invoice.invoice_date.isoformat(),
        due_date=invoice.due_date.isoformat(),
        currency=invoice.currency,
        subtotal=summary.subtotal,
        discount_amount=summary.discount_amount,
        tax_amount=summary.tax_amount,
        total_amount=summary.total_amount,
        amount_paid=summary.amount_paid,
        amount_refunded=summary.amount_refunded,
        credits_applied=summary.credits_applied,
        balance_due=summary.balance_due,
        notes=invoice.notes,
        is_overdue=summary.is_overdue,
        lines=[
            {
                "service_code": line.service_code,
                "description": line.description,
                "details": line.details,
                "quantity": line.quantity,
                "unit_price": line.unit_price,
                "line_total": line.line_total,
            }
            for line in invoice.lines
        ],
        portal_status="paid" if summary.balance_due <= Decimal("0.00") else "payable",
    )


@router.post("/customers/{customer_id}/invite", response_model=CustomerPortalInviteRead, status_code=201)
def invite_customer_portal(
    customer_id: UUID,
    payload: CustomerPortalInviteCreate,
    request: Request,
    user: User = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
) -> CustomerPortalInvitation:
    enforce_rate_limit(request, scope="customer-portal-invite-ip", limit=30, window_seconds=3600)
    customer = db.scalar(select(Customer).where(
        Customer.id == customer_id, Customer.company_id == user.company_id,
    ).with_for_update())
    if customer is None or customer.status != "active":
        raise DomainError(404, "customer_not_found", "Active customer not found")
    if not customer.email:
        raise DomainError(422, "customer_email_required", "Add an email address to this customer before inviting them to the portal")
    email = customer.email.strip().lower()
    enforce_rate_limit(request, scope="customer-portal-invite-email", limit=5, window_seconds=3600, subject=f"{user.company_id}:{email}", by_ip=False)

    identity = db.scalar(select(CustomerPortalIdentity).where(CustomerPortalIdentity.email == email))
    if identity is not None:
        existing_membership = db.scalar(select(CustomerPortalMembership.id).where(
            CustomerPortalMembership.portal_user_id == identity.id,
            CustomerPortalMembership.company_id == user.company_id,
            CustomerPortalMembership.customer_id == customer.id,
            CustomerPortalMembership.is_active.is_(True),
        ))
        if existing_membership is not None:
            raise DomainError(409, "customer_portal_already_enabled", "This customer already has active portal access")
    company = db.get(Company, user.company_id)
    if company is None or not company.is_active:
        raise DomainError(403, "company_inactive", "Company account is inactive")

    settings = get_settings()
    now = _now()
    if settings.customer_portal_invitation_cooldown_seconds > 0:
        cutoff = now - timedelta(seconds=settings.customer_portal_invitation_cooldown_seconds)
        recently_sent = db.scalar(select(CustomerPortalInvitation.id).where(
            CustomerPortalInvitation.company_id == user.company_id,
            CustomerPortalInvitation.customer_id == customer.id,
            CustomerPortalInvitation.email == email,
            CustomerPortalInvitation.created_at >= cutoff,
        ).limit(1))
        if recently_sent is not None:
            raise DomainError(429, "customer_portal_invitation_cooldown", "A recent invitation was already sent. Wait before sending another link.")
    for old in db.scalars(select(CustomerPortalInvitation).where(
        CustomerPortalInvitation.company_id == user.company_id,
        CustomerPortalInvitation.customer_id == customer.id,
        CustomerPortalInvitation.email == email,
        CustomerPortalInvitation.status == "pending",
    ).with_for_update()).all():
        old.status = "revoked"

    raw = secrets.token_urlsafe(48)
    expires_at = now + timedelta(minutes=settings.customer_portal_invitation_token_minutes)
    invite = CustomerPortalInvitation(
        company_id=user.company_id, customer_id=customer.id, invited_by_user_id=user.id,
        email=email, full_name=(payload.full_name or customer.name).strip(),
        token_hash=_hash_token(raw), status="pending", expires_at=expires_at,
    )
    db.add(invite)
    db.flush()
    url = f"{settings.customer_portal_invitation_url.rstrip('/')}/{quote(raw, safe='')}"
    body = (
        f"Hello {invite.full_name},\n\n"
        f"{company.name} has invited you to its customer portal for {customer.name}.\n"
        "Use this one-time link to activate portal access. You will create your own password; the service provider will never see it.\n\n"
        f"{url}\n\n"
        f"The invitation expires at {expires_at.isoformat()}. If you were not expecting this, ignore this email."
    )
    db.add(NotificationOutbox(
        company_id=user.company_id, created_by_user_id=user.id,
        event_type="customer.portal_invited", channel="email", recipient_email=email,
        subject=f"Your {company.name} customer portal invitation", body=body,
        payload={"customer_portal_invitation_id": str(invite.id), "customer_id": str(customer.id)},
        idempotency_key=f"customer-portal-invitation:{invite.id}",
        request_fingerprint=hashlib.sha256(f"{invite.id}:{email}".encode()).hexdigest(),
        status="queued", scheduled_at=now, next_attempt_at=now, attempt_count=0,
        max_attempts=settings.notification_default_max_attempts,
    ))
    db.commit()
    db.refresh(invite)
    return invite


@router.get("/invitations/public/{raw_token}", response_model=CustomerPortalInvitePreview)
def preview_customer_invitation(
    raw_token: str, request: Request, response: Response, db: Session = Depends(get_db),
) -> CustomerPortalInvitePreview:
    _private_response(response)
    enforce_rate_limit(request, scope="customer-portal-invite-preview", limit=60, window_seconds=300)
    invite = db.scalar(select(CustomerPortalInvitation).where(CustomerPortalInvitation.token_hash == _hash_token(raw_token)))
    if invite is None or invite.status != "pending":
        raise DomainError(404, "invitation_unavailable", "This customer portal invitation is invalid or unavailable")
    if _utc(invite.expires_at) <= _now():
        invite.status = "expired"
        db.commit()
        raise DomainError(410, "invitation_expired", "This invitation has expired. Ask the service provider to send a new one.")
    company = db.get(Company, invite.company_id)
    customer = db.scalar(select(Customer).where(Customer.id == invite.customer_id, Customer.company_id == invite.company_id))
    if company is None or not company.is_active or customer is None or customer.status != "active" or (customer.email or "").strip().lower() != invite.email:
        raise DomainError(410, "invitation_unavailable", "This customer portal invitation is no longer available")
    return CustomerPortalInvitePreview(email=invite.email, full_name=invite.full_name, company_name=company.name, customer_name=customer.name, expires_at=_utc(invite.expires_at))


@router.post("/invitations/public/{raw_token}/accept", status_code=201)
def accept_customer_invitation(
    raw_token: str,
    payload: CustomerPortalAccept,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenPair | AuthenticatedSession:
    _private_response(response)
    enforce_rate_limit(request, scope="customer-portal-invite-accept-ip", limit=20, window_seconds=900)
    invite = db.scalar(select(CustomerPortalInvitation).where(
        CustomerPortalInvitation.token_hash == _hash_token(raw_token),
    ).with_for_update())
    if invite is None or invite.status != "pending":
        raise DomainError(404, "invitation_unavailable", "This customer portal invitation is invalid or unavailable")
    now = _now()
    if _utc(invite.expires_at) <= now:
        invite.status = "expired"
        db.commit()
        raise DomainError(410, "invitation_expired", "This invitation has expired. Ask the service provider to send a new one.")
    company = db.get(Company, invite.company_id)
    customer = db.scalar(select(Customer).where(
        Customer.id == invite.customer_id, Customer.company_id == invite.company_id,
    ).with_for_update())
    if company is None or not company.is_active or customer is None or customer.status != "active" or (customer.email or "").strip().lower() != invite.email:
        raise DomainError(410, "invitation_unavailable", "This customer portal invitation is no longer available")

    identity = db.scalar(select(CustomerPortalIdentity).where(CustomerPortalIdentity.email == invite.email).with_for_update())
    if identity is not None:
        if not identity.is_active or not verify_password(payload.password, identity.password_hash):
            raise DomainError(401, "existing_portal_account", "An account already exists for this email. Sign in with its existing password, then ask the service provider to issue a fresh invitation if needed.")
    else:
        identity = CustomerPortalIdentity(
            email=invite.email, full_name=payload.full_name.strip(),
            password_hash=hash_password(payload.password), is_active=True,
        )
        db.add(identity)
        db.flush()

    existing_membership = db.scalar(select(CustomerPortalMembership).where(
        CustomerPortalMembership.portal_user_id == identity.id,
        CustomerPortalMembership.company_id == invite.company_id,
        CustomerPortalMembership.customer_id == invite.customer_id,
    ).with_for_update())
    if existing_membership is not None:
        if existing_membership.is_active:
            raise DomainError(409, "customer_portal_already_enabled", "This customer already has active portal access")
        existing_membership.is_active = True
        existing_membership.invited_by_user_id = invite.invited_by_user_id
        membership = existing_membership
    else:
        membership = CustomerPortalMembership(
            portal_user_id=identity.id, company_id=invite.company_id, customer_id=invite.customer_id,
            invited_by_user_id=invite.invited_by_user_id, is_active=True,
        )
        db.add(membership)
        db.flush()

    invite.status = "accepted"
    invite.accepted_at = now
    session_id = uuid4()
    pair, jti, expires_at = _customer_token_pair(identity, invite.company_id, session_id)
    db.add(CustomerPortalSession(portal_user_id=identity.id, id=session_id, refresh_jti=jti, expires_at=expires_at))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise DomainError(409, "invitation_conflict", "This invitation could not be activated. Sign in and ask the service provider for a new invitation.") from None
    return _session_response(request, response, pair)


@router.post("/auth/login")
def customer_login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    _private_response(response)
    email = str(payload.email).strip().lower()
    enforce_rate_limit(request, scope="customer-portal-login-ip", limit=30, window_seconds=60)
    enforce_rate_limit(request, scope="customer-portal-login-email", limit=10, window_seconds=900, subject=email, by_ip=False)
    identity = db.scalar(select(CustomerPortalIdentity).where(CustomerPortalIdentity.email == email))
    matched = verify_password(payload.password, identity.password_hash if identity else _DUMMY_PASSWORD_HASH)
    if identity is None or not matched or not identity.is_active or not _has_active_membership(db, identity.id):
        raise DomainError(401, "invalid_customer_credentials", "Email or password is incorrect, or portal access is no longer active")
    membership_company_id = db.scalar(
        select(CustomerPortalMembership.company_id)
        .join(Company, Company.id == CustomerPortalMembership.company_id)
        .join(Customer, Customer.id == CustomerPortalMembership.customer_id)
        .where(
            CustomerPortalMembership.portal_user_id == identity.id,
            CustomerPortalMembership.is_active.is_(True),
            Company.is_active.is_(True),
            Customer.status == "active",
        ).order_by(CustomerPortalMembership.created_at, CustomerPortalMembership.id).limit(1)
    )
    if membership_company_id is None:
        raise DomainError(401, "invalid_customer_credentials", "Email or password is incorrect, or portal access is no longer active")
    session_id = uuid4()
    pair, jti, expires_at = _customer_token_pair(identity, membership_company_id, session_id)
    db.add(CustomerPortalSession(id=session_id, portal_user_id=identity.id, refresh_jti=jti, expires_at=expires_at))
    db.commit()
    return _session_response(request, response, pair)


@router.post("/auth/refresh")
def refresh_customer_session(
    request: Request, response: Response, db: Session = Depends(get_db),
):
    _private_response(response)
    raw = request.cookies.get(CUSTOMER_REFRESH_COOKIE)
    if request.headers.get("origin") and not raw:
        raise DomainError(401, "customer_cookie_session_required", "Customer browser sessions must use the secure refresh cookie")
    if not raw:
        raise DomainError(401, "invalid_customer_refresh", "The customer portal refresh session is invalid or expired")
    try:
        claims = decode_token(raw)
        if claims.get("typ") != "customer_refresh":
            raise ValueError("wrong token type")
        identity_id, session_id, jti = UUID(str(claims["sub"])), UUID(str(claims["sid"])), str(claims["jti"])
    except (jwt.PyJWTError, ValueError, KeyError, TypeError):
        clear_customer_portal_cookies(response)
        raise DomainError(401, "invalid_customer_refresh", "The customer portal refresh session is invalid or expired") from None
    session = db.scalar(select(CustomerPortalSession).where(CustomerPortalSession.id == session_id).with_for_update())
    now = _now()
    if session is None or session.portal_user_id != identity_id or session.revoked_at is not None or session.refresh_jti != jti or _utc(session.expires_at) <= now:
        clear_customer_portal_cookies(response)
        raise DomainError(401, "invalid_customer_refresh", "The customer portal refresh session is invalid or expired")
    identity = db.get(CustomerPortalIdentity, identity_id)
    company_id = db.scalar(select(CustomerPortalMembership.company_id)
        .join(Company, Company.id == CustomerPortalMembership.company_id)
        .join(Customer, Customer.id == CustomerPortalMembership.customer_id)
        .where(
            CustomerPortalMembership.portal_user_id == identity_id,
            CustomerPortalMembership.is_active.is_(True),
            Company.is_active.is_(True),
            Customer.status == "active",
        ).order_by(CustomerPortalMembership.created_at, CustomerPortalMembership.id).limit(1))
    if identity is None or not identity.is_active or company_id is None:
        session.revoked_at = now
        db.commit()
        clear_customer_portal_cookies(response)
        raise DomainError(401, "invalid_customer_session", "Customer portal access is no longer active")
    pair, next_jti, next_expiry = _customer_token_pair(identity, company_id, session_id)
    session.refresh_jti, session.expires_at = next_jti, next_expiry
    db.commit()
    return _session_response(request, response, pair)


@router.post("/auth/logout", status_code=204)
def customer_logout(
    request: Request, response: Response, identity: CustomerPortalIdentity = Depends(get_customer_identity),
    db: Session = Depends(get_db),
) -> Response:
    session_id = getattr(request.state, "customer_portal_session_id", None)
    if session_id:
        session = db.get(CustomerPortalSession, session_id)
        if session and session.portal_user_id == identity.id and session.revoked_at is None:
            session.revoked_at = _now()
            db.commit()
    clear_customer_portal_cookies(response)
    response.status_code = 204
    return response


@router.get("/auth/me", response_model=CustomerPortalMe)
def customer_me(identity: CustomerPortalIdentity = Depends(get_customer_identity), db: Session = Depends(get_db)) -> CustomerPortalMe:
    rows = db.execute(
        select(CustomerPortalMembership, Customer, Company)
        .join(Customer, Customer.id == CustomerPortalMembership.customer_id)
        .join(Company, Company.id == CustomerPortalMembership.company_id)
        .where(
            CustomerPortalMembership.portal_user_id == identity.id,
            CustomerPortalMembership.is_active.is_(True),
            Customer.status == "active",
            Company.is_active.is_(True),
        ).order_by(CustomerPortalMembership.created_at, CustomerPortalMembership.id)
    ).all()
    return CustomerPortalMe(
        id=identity.id, email=identity.email, full_name=identity.full_name,
        memberships=[
            CustomerPortalMembershipRead(
                membership_id=m.id, customer_id=c.id, company_id=company.id,
                company_name=company.name, customer_name=c.name,
            )
            for m, c, company in rows
        ],
    )


@router.get("/memberships/{membership_id}/overview", response_model=CustomerPortalOverview)
def portal_overview(membership_id: UUID, identity: CustomerPortalIdentity = Depends(get_customer_identity), db: Session = Depends(get_db)) -> CustomerPortalOverview:
    membership, customer, company = _membership(db, identity, membership_id)
    locations = list(db.scalars(select(ServiceLocation).where(
        ServiceLocation.company_id == company.id,
        ServiceLocation.customer_id == customer.id,
        ServiceLocation.is_active.is_(True),
    ).order_by(ServiceLocation.name, ServiceLocation.id)).all())
    agreements = db.scalar(select(func.count()).select_from(Agreement).where(
        Agreement.company_id == company.id, Agreement.customer_id == customer.id,
        Agreement.status != "draft",
    )) or 0
    open_work = db.scalar(select(func.count()).select_from(WorkOrder).where(
        WorkOrder.company_id == company.id, WorkOrder.customer_id == customer.id,
        WorkOrder.status.notin_(("completed", "cancelled")),
    )) or 0
    unpaid = db.scalar(select(func.count()).select_from(Invoice).where(
        Invoice.company_id == company.id, Invoice.customer_id == customer.id,
        Invoice.status.in_(("issued", "partially_paid", "overdue")),
    )) or 0
    return CustomerPortalOverview(
        company_name=company.name, customer_name=customer.name, customer_number=customer.customer_number,
        customer_kind=customer.kind,
        locations=[CustomerPortalLocationRead(
            id=x.id, name=x.name, address_line1=x.address_line1, address_line2=x.address_line2,
            city=x.city, region=x.region, postal_code=x.postal_code, country_code=x.country_code, is_active=x.is_active,
        ) for x in locations],
        agreement_count=agreements, open_work_order_count=open_work, unpaid_invoice_count=unpaid,
    )


@router.get("/memberships/{membership_id}/agreements", response_model=list[CustomerPortalAgreementRead])
def portal_agreements(membership_id: UUID, identity: CustomerPortalIdentity = Depends(get_customer_identity), db: Session = Depends(get_db)) -> list[CustomerPortalAgreementRead]:
    membership, customer, company = _membership(db, identity, membership_id)
    items = list(db.scalars(
        select(Agreement).options(selectinload(Agreement.lines))
        .where(
            Agreement.company_id == company.id, Agreement.customer_id == customer.id,
            Agreement.status != "draft",
        ).order_by(Agreement.start_date.desc(), Agreement.id)
        .limit(200)
    ).all())
    return [CustomerPortalAgreementRead(
        id=a.id, agreement_number=a.agreement_number, title=a.title, status=a.status,
        start_date=a.start_date.isoformat(), end_date=a.end_date.isoformat(),
        billing_frequency=a.billing_frequency, currency=a.currency, total_amount=a.total_amount,
        terms_text=a.terms_text,
        lines=[{
            "service_code": line.service_code, "name": line.name, "description": line.description,
            "quantity": line.quantity, "unit_price": line.unit_price, "line_total": line.line_total,
        } for line in a.lines],
    ) for a in items]


@router.get("/memberships/{membership_id}/locations", response_model=list[CustomerPortalLocationRead])
def portal_locations(membership_id: UUID, identity: CustomerPortalIdentity = Depends(get_customer_identity), db: Session = Depends(get_db)) -> list[CustomerPortalLocationRead]:
    membership, customer, company = _membership(db, identity, membership_id)
    items = db.scalars(select(ServiceLocation).where(
        ServiceLocation.company_id == company.id, ServiceLocation.customer_id == customer.id,
    ).order_by(ServiceLocation.name, ServiceLocation.id).limit(300)).all()
    return [CustomerPortalLocationRead(
        id=x.id, name=x.name, address_line1=x.address_line1, address_line2=x.address_line2,
        city=x.city, region=x.region, postal_code=x.postal_code, country_code=x.country_code, is_active=x.is_active,
    ) for x in items]


@router.get("/memberships/{membership_id}/equipment", response_model=list[CustomerPortalEquipmentRead])
def portal_equipment(membership_id: UUID, identity: CustomerPortalIdentity = Depends(get_customer_identity), db: Session = Depends(get_db)) -> list[CustomerPortalEquipmentRead]:
    membership, customer, company = _membership(db, identity, membership_id)
    items = db.scalars(select(Equipment).where(
        Equipment.company_id == company.id, Equipment.customer_id == customer.id,
    ).order_by(Equipment.category, Equipment.asset_number, Equipment.id).limit(500)).all()
    return [CustomerPortalEquipmentRead(
        id=x.id, asset_number=x.asset_number, service_location_id=x.service_location_id,
        category=x.category, manufacturer=x.manufacturer, model_number=x.model_number,
        serial_number=x.serial_number, installed_on=x.installed_on.isoformat() if x.installed_on else None,
        warranty_expires_on=x.warranty_expires_on.isoformat() if x.warranty_expires_on else None,
        status=x.status,
    ) for x in items]


@router.get("/memberships/{membership_id}/work-orders", response_model=list[CustomerPortalWorkOrderRead])
def portal_work_orders(membership_id: UUID, identity: CustomerPortalIdentity = Depends(get_customer_identity), db: Session = Depends(get_db)) -> list[CustomerPortalWorkOrderRead]:
    membership, customer, company = _membership(db, identity, membership_id)
    rows = db.execute(
        select(WorkOrder, ServiceLocation, Equipment)
        .join(ServiceLocation, ServiceLocation.id == WorkOrder.service_location_id)
        .outerjoin(Equipment, Equipment.id == WorkOrder.equipment_id)
        .where(WorkOrder.company_id == company.id, WorkOrder.customer_id == customer.id)
        .order_by(WorkOrder.scheduled_for.desc(), WorkOrder.id).limit(200)
    ).all()
    return [CustomerPortalWorkOrderRead(
        id=w.id, work_order_number=w.work_order_number, title=w.title, status=w.status,
        priority=w.priority, scheduled_for=w.scheduled_for.isoformat(),
        appointment_start=w.appointment_start, appointment_end=w.appointment_end,
        service_location_name=loc.name, service_location_city=loc.city,
        equipment_label=(f"{equip.category} · {equip.asset_number}" if equip else None),
    ) for w, loc, equip in rows]


@router.get("/memberships/{membership_id}/invoices", response_model=list[CustomerPortalInvoiceRead])
def portal_invoices(membership_id: UUID, identity: CustomerPortalIdentity = Depends(get_customer_identity), db: Session = Depends(get_db)) -> list[CustomerPortalInvoiceRead]:
    membership, customer, company = _membership(db, identity, membership_id)
    items = list(db.scalars(
        select(Invoice).options(selectinload(Invoice.lines))
        .where(
            Invoice.company_id == company.id, Invoice.customer_id == customer.id,
            Invoice.status.in_(("issued", "partially_paid", "paid", "overdue")),
        ).order_by(Invoice.invoice_date.desc(), Invoice.id).limit(200)
    ).all())
    return [_portal_invoice(db, item) for item in items]


def _customer_invoice(db: Session, membership, customer: Customer, company: Company, invoice_id: UUID, *, lock: bool = False) -> Invoice:
    stmt = select(Invoice).options(selectinload(Invoice.lines)).where(
        Invoice.id == invoice_id,
        Invoice.company_id == company.id,
        Invoice.customer_id == customer.id,
        Invoice.status.in_(("issued", "partially_paid", "paid", "overdue")),
    )
    if lock:
        stmt = stmt.with_for_update()
    invoice = db.scalar(stmt)
    if invoice is None:
        raise DomainError(404, "invoice_not_found", "Invoice not found")
    return invoice


@router.get("/memberships/{membership_id}/invoices/{invoice_id}", response_model=CustomerPortalInvoiceRead)
def portal_invoice_detail(
    membership_id: UUID, invoice_id: UUID,
    identity: CustomerPortalIdentity = Depends(get_customer_identity), db: Session = Depends(get_db),
) -> CustomerPortalInvoiceRead:
    membership, customer, company = _membership(db, identity, membership_id)
    invoice = _customer_invoice(db, membership, customer, company, invoice_id)
    return _portal_invoice(db, invoice)


@router.get("/memberships/{membership_id}/invoices/{invoice_id}/pdf")
def portal_invoice_pdf(
    membership_id: UUID, invoice_id: UUID,
    response: Response,
    identity: CustomerPortalIdentity = Depends(get_customer_identity), db: Session = Depends(get_db),
) -> StreamingResponse:
    membership, customer, company = _membership(db, identity, membership_id)
    invoice = _customer_invoice(db, membership, customer, company, invoice_id)
    stream = render_invoice_pdf(invoice, customer_name=customer.name)
    result = StreamingResponse(
        stream, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{invoice.invoice_number}.pdf"', "Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
    )
    return result


@router.post("/memberships/{membership_id}/invoices/{invoice_id}/payment-intent", response_model=CustomerPortalPaymentIntentRead)
def portal_create_payment_intent(
    membership_id: UUID, invoice_id: UUID, request: Request, response: Response,
    identity: CustomerPortalIdentity = Depends(get_customer_identity), db: Session = Depends(get_db),
) -> CustomerPortalPaymentIntentRead:
    _private_response(response)
    membership, customer, company = _membership(db, identity, membership_id)
    enforce_rate_limit(request, scope="customer-portal-payment-intent", limit=8, window_seconds=900, subject=f"{identity.id}:{invoice_id}")
    invoice = _customer_invoice(db, membership, customer, company, invoice_id, lock=True)
    from app.api.billing import invoice_response
    from app.services.stripe_service import create_payment_intent, stripe_enabled
    if not stripe_enabled():
        raise DomainError(503, "stripe_not_configured", "Online card payments are not configured. Contact the service provider to arrange payment.")
    summary = invoice_response(db, invoice)
    if invoice.status not in {"issued", "partially_paid"} or summary.balance_due <= Decimal("0.00"):
        raise DomainError(409, "invoice_not_payable", "This invoice has no outstanding balance")
    version = invoice.updated_at.isoformat() if invoice.updated_at else "initial"
    suffix = hashlib.sha256(f"{membership.id}:{invoice.id}:{version}:{summary.balance_due}".encode()).hexdigest()[:32]
    intent = create_payment_intent(
        invoice, amount_due=summary.balance_due,
        idempotency_key=f"customer-portal:{membership.id}:{suffix}",
        customer_portal_membership_id=str(membership.id),
    )
    return CustomerPortalPaymentIntentRead(**intent)


@router.post("/memberships/{membership_id}/invoices/{invoice_id}/confirm", response_model=CustomerPortalInvoiceRead)
def portal_confirm_payment(
    membership_id: UUID, invoice_id: UUID, payload: CustomerPortalPaymentConfirm,
    request: Request, response: Response,
    identity: CustomerPortalIdentity = Depends(get_customer_identity), db: Session = Depends(get_db),
) -> CustomerPortalInvoiceRead:
    _private_response(response)
    membership, customer, company = _membership(db, identity, membership_id)
    enforce_rate_limit(request, scope="customer-portal-payment-confirm", limit=12, window_seconds=900, subject=f"{identity.id}:{invoice_id}")
    payment_intent_id = payload.payment_intent_id
    invoice = _customer_invoice(db, membership, customer, company, invoice_id, lock=True)
    from app.services.stripe_service import _client, record_stripe_payment
    try:
        intent = _client().PaymentIntent.retrieve(payment_intent_id)
    except Exception as exc:
        raise DomainError(502, "stripe_verification_failed", "Unable to verify the payment with Stripe. Refresh the invoice and check the balance before trying again.") from exc
    metadata = intent.get("metadata", {}) or {}
    if (
        metadata.get("invoice_id") != str(invoice.id)
        or metadata.get("company_id") != str(company.id)
        or metadata.get("customer_portal_membership_id") != str(membership.id)
    ):
        raise DomainError(404, "payment_intent_not_found", "This payment does not belong to the selected customer invoice")
    record_stripe_payment(db, invoice, payment_intent_id, idempotency_key=f"stripe:{payment_intent_id}", intent_data=intent)
    db.refresh(invoice)
    invoice = _customer_invoice(db, membership, customer, company, invoice_id)
    return _portal_invoice(db, invoice)


@router.get("/customers/{customer_id}/access", response_model=CustomerPortalAccessRead)
def customer_portal_access(
    customer_id: UUID,
    user: User = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
) -> CustomerPortalAccessRead:
    customer = db.scalar(select(Customer).where(
        Customer.id == customer_id, Customer.company_id == user.company_id,
    ))
    if customer is None:
        raise DomainError(404, "customer_not_found", "Customer not found")
    email = (customer.email or "").strip().lower()
    if not email:
        return CustomerPortalAccessRead(has_access=False)
    identity = db.scalar(select(CustomerPortalIdentity).where(CustomerPortalIdentity.email == email))
    if identity is not None:
        active = db.scalar(select(CustomerPortalMembership.id).where(
            CustomerPortalMembership.portal_user_id == identity.id,
            CustomerPortalMembership.company_id == user.company_id,
            CustomerPortalMembership.customer_id == customer.id,
            CustomerPortalMembership.is_active.is_(True),
        )) is not None
        if active:
            return CustomerPortalAccessRead(has_access=True, invited_email=email, invitation_status="accepted")
    invitation = db.scalar(select(CustomerPortalInvitation).where(
        CustomerPortalInvitation.company_id == user.company_id,
        CustomerPortalInvitation.customer_id == customer.id,
        CustomerPortalInvitation.email == email,
    ).order_by(CustomerPortalInvitation.created_at.desc(), CustomerPortalInvitation.id.desc()).limit(1))
    return CustomerPortalAccessRead(
        has_access=False, invited_email=email,
        invitation_status=invitation.status if invitation is not None else None,
    )


@router.delete("/customers/{customer_id}/access", status_code=204)
def revoke_customer_portal_access(
    customer_id: UUID,
    response: Response,
    user: User = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
) -> Response:
    customer = db.scalar(select(Customer).where(
        Customer.id == customer_id, Customer.company_id == user.company_id,
    ).with_for_update())
    if customer is None:
        raise DomainError(404, "customer_not_found", "Customer not found")
    email = (customer.email or "").strip().lower()
    now = _now()
    if email:
        identity = db.scalar(select(CustomerPortalIdentity).where(CustomerPortalIdentity.email == email))
        if identity is not None:
            memberships = db.scalars(select(CustomerPortalMembership).where(
                CustomerPortalMembership.portal_user_id == identity.id,
                CustomerPortalMembership.company_id == user.company_id,
                CustomerPortalMembership.customer_id == customer.id,
                CustomerPortalMembership.is_active.is_(True),
            ).with_for_update()).all()
            for membership in memberships:
                membership.is_active = False
        invitations = db.scalars(select(CustomerPortalInvitation).where(
            CustomerPortalInvitation.company_id == user.company_id,
            CustomerPortalInvitation.customer_id == customer.id,
            CustomerPortalInvitation.status == "pending",
        ).with_for_update()).all()
        for invitation in invitations:
            invitation.status = "revoked"
    db.commit()
    response.status_code = 204
    return response


def _customer_document_filter(company: Company, customer: Customer):
    locations = select(ServiceLocation.id).where(
        ServiceLocation.company_id == company.id, ServiceLocation.customer_id == customer.id,
    )
    equipment_ids = select(Equipment.id).where(
        Equipment.company_id == company.id, Equipment.customer_id == customer.id,
    )
    agreement_ids = select(Agreement.id).where(
        Agreement.company_id == company.id, Agreement.customer_id == customer.id,
        Agreement.status != "draft",
    )
    work_order_ids = select(WorkOrder.id).where(
        WorkOrder.company_id == company.id, WorkOrder.customer_id == customer.id,
    )
    invoice_ids = select(Invoice.id).where(
        Invoice.company_id == company.id, Invoice.customer_id == customer.id,
        Invoice.status.in_(("issued", "partially_paid", "paid", "overdue")),
    )
    return or_(
        (Attachment.entity_type == "customer") & (Attachment.entity_id == customer.id),
        (Attachment.entity_type == "service_location") & Attachment.entity_id.in_(locations),
        (Attachment.entity_type == "equipment") & Attachment.entity_id.in_(equipment_ids),
        (Attachment.entity_type == "agreement") & Attachment.entity_id.in_(agreement_ids),
        (Attachment.entity_type == "work_order") & Attachment.entity_id.in_(work_order_ids),
        (Attachment.entity_type == "invoice") & Attachment.entity_id.in_(invoice_ids),
    )


@router.get("/memberships/{membership_id}/payments", response_model=list[CustomerPortalPaymentRead])
def portal_payments(
    membership_id: UUID,
    identity: CustomerPortalIdentity = Depends(get_customer_identity),
    db: Session = Depends(get_db),
) -> list[CustomerPortalPaymentRead]:
    membership, customer, company = _membership(db, identity, membership_id)
    rows = db.execute(
        select(Payment, Invoice)
        .join(Invoice, Invoice.id == Payment.invoice_id)
        .where(
            Payment.company_id == company.id,
            Invoice.company_id == company.id,
            Invoice.customer_id == customer.id,
            Invoice.status.in_(("issued", "partially_paid", "paid", "overdue")),
        )
        .order_by(Payment.received_at.desc(), Payment.id)
        .limit(200)
    ).all()
    if not rows:
        return []
    payment_ids = [payment.id for payment, _ in rows]
    refunds: dict[UUID, list[CustomerPortalRefundRead]] = {payment_id: [] for payment_id in payment_ids}
    for item in db.scalars(
        select(PaymentRefund).where(
            PaymentRefund.company_id == company.id,
            PaymentRefund.payment_id.in_(payment_ids),
        ).order_by(PaymentRefund.refunded_at, PaymentRefund.id)
    ).all():
        refunds[item.payment_id].append(CustomerPortalRefundRead(
            id=item.id, amount=item.amount, refund_method=item.refund_method,
            reference=item.reference, reason=item.reason, refunded_at=item.refunded_at,
        ))
    return [
        CustomerPortalPaymentRead(
            id=payment.id, invoice_id=invoice.id, invoice_number=invoice.invoice_number,
            amount=payment.amount, payment_method=payment.payment_method,
            reference=payment.reference, received_at=payment.received_at,
            notes=payment.notes, stripe_status=payment.stripe_status,
            refunds=refunds[payment.id],
        )
        for payment, invoice in rows
    ]


@router.get("/memberships/{membership_id}/documents", response_model=list[CustomerPortalAttachmentRead])
def portal_documents(
    membership_id: UUID,
    identity: CustomerPortalIdentity = Depends(get_customer_identity),
    db: Session = Depends(get_db),
) -> list[Attachment]:
    membership, customer, company = _membership(db, identity, membership_id)
    query = select(Attachment).where(
        Attachment.company_id == company.id,
        Attachment.status == "active",
        _customer_document_filter(company, customer),
    ).order_by(Attachment.created_at.desc(), Attachment.id).limit(200)
    items = list(db.scalars(query).all())
    return [
        CustomerPortalAttachmentRead(
            id=item.id, entity_type=item.entity_type, entity_id=item.entity_id,
            original_filename=item.original_filename, content_type=item.content_type,
            size_bytes=item.size_bytes, description=item.description, created_at=item.created_at,
        )
        for item in items
    ]


@router.get("/memberships/{membership_id}/documents/{attachment_id}")
def portal_download_document(
    membership_id: UUID,
    attachment_id: UUID,
    identity: CustomerPortalIdentity = Depends(get_customer_identity),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    membership, customer, company = _membership(db, identity, membership_id)
    attachment = db.scalar(select(Attachment).where(
        Attachment.id == attachment_id,
        Attachment.company_id == company.id,
        Attachment.status == "active",
        _customer_document_filter(company, customer),
    ))
    if attachment is None:
        raise DomainError(404, "customer_document_not_found", "Document not found")
    try:
        backend = build_storage()
    except ValueError as exc:
        raise DomainError(503, "storage_backend_unavailable", "Document storage is temporarily unavailable") from exc
    if not backend.exists(attachment.storage_key):
        raise DomainError(410, "customer_document_storage_missing", "This document is no longer available")
    return StreamingResponse(
        backend.open(attachment.storage_key),
        media_type=attachment.content_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(attachment.original_filename)}",
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
        },
    )
