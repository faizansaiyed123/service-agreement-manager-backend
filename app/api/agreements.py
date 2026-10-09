from datetime import UTC, date, datetime
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.agreement_schemas import AcceptanceEvidence, AgreementCreate, AgreementEventRead, AgreementLineInput, AgreementRead, AgreementUpdate, AgreementVersionRead, ReasonRequest
from app.api.deps import get_current_user, require_roles
from app.core.errors import DomainError
from app.db.session import get_db
from app.models import Agreement, AgreementEvent, AgreementLine, AgreementVersion, Company, Customer, ServiceCatalogItem, ServiceLocation, User

router = APIRouter(prefix="/agreements", tags=["agreements"])
CENT = Decimal("0.01")


def scoped_agreement(db: Session, company_id: UUID, agreement_id: UUID) -> Agreement:
    item = db.scalar(select(Agreement).options(selectinload(Agreement.lines)).where(
        Agreement.id == agreement_id, Agreement.company_id == company_id
    ))
    if item is None:
        raise DomainError(404, "agreement_not_found", "Agreement not found")
    return item


def add_event(db: Session, agreement: Agreement, actor_id: UUID, event_type: str, from_status: str | None = None, detail: dict | None = None) -> None:
    db.add(AgreementEvent(
        agreement_id=agreement.id, actor_user_id=actor_id, event_type=event_type,
        from_status=from_status, to_status=agreement.status, detail=detail,
    ))


def make_line(db: Session, company_id: UUID, payload: AgreementLineInput) -> AgreementLine:
    if payload.catalog_item_id is not None:
        catalog = db.scalar(select(ServiceCatalogItem).where(
            ServiceCatalogItem.id == payload.catalog_item_id,
            ServiceCatalogItem.company_id == company_id,
            ServiceCatalogItem.is_active.is_(True),
        ))
        if catalog is None:
            raise DomainError(404, "catalog_item_not_found", "Active service catalog item not found")
        code, name, description, unit_price, catalog_id = catalog.service_code, catalog.name, catalog.description, catalog.unit_price, catalog.id
    else:
        code = (payload.service_code or "CUSTOM").upper()
        name = payload.name.strip() if payload.name else ""
        description, unit_price, catalog_id = payload.description, payload.unit_price, None
    if unit_price is None:
        raise DomainError(422, "price_required", "Custom service lines require unit_price")
    total = (payload.quantity * unit_price).quantize(CENT, rounding=ROUND_HALF_UP)
    return AgreementLine(
        catalog_item_id=catalog_id, service_code=code, name=name, description=description,
        quantity=payload.quantity, unit_price=unit_price, line_total=total,
    )


def refresh_total(agreement: Agreement) -> None:
    agreement.total_amount = sum((line.line_total for line in agreement.lines), Decimal("0.00")).quantize(CENT)


def serialize_snapshot(agreement: Agreement) -> dict:
    return {
        "agreement_number": agreement.agreement_number, "title": agreement.title,
        "start_date": agreement.start_date.isoformat(), "end_date": agreement.end_date.isoformat(),
        "billing_frequency": agreement.billing_frequency, "currency": agreement.currency,
        "auto_renew": agreement.auto_renew, "renewal_notice_days": agreement.renewal_notice_days,
        "terms_text": agreement.terms_text, "total_amount": str(agreement.total_amount),
        "lines": [{
            "service_code": line.service_code, "name": line.name, "description": line.description,
            "quantity": str(line.quantity), "unit_price": str(line.unit_price), "line_total": str(line.line_total),
        } for line in agreement.lines],
    }


@router.post("", response_model=AgreementRead, status_code=201)
def create_agreement(payload: AgreementCreate, user: User = Depends(require_roles("owner", "admin", "manager", "staff")), db: Session = Depends(get_db)) -> Agreement:
    customer = db.scalar(select(Customer).where(Customer.id == payload.customer_id, Customer.company_id == user.company_id))
    if customer is None or customer.status != "active":
        raise DomainError(404, "customer_not_found", "Active customer not found")
    location = db.scalar(select(ServiceLocation).where(
        ServiceLocation.id == payload.service_location_id, ServiceLocation.customer_id == customer.id,
        ServiceLocation.company_id == user.company_id, ServiceLocation.is_active.is_(True),
    ))
    if location is None:
        raise DomainError(404, "service_location_not_found", "Active service location not found for customer")
    company = db.scalar(select(Company).where(Company.id == user.company_id).with_for_update())
    if company is None or not company.is_active:
        raise DomainError(403, "company_inactive", "Company account is inactive")
    company.agreement_sequence += 1
    agreement = Agreement(
        company_id=user.company_id, customer_id=customer.id, service_location_id=location.id,
        agreement_number=f"SA-{company.agreement_sequence:06d}", title=payload.title.strip(),
        start_date=payload.start_date, end_date=payload.end_date, billing_frequency=payload.billing_frequency,
        currency=company.currency, auto_renew=payload.auto_renew, renewal_notice_days=payload.renewal_notice_days,
        terms_text=payload.terms_text,
    )
    db.add(agreement)
    db.flush()
    for line_input in payload.lines:
        agreement.lines.append(make_line(db, user.company_id, line_input))
    refresh_total(agreement)
    db.flush()
    add_event(db, agreement, user.id, "agreement.created", detail={"agreement_number": agreement.agreement_number})
    db.commit()
    return scoped_agreement(db, user.company_id, agreement.id)


@router.get("", response_model=list[AgreementRead])
def list_agreements(status: str | None = Query(default=None, pattern="^(draft|proposed|accepted|active|suspended|cancelled|expired)$"), customer_id: UUID | None = None, limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0), user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Agreement]:
    stmt = select(Agreement).options(selectinload(Agreement.lines)).where(Agreement.company_id == user.company_id)
    if status:
        stmt = stmt.where(Agreement.status == status)
    if customer_id:
        stmt = stmt.where(Agreement.customer_id == customer_id)
    return list(db.scalars(stmt.order_by(Agreement.created_at.desc(), Agreement.id).limit(limit).offset(offset)).all())


@router.get("/{agreement_id}", response_model=AgreementRead)
def get_agreement(agreement_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Agreement:
    return scoped_agreement(db, user.company_id, agreement_id)


@router.patch("/{agreement_id}", response_model=AgreementRead)
def update_draft(agreement_id: UUID, payload: AgreementUpdate, user: User = Depends(require_roles("owner", "admin", "manager", "staff")), db: Session = Depends(get_db)) -> Agreement:
    agreement = scoped_agreement(db, user.company_id, agreement_id)
    if agreement.status != "draft":
        raise DomainError(409, "agreement_not_editable", "Only draft agreements can be edited")
    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise DomainError(422, "empty_update", "At least one field must be provided")
    lines = data.pop("lines", None)
    start_date = data.get("start_date", agreement.start_date)
    end_date = data.get("end_date", agreement.end_date)
    if start_date is None or end_date is None or end_date < start_date:
        raise DomainError(422, "invalid_date_range", "end_date must be on or after start_date")
    for key, value in data.items():
        if key == "title":
            value = value.strip()
            if not value:
                raise DomainError(422, "invalid_field", "title cannot be blank")
        setattr(agreement, key, value)
    if lines is not None:
        agreement.lines.clear()
        db.flush()
        for line_input in lines:
            agreement.lines.append(make_line(db, user.company_id, line_input))
    refresh_total(agreement)
    add_event(db, agreement, user.id, "agreement.draft_updated", detail={"lines_replaced": lines is not None})
    db.commit()
    return scoped_agreement(db, user.company_id, agreement.id)


@router.post("/{agreement_id}/propose", response_model=AgreementRead)
def propose_agreement(agreement_id: UUID, user: User = Depends(require_roles("owner", "admin", "manager")), db: Session = Depends(get_db)) -> Agreement:
    agreement = scoped_agreement(db, user.company_id, agreement_id)
    if agreement.status != "draft":
        raise DomainError(409, "invalid_agreement_transition", "Only draft agreements can be proposed")
    previous = agreement.status
    agreement.status = "proposed"
    agreement.version_number += 1
    db.add(AgreementVersion(
        agreement_id=agreement.id, version_number=agreement.version_number,
        snapshot=serialize_snapshot(agreement), change_reason="Initial proposal", created_by=user.id,
    ))
    add_event(db, agreement, user.id, "agreement.proposed", from_status=previous, detail={"version": agreement.version_number})
    db.commit()
    return scoped_agreement(db, user.company_id, agreement.id)


@router.post("/{agreement_id}/accept", response_model=AgreementRead)
def accept_agreement(agreement_id: UUID, payload: AcceptanceEvidence, user: User = Depends(require_roles("owner", "admin", "manager", "staff")), db: Session = Depends(get_db)) -> Agreement:
    agreement = scoped_agreement(db, user.company_id, agreement_id)
    if agreement.status != "proposed":
        raise DomainError(409, "invalid_agreement_transition", "Only proposed agreements can be accepted")
    previous = agreement.status
    agreement.accepted_by_name = payload.accepted_by_name.strip()
    agreement.acceptance_method = payload.method
    agreement.acceptance_reference = payload.reference
    agreement.accepted_at = datetime.now(UTC)
    agreement.status = "active" if agreement.start_date <= date.today() else "accepted"
    add_event(db, agreement, user.id, "agreement.accepted", from_status=previous, detail={"method": payload.method, "reference": payload.reference})
    db.commit()
    return scoped_agreement(db, user.company_id, agreement.id)


@router.post("/{agreement_id}/activate", response_model=AgreementRead)
def activate_agreement(agreement_id: UUID, user: User = Depends(require_roles("owner", "admin", "manager")), db: Session = Depends(get_db)) -> Agreement:
    agreement = scoped_agreement(db, user.company_id, agreement_id)
    if agreement.status != "accepted":
        raise DomainError(409, "invalid_agreement_transition", "Only accepted agreements can be activated")
    if agreement.start_date > date.today():
        raise DomainError(409, "agreement_not_yet_effective", "The agreement start date is in the future")
    previous = agreement.status
    agreement.status = "active"
    add_event(db, agreement, user.id, "agreement.activated", from_status=previous)
    db.commit()
    return scoped_agreement(db, user.company_id, agreement.id)


@router.post("/{agreement_id}/suspend", response_model=AgreementRead)
def suspend_agreement(agreement_id: UUID, payload: ReasonRequest, user: User = Depends(require_roles("owner", "admin", "manager")), db: Session = Depends(get_db)) -> Agreement:
    agreement = scoped_agreement(db, user.company_id, agreement_id)
    if agreement.status != "active":
        raise DomainError(409, "invalid_agreement_transition", "Only active agreements can be suspended")
    previous = agreement.status
    agreement.status = "suspended"
    add_event(db, agreement, user.id, "agreement.suspended", from_status=previous, detail={"reason": payload.reason})
    db.commit()
    return scoped_agreement(db, user.company_id, agreement.id)


@router.post("/{agreement_id}/resume", response_model=AgreementRead)
def resume_agreement(agreement_id: UUID, user: User = Depends(require_roles("owner", "admin", "manager")), db: Session = Depends(get_db)) -> Agreement:
    agreement = scoped_agreement(db, user.company_id, agreement_id)
    if agreement.status != "suspended":
        raise DomainError(409, "invalid_agreement_transition", "Only suspended agreements can be resumed")
    previous = agreement.status
    agreement.status = "active"
    add_event(db, agreement, user.id, "agreement.resumed", from_status=previous)
    db.commit()
    return scoped_agreement(db, user.company_id, agreement.id)


@router.post("/{agreement_id}/cancel", response_model=AgreementRead)
def cancel_agreement(agreement_id: UUID, payload: ReasonRequest, user: User = Depends(require_roles("owner", "admin", "manager")), db: Session = Depends(get_db)) -> Agreement:
    agreement = scoped_agreement(db, user.company_id, agreement_id)
    if agreement.status not in {"draft", "proposed", "accepted", "active", "suspended"}:
        raise DomainError(409, "invalid_agreement_transition", "This agreement cannot be cancelled in its current state")
    previous = agreement.status
    agreement.status = "cancelled"
    agreement.cancelled_at = datetime.now(UTC)
    agreement.cancellation_reason = payload.reason.strip()
    add_event(db, agreement, user.id, "agreement.cancelled", from_status=previous, detail={"reason": payload.reason})
    db.commit()
    return scoped_agreement(db, user.company_id, agreement.id)


@router.get("/{agreement_id}/versions", response_model=list[AgreementVersionRead])
def list_versions(agreement_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[AgreementVersion]:
    scoped_agreement(db, user.company_id, agreement_id)
    return list(db.scalars(select(AgreementVersion).join(Agreement).where(AgreementVersion.agreement_id == agreement_id, Agreement.company_id == user.company_id).order_by(AgreementVersion.version_number)).all())


@router.get("/{agreement_id}/events", response_model=list[AgreementEventRead])
def list_events(agreement_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[AgreementEvent]:
    scoped_agreement(db, user.company_id, agreement_id)
    return list(db.scalars(select(AgreementEvent).join(Agreement).where(AgreementEvent.agreement_id == agreement_id, Agreement.company_id == user.company_id).order_by(AgreementEvent.created_at, AgreementEvent.id)).all())


@router.delete("/{agreement_id}", status_code=204)
def reject_delete() -> Response:
    raise DomainError(405, "agreement_history_preserved", "Agreements are retained for audit; cancel instead")
