from datetime import UTC, date, datetime
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, require_roles
from app.core.errors import DomainError
from app.db.session import get_db
from app.models import Agreement, AgreementEvent, AgreementLine, AgreementRenewal, AgreementVersion, Company, User
from app.renewal_schemas import AgreementRead, RenewalAcceptance, RenewalDecline, RenewalOfferCreate, RenewalOfferRead

router = APIRouter(prefix="/agreements/{agreement_id}/renewals", tags=["agreement renewals"])
CENT = Decimal("0.01")
MANAGER_ROLES = ("owner", "admin", "manager")


def utc_today() -> date:
    return datetime.now(UTC).date()


def get_source(db: Session, company_id: UUID, agreement_id: UUID) -> Agreement:
    source = db.scalar(select(Agreement).options(selectinload(Agreement.lines)).where(
        Agreement.id == agreement_id, Agreement.company_id == company_id
    ))
    if source is None:
        raise DomainError(404, "agreement_not_found", "Agreement not found")
    return source


def get_offer(db: Session, company_id: UUID, agreement_id: UUID, renewal_id: UUID) -> AgreementRenewal:
    offer = db.scalar(select(AgreementRenewal).where(
        AgreementRenewal.id == renewal_id,
        AgreementRenewal.company_id == company_id,
        AgreementRenewal.source_agreement_id == agreement_id,
    ))
    if offer is None:
        raise DomainError(404, "renewal_offer_not_found", "Renewal offer not found")
    return offer


def make_snapshot(source: Agreement, payload: RenewalOfferCreate) -> dict:
    if payload.lines is None:
        lines = [{
            "catalog_item_id": str(line.catalog_item_id) if line.catalog_item_id else None,
            "service_code": line.service_code,
            "name": line.name,
            "description": line.description,
            "quantity": str(line.quantity),
            "unit_price": str(line.unit_price),
            "line_total": str(line.line_total),
        } for line in source.lines]
    else:
        lines = []
        for line in payload.lines:
            total = (line.quantity * line.unit_price).quantize(CENT, rounding=ROUND_HALF_UP)
            lines.append({
                "catalog_item_id": None,
                "service_code": line.service_code.upper(),
                "name": line.name.strip(),
                "description": line.description,
                "quantity": str(line.quantity),
                "unit_price": str(line.unit_price),
                "line_total": str(total),
            })
    if not lines:
        raise DomainError(409, "agreement_requires_lines", "Agreement requires line items before it can be renewed")
    total_amount = sum((Decimal(line["line_total"]) for line in lines), Decimal("0.00")).quantize(CENT)
    return {
        "title": (payload.title or source.title).strip(),
        "proposed_start_date": payload.proposed_start_date.isoformat(),
        "proposed_end_date": payload.proposed_end_date.isoformat(),
        "billing_frequency": payload.billing_frequency or source.billing_frequency,
        "currency": source.currency,
        "auto_renew": source.auto_renew if payload.auto_renew is None else payload.auto_renew,
        "renewal_notice_days": source.renewal_notice_days if payload.renewal_notice_days is None else payload.renewal_notice_days,
        "terms_text": source.terms_text if payload.terms_text is None else payload.terms_text,
        "total_amount": str(total_amount),
        "lines": lines,
    }


def create_agreement_snapshot(agreement: Agreement) -> dict:
    return {
        "agreement_number": agreement.agreement_number,
        "title": agreement.title,
        "start_date": agreement.start_date.isoformat(),
        "end_date": agreement.end_date.isoformat(),
        "billing_frequency": agreement.billing_frequency,
        "currency": agreement.currency,
        "auto_renew": agreement.auto_renew,
        "renewal_notice_days": agreement.renewal_notice_days,
        "terms_text": agreement.terms_text,
        "total_amount": str(agreement.total_amount),
        "lines": [{
            "service_code": line.service_code,
            "name": line.name,
            "description": line.description,
            "quantity": str(line.quantity),
            "unit_price": str(line.unit_price),
            "line_total": str(line.line_total),
        } for line in agreement.lines],
    }


def log_agreement_event(
    db: Session,
    agreement: Agreement,
    actor_id: UUID,
    event_type: str,
    from_status: str | None = None,
    detail: dict | None = None,
) -> None:
    db.add(AgreementEvent(
        agreement_id=agreement.id, actor_user_id=actor_id, event_type=event_type,
        from_status=from_status, to_status=agreement.status, detail=detail, created_at=datetime.now(UTC),
    ))


@router.post("", response_model=RenewalOfferRead, status_code=201)
def create_renewal_offer(
    agreement_id: UUID,
    payload: RenewalOfferCreate,
    user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: Session = Depends(get_db),
) -> AgreementRenewal:
    source = get_source(db, user.company_id, agreement_id)
    today = utc_today()
    if source.status != "active" or source.end_date < today:
        raise DomainError(409, "agreement_not_renewable", "Only current active agreements can be offered for renewal")
    if payload.proposed_start_date <= source.end_date:
        raise DomainError(422, "renewal_term_overlap", "The proposed renewal must start after the current agreement ends")
    if payload.expires_on < today:
        raise DomainError(422, "renewal_offer_expired", "expires_on must be today or later")
    existing = db.scalars(select(AgreementRenewal).where(
        AgreementRenewal.company_id == user.company_id,
        AgreementRenewal.source_agreement_id == source.id,
        AgreementRenewal.status == "offered",
    )).all()
    for offer in existing:
        if offer.expires_on < today:
            offer.status = "expired"
    if any(offer.expires_on >= today for offer in existing):
        raise DomainError(409, "renewal_offer_already_open", "An unexpired renewal offer already exists for this agreement")
    snapshot = make_snapshot(source, payload)
    offer = AgreementRenewal(
        company_id=user.company_id, source_agreement_id=source.id, offered_by_user_id=user.id,
        status="offered", proposed_start_date=payload.proposed_start_date,
        proposed_end_date=payload.proposed_end_date, expires_on=payload.expires_on, snapshot=snapshot,
    )
    db.add(offer)
    db.flush()
    log_agreement_event(db, source, user.id, "agreement.renewal_offered", detail={
        "renewal_offer_id": str(offer.id), "expires_on": offer.expires_on.isoformat(),
        "proposed_start_date": offer.proposed_start_date.isoformat(),
    })
    db.commit()
    db.refresh(offer)
    return offer


@router.get("", response_model=list[RenewalOfferRead])
def list_renewal_offers(
    agreement_id: UUID,
    status: str | None = Query(default=None, pattern="^(offered|accepted|declined|expired|cancelled)$"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AgreementRenewal]:
    get_source(db, user.company_id, agreement_id)
    stmt = select(AgreementRenewal).where(
        AgreementRenewal.company_id == user.company_id,
        AgreementRenewal.source_agreement_id == agreement_id,
    )
    if status:
        stmt = stmt.where(AgreementRenewal.status == status)
    return list(db.scalars(stmt.order_by(AgreementRenewal.created_at.desc(), AgreementRenewal.id).limit(limit).offset(offset)).all())


@router.post("/{renewal_id}/accept", response_model=AgreementRead)
def accept_renewal_offer(
    agreement_id: UUID,
    renewal_id: UUID,
    payload: RenewalAcceptance,
    user: User = Depends(require_roles("owner", "admin", "manager", "staff")),
    db: Session = Depends(get_db),
) -> Agreement:
    source = get_source(db, user.company_id, agreement_id)
    offer = get_offer(db, user.company_id, agreement_id, renewal_id)
    if offer.status != "offered":
        raise DomainError(409, "renewal_offer_not_open", "Only open renewal offers can be accepted")
    if offer.expires_on < utc_today():
        offer.status = "expired"
        db.commit()
        raise DomainError(409, "renewal_offer_expired", "This renewal offer has expired")
    if source.status != "active":
        raise DomainError(409, "agreement_not_renewable", "The source agreement is no longer active")
    company = db.scalar(select(Company).where(Company.id == user.company_id).with_for_update())
    if company is None or not company.is_active:
        raise DomainError(403, "company_inactive", "Company account is inactive")
    company.agreement_sequence += 1
    successor = Agreement(
        company_id=user.company_id, customer_id=source.customer_id,
        service_location_id=source.service_location_id,
        agreement_number=f"SA-{company.agreement_sequence:06d}",
        title=offer.snapshot["title"], status="accepted",
        start_date=offer.proposed_start_date, end_date=offer.proposed_end_date,
        billing_frequency=offer.snapshot["billing_frequency"], currency=offer.snapshot["currency"],
        auto_renew=offer.snapshot["auto_renew"], renewal_notice_days=offer.snapshot["renewal_notice_days"],
        terms_text=offer.snapshot["terms_text"], total_amount=Decimal(offer.snapshot["total_amount"]),
        accepted_by_name=payload.accepted_by_name.strip(), accepted_at=datetime.now(UTC),
        acceptance_method=payload.method, acceptance_reference=payload.reference, version_number=1,
    )
    db.add(successor)
    db.flush()
    for line in offer.snapshot["lines"]:
        successor.lines.append(AgreementLine(
            catalog_item_id=UUID(line["catalog_item_id"]) if line.get("catalog_item_id") else None,
            service_code=line["service_code"], name=line["name"], description=line.get("description"),
            quantity=Decimal(line["quantity"]), unit_price=Decimal(line["unit_price"]),
            line_total=Decimal(line["line_total"]),
        ))
    db.flush()
    db.add(AgreementVersion(
        agreement_id=successor.id, version_number=1,
        snapshot=create_agreement_snapshot(successor),
        change_reason="Accepted renewal offer", created_by=user.id,
    ))
    offer.status = "accepted"
    offer.renewed_agreement_id = successor.id
    offer.accepted_by_name = payload.accepted_by_name.strip()
    offer.accepted_at = successor.accepted_at
    offer.acceptance_method = payload.method
    offer.acceptance_reference = payload.reference
    log_agreement_event(db, source, user.id, "agreement.renewal_accepted", detail={
        "renewal_offer_id": str(offer.id), "successor_agreement_id": str(successor.id),
    })
    log_agreement_event(db, successor, user.id, "agreement.renewal_accepted", detail={
        "source_agreement_id": str(source.id), "renewal_offer_id": str(offer.id),
    })
    db.commit()
    renewed = db.scalar(select(Agreement).options(selectinload(Agreement.lines)).where(
        Agreement.id == successor.id, Agreement.company_id == user.company_id
    ))
    if renewed is None:
        raise DomainError(500, "renewal_successor_missing", "The successor agreement could not be loaded")
    return renewed


@router.post("/{renewal_id}/decline", response_model=RenewalOfferRead)
def decline_renewal_offer(
    agreement_id: UUID,
    renewal_id: UUID,
    payload: RenewalDecline,
    user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: Session = Depends(get_db),
) -> AgreementRenewal:
    source = get_source(db, user.company_id, agreement_id)
    offer = get_offer(db, user.company_id, agreement_id, renewal_id)
    if offer.status != "offered":
        raise DomainError(409, "renewal_offer_not_open", "Only open renewal offers can be declined")
    if offer.expires_on < utc_today():
        offer.status = "expired"
        db.commit()
        raise DomainError(409, "renewal_offer_expired", "This renewal offer has expired")
    offer.status = "declined"
    offer.decline_reason = payload.reason.strip()
    log_agreement_event(db, source, user.id, "agreement.renewal_declined", detail={
        "renewal_offer_id": str(offer.id), "reason": payload.reason,
    })
    db.commit()
    db.refresh(offer)
    return offer


@router.post("/{renewal_id}/cancel", response_model=RenewalOfferRead)
def cancel_renewal_offer(
    agreement_id: UUID,
    renewal_id: UUID,
    user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: Session = Depends(get_db),
) -> AgreementRenewal:
    source = get_source(db, user.company_id, agreement_id)
    offer = get_offer(db, user.company_id, agreement_id, renewal_id)
    if offer.status != "offered":
        raise DomainError(409, "renewal_offer_not_open", "Only open renewal offers can be cancelled")
    offer.status = "cancelled"
    log_agreement_event(db, source, user.id, "agreement.renewal_cancelled", detail={"renewal_offer_id": str(offer.id)})
    db.commit()
    db.refresh(offer)
    return offer
