from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.errors import DomainError
from app.db.session import get_db
from app.models import Agreement, Company, Customer, RecurringInvoiceSchedule, ServiceLocation, User
from app.schemas.recurring import RecurringInvoiceCreate, RecurringInvoiceRead, RecurringInvoiceUpdate

router = APIRouter(prefix="/recurring-invoices", tags=["recurring-invoices"])
ROLES = ("owner", "admin", "manager", "billing")


def scoped(db: Session, company_id: UUID, schedule_id: UUID, lock: bool = False) -> RecurringInvoiceSchedule:
    stmt = select(RecurringInvoiceSchedule).where(
        RecurringInvoiceSchedule.id == schedule_id,
        RecurringInvoiceSchedule.company_id == company_id,
    )
    if lock:
        stmt = stmt.with_for_update()
    schedule = db.scalar(stmt)
    if schedule is None:
        raise DomainError(404, "recurring_invoice_not_found", "Recurring invoice schedule not found")
    return schedule


def validate_refs(db: Session, user: User, payload: RecurringInvoiceCreate) -> tuple[Company, UUID | None]:
    company = db.get(Company, user.company_id)
    if company is None or not company.is_active:
        raise DomainError(403, "company_inactive", "Company account is inactive")
    customer = db.scalar(select(Customer).where(
        Customer.id == payload.customer_id,
        Customer.company_id == user.company_id,
        Customer.status == "active",
    ))
    if customer is None:
        raise DomainError(404, "customer_not_found", "Active customer not found")
    location_id = payload.service_location_id
    if payload.agreement_id is not None:
        agreement = db.scalar(select(Agreement).where(
            Agreement.id == payload.agreement_id,
            Agreement.company_id == user.company_id,
            Agreement.customer_id == payload.customer_id,
            Agreement.status.in_(("accepted", "active", "suspended")),
        ))
        if agreement is None:
            raise DomainError(404, "agreement_not_found", "A matching current agreement was not found")
        if location_id is None:
            location_id = agreement.service_location_id
        elif location_id != agreement.service_location_id:
            raise DomainError(422, "agreement_location_mismatch", "Recurring invoice location must match the linked agreement")
    if location_id is not None:
        location = db.scalar(select(ServiceLocation).where(
            ServiceLocation.id == location_id,
            ServiceLocation.company_id == user.company_id,
            ServiceLocation.customer_id == payload.customer_id,
            ServiceLocation.is_active.is_(True),
        ))
        if location is None:
            raise DomainError(404, "service_location_not_found", "Active service location not found")
    return company, location_id


@router.post("", response_model=RecurringInvoiceRead, status_code=201)
def create_schedule(
    payload: RecurringInvoiceCreate,
    user: User = Depends(require_roles(*ROLES)),
    db: Session = Depends(get_db),
) -> RecurringInvoiceSchedule:
    company, location_id = validate_refs(db, user, payload)
    schedule = RecurringInvoiceSchedule(
        company_id=user.company_id,
        customer_id=payload.customer_id,
        service_location_id=location_id,
        agreement_id=payload.agreement_id,
        created_by_user_id=user.id,
        name=payload.name,
        frequency=payload.frequency,
        next_invoice_date=payload.next_invoice_date,
        due_days=payload.due_days,
        currency=company.currency,
        discount_percent=payload.discount_percent,
        tax_percent=payload.tax_percent,
        notes=payload.notes,
        line_templates=[line.model_dump(mode="json") for line in payload.lines],
        auto_issue=payload.auto_issue,
    )
    db.add(schedule)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DomainError(409, "recurring_invoice_conflict", "A recurring invoice schedule with this name already exists") from exc
    db.refresh(schedule)
    return schedule


@router.get("", response_model=list[RecurringInvoiceRead])
def list_schedules(
    active: bool | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[RecurringInvoiceSchedule]:
    stmt = select(RecurringInvoiceSchedule).where(
        RecurringInvoiceSchedule.company_id == user.company_id
    )
    if active is not None:
        stmt = stmt.where(RecurringInvoiceSchedule.is_active.is_(active))
    return list(db.scalars(stmt.order_by(
        RecurringInvoiceSchedule.next_invoice_date,
        RecurringInvoiceSchedule.name,
        RecurringInvoiceSchedule.id,
    )).all())


@router.get("/{schedule_id}", response_model=RecurringInvoiceRead)
def get_schedule(
    schedule_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecurringInvoiceSchedule:
    return scoped(db, user.company_id, schedule_id)


@router.patch("/{schedule_id}", response_model=RecurringInvoiceRead)
def update_schedule(
    schedule_id: UUID,
    payload: RecurringInvoiceUpdate,
    user: User = Depends(require_roles(*ROLES)),
    db: Session = Depends(get_db),
) -> RecurringInvoiceSchedule:
    schedule = scoped(db, user.company_id, schedule_id, lock=True)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise DomainError(422, "empty_update", "At least one field must be provided")
    if "name" in changes:
        changes["name"] = changes["name"].strip()
        if not changes["name"]:
            raise DomainError(422, "invalid_field", "name cannot be blank")
    lines = changes.pop("lines", None)
    if lines is not None:
        schedule.line_templates = [line.model_dump(mode="json") for line in lines]
    for key, value in changes.items():
        setattr(schedule, key, value)
    db.commit()
    db.refresh(schedule)
    return schedule


@router.post("/{schedule_id}/pause", response_model=RecurringInvoiceRead)
def pause_schedule(
    schedule_id: UUID,
    user: User = Depends(require_roles(*ROLES)),
    db: Session = Depends(get_db),
) -> RecurringInvoiceSchedule:
    schedule = scoped(db, user.company_id, schedule_id, lock=True)
    schedule.is_active = False
    db.commit()
    db.refresh(schedule)
    return schedule


@router.post("/{schedule_id}/resume", response_model=RecurringInvoiceRead)
def resume_schedule(
    schedule_id: UUID,
    user: User = Depends(require_roles(*ROLES)),
    db: Session = Depends(get_db),
) -> RecurringInvoiceSchedule:
    schedule = scoped(db, user.company_id, schedule_id, lock=True)
    schedule.is_active = True
    db.commit()
    db.refresh(schedule)
    return schedule
