import calendar
from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.models import Agreement, Company, Customer, Equipment, MaintenanceSchedule, ServiceLocation, WorkOrder, WorkOrderEvent

MONTHS = {"monthly": 1, "quarterly": 3, "semi_annual": 6, "annual": 12}


def validate_context(
    db: Session,
    company_id: UUID,
    customer_id: UUID,
    location_id: UUID,
    equipment_id: UUID | None = None,
    agreement_id: UUID | None = None,
    for_date: date | None = None,
) -> tuple[Customer, ServiceLocation]:
    customer = db.scalar(select(Customer).where(
        Customer.id == customer_id,
        Customer.company_id == company_id,
    ))
    if customer is None or customer.status != "active":
        raise DomainError(404, "customer_not_found", "Active customer not found")
    location = db.scalar(select(ServiceLocation).where(
        ServiceLocation.id == location_id,
        ServiceLocation.company_id == company_id,
        ServiceLocation.customer_id == customer_id,
        ServiceLocation.is_active.is_(True),
    ))
    if location is None:
        raise DomainError(404, "service_location_not_found", "Active service location not found for customer")
    if equipment_id is not None:
        equipment = db.scalar(select(Equipment).where(
            Equipment.id == equipment_id,
            Equipment.company_id == company_id,
            Equipment.customer_id == customer_id,
            Equipment.service_location_id == location_id,
            Equipment.status == "active",
        ))
        if equipment is None:
            raise DomainError(404, "equipment_not_found", "Active equipment not found at this customer location")
    if agreement_id is not None:
        agreement = db.scalar(select(Agreement).where(
            Agreement.id == agreement_id,
            Agreement.company_id == company_id,
            Agreement.customer_id == customer_id,
            Agreement.service_location_id == location_id,
            Agreement.status == "active",
        ))
        if agreement is None:
            raise DomainError(409, "agreement_not_active", "An active matching agreement is required")
        if for_date is not None and not (agreement.start_date <= for_date <= agreement.end_date):
            raise DomainError(409, "agreement_out_of_term", "The scheduled date is outside the agreement term")
    return customer, location


def add_order_event(
    db: Session,
    order: WorkOrder,
    actor_id: UUID | None,
    name: str,
    previous: str | None = None,
    detail: dict | None = None,
) -> None:
    db.add(WorkOrderEvent(
        work_order_id=order.id,
        actor_user_id=actor_id,
        event_type=name,
        from_status=previous,
        to_status=order.status,
        detail=detail,
        created_at=datetime.now(UTC),
    ))


def next_occurrence(current: date, frequency: str) -> date:
    months = MONTHS[frequency]
    index = current.month - 1 + months
    year = current.year + index // 12
    month = index % 12 + 1
    day = min(current.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def create_work_order_number(db: Session, company_id: UUID) -> str:
    company = db.scalar(select(Company).where(Company.id == company_id).with_for_update())
    if company is None or not company.is_active:
        raise DomainError(403, "company_inactive", "Company account is inactive")
    company.work_order_sequence += 1
    return f"WO-{company.work_order_sequence:06d}"



def generate_scheduled_occurrence(
    db: Session,
    company_id: UUID,
    schedule_id: UUID,
    occurrence_date: date,
    actor_id: UUID | None,
    *,
    today: date | None = None,
) -> tuple[WorkOrder, bool]:
    """Create one scheduled occurrence in the caller's transaction.

    Returns (work_order, created). Callers commit. The row lock serializes
    schedule advancement, while the unique occurrence constraint is the final
    database-level duplicate guard.
    """
    schedule = db.scalar(select(MaintenanceSchedule).where(
        MaintenanceSchedule.id == schedule_id,
        MaintenanceSchedule.company_id == company_id,
    ).with_for_update())
    if schedule is None:
        raise DomainError(404, "schedule_not_found", "Maintenance schedule not found")

    existing = db.scalar(select(WorkOrder).where(
        WorkOrder.maintenance_schedule_id == schedule.id,
        WorkOrder.occurrence_date == occurrence_date,
    ))
    if existing is not None:
        return existing, False

    current_day = today or datetime.now(UTC).date()
    if not schedule.is_active:
        raise DomainError(409, "schedule_inactive", "Inactive maintenance schedules cannot generate work orders")
    if occurrence_date != schedule.next_due_date:
        raise DomainError(409, "occurrence_out_of_sequence", "occurrence_date must match the schedule's next due date")
    if occurrence_date > current_day:
        raise DomainError(409, "occurrence_not_due", "A future maintenance occurrence cannot be generated yet")

    validate_context(
        db, company_id, schedule.customer_id, schedule.service_location_id,
        schedule.equipment_id, schedule.agreement_id, occurrence_date,
    )
    order = WorkOrder(
        company_id=company_id,
        customer_id=schedule.customer_id,
        service_location_id=schedule.service_location_id,
        equipment_id=schedule.equipment_id,
        agreement_id=schedule.agreement_id,
        maintenance_schedule_id=schedule.id,
        occurrence_date=occurrence_date,
        work_order_number=create_work_order_number(db, company_id),
        title=schedule.name,
        description=schedule.description,
        priority="normal",
        scheduled_for=occurrence_date,
        status="scheduled",
    )
    db.add(order)
    db.flush()
    add_order_event(
        db, order, actor_id, "work_order.generated",
        detail={"schedule_id": str(schedule.id), "occurrence_date": occurrence_date.isoformat()},
    )
    schedule.next_due_date = next_occurrence(occurrence_date, schedule.frequency)
    schedule.last_generation_attempt_at = datetime.now(UTC)
    schedule.last_generation_error = None
    db.flush()
    return order, True
