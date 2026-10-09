import calendar
from datetime import UTC, date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.errors import DomainError
from app.db.session import get_db
from app.models import Agreement, Company, Customer, Equipment, MaintenanceSchedule, ServiceLocation, User, WorkOrder, WorkOrderEvent
from app.operations_schemas import AssignTechnician, CancelWorkOrder, GenerateOccurrence, ScheduleCreate, ScheduleRead, ScheduleUpdate, WorkOrderCompletion, WorkOrderCreate, WorkOrderEventRead, WorkOrderRead, WorkOrderUpdate

schedules_router = APIRouter(prefix="/maintenance/schedules", tags=["maintenance"])
work_orders_router = APIRouter(prefix="/work-orders", tags=["work orders"])
MONTHS = {"monthly": 1, "quarterly": 3, "semi_annual": 6, "annual": 12}


def scoped_schedule(db: Session, company_id: UUID, schedule_id: UUID) -> MaintenanceSchedule:
    obj = db.scalar(select(MaintenanceSchedule).where(
        MaintenanceSchedule.id == schedule_id, MaintenanceSchedule.company_id == company_id
    ))
    if obj is None:
        raise DomainError(404, "schedule_not_found", "Maintenance schedule not found")
    return obj


def scoped_order(db: Session, company_id: UUID, order_id: UUID) -> WorkOrder:
    obj = db.scalar(select(WorkOrder).where(WorkOrder.id == order_id, WorkOrder.company_id == company_id))
    if obj is None:
        raise DomainError(404, "work_order_not_found", "Work order not found")
    return obj


def validate_context(
    db: Session, company_id: UUID, customer_id: UUID, location_id: UUID,
    equipment_id: UUID | None = None, agreement_id: UUID | None = None, for_date: date | None = None,
) -> tuple[Customer, ServiceLocation]:
    customer = db.scalar(select(Customer).where(Customer.id == customer_id, Customer.company_id == company_id))
    if customer is None or customer.status != "active":
        raise DomainError(404, "customer_not_found", "Active customer not found")
    location = db.scalar(select(ServiceLocation).where(
        ServiceLocation.id == location_id, ServiceLocation.company_id == company_id,
        ServiceLocation.customer_id == customer_id, ServiceLocation.is_active.is_(True),
    ))
    if location is None:
        raise DomainError(404, "service_location_not_found", "Active service location not found for customer")
    if equipment_id is not None:
        equipment = db.scalar(select(Equipment).where(
            Equipment.id == equipment_id, Equipment.company_id == company_id,
            Equipment.customer_id == customer_id, Equipment.service_location_id == location_id,
            Equipment.status == "active",
        ))
        if equipment is None:
            raise DomainError(404, "equipment_not_found", "Active equipment not found at this customer location")
    if agreement_id is not None:
        agreement = db.scalar(select(Agreement).where(
            Agreement.id == agreement_id, Agreement.company_id == company_id,
            Agreement.customer_id == customer_id, Agreement.service_location_id == location_id,
            Agreement.status == "active",
        ))
        if agreement is None:
            raise DomainError(409, "agreement_not_active", "An active matching agreement is required")
        if for_date is not None and not (agreement.start_date <= for_date <= agreement.end_date):
            raise DomainError(409, "agreement_out_of_term", "The scheduled date is outside the agreement term")
    return customer, location


def add_order_event(db: Session, order: WorkOrder, actor_id: UUID, name: str, previous: str | None = None, detail: dict | None = None) -> None:
    db.add(WorkOrderEvent(
        work_order_id=order.id, actor_user_id=actor_id, event_type=name,
        from_status=previous, to_status=order.status, detail=detail, created_at=datetime.now(UTC),
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


@schedules_router.post("", response_model=ScheduleRead, status_code=201)
def create_schedule(payload: ScheduleCreate, user: User = Depends(require_roles("owner", "admin", "manager", "staff")), db: Session = Depends(get_db)) -> MaintenanceSchedule:
    validate_context(db, user.company_id, payload.customer_id, payload.service_location_id, payload.equipment_id, payload.agreement_id, payload.next_due_date)
    schedule = MaintenanceSchedule(
        company_id=user.company_id, customer_id=payload.customer_id, service_location_id=payload.service_location_id,
        equipment_id=payload.equipment_id, agreement_id=payload.agreement_id, created_by=user.id,
        name=payload.name, description=payload.description, frequency=payload.frequency,
        next_due_date=payload.next_due_date, checklist_template=payload.checklist_template,
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule


@schedules_router.get("", response_model=list[ScheduleRead])
def list_schedules(
    active: bool | None = None, due_through: date | None = None,
    limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> list[MaintenanceSchedule]:
    stmt = select(MaintenanceSchedule).where(MaintenanceSchedule.company_id == user.company_id)
    if active is not None:
        stmt = stmt.where(MaintenanceSchedule.is_active.is_(active))
    if due_through:
        stmt = stmt.where(MaintenanceSchedule.next_due_date <= due_through)
    return list(db.scalars(stmt.order_by(MaintenanceSchedule.next_due_date, MaintenanceSchedule.id).limit(limit).offset(offset)).all())


@schedules_router.get("/{schedule_id}", response_model=ScheduleRead)
def get_schedule(schedule_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> MaintenanceSchedule:
    return scoped_schedule(db, user.company_id, schedule_id)


@schedules_router.patch("/{schedule_id}", response_model=ScheduleRead)
def update_schedule(
    schedule_id: UUID, payload: ScheduleUpdate,
    user: User = Depends(require_roles("owner", "admin", "manager")),
    db: Session = Depends(get_db),
) -> MaintenanceSchedule:
    schedule = scoped_schedule(db, user.company_id, schedule_id)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise DomainError(422, "empty_update", "At least one field must be provided")
    for key, value in updates.items():
        if key == "name":
            value = value.strip()
            if not value:
                raise DomainError(422, "invalid_field", "name cannot be blank")
        if key == "checklist_template" and value is not None:
            value = [entry.strip() for entry in value]
            if any(not entry for entry in value) or len(set(value)) != len(value):
                raise DomainError(422, "invalid_checklist", "Checklist entries must be nonblank and unique")
        setattr(schedule, key, value)
    db.commit()
    db.refresh(schedule)
    return schedule


@schedules_router.post("/{schedule_id}/generate", response_model=WorkOrderRead, status_code=201)
def generate_scheduled_work_order(
    schedule_id: UUID, payload: GenerateOccurrence, response: Response,
    user: User = Depends(require_roles("owner", "admin", "manager", "staff")),
    db: Session = Depends(get_db),
) -> WorkOrder:
    existing = db.scalar(select(WorkOrder).join(MaintenanceSchedule).where(
        MaintenanceSchedule.id == schedule_id, MaintenanceSchedule.company_id == user.company_id,
        WorkOrder.occurrence_date == payload.occurrence_date,
    ))
    if existing is not None:
        response.status_code = 200
        return existing
    schedule = db.scalar(select(MaintenanceSchedule).where(
        MaintenanceSchedule.id == schedule_id, MaintenanceSchedule.company_id == user.company_id
    ).with_for_update())
    if schedule is None:
        raise DomainError(404, "schedule_not_found", "Maintenance schedule not found")
    db.refresh(schedule)
    existing = db.scalar(select(WorkOrder).where(
        WorkOrder.maintenance_schedule_id == schedule.id,
        WorkOrder.occurrence_date == payload.occurrence_date,
    ))
    if existing is not None:
        response.status_code = 200
        return existing
    if not schedule.is_active:
        raise DomainError(409, "schedule_inactive", "Inactive maintenance schedules cannot generate work orders")
    if payload.occurrence_date != schedule.next_due_date:
        raise DomainError(409, "occurrence_out_of_sequence", "occurrence_date must match the schedule's next due date")
    if payload.occurrence_date > date.today():
        raise DomainError(409, "occurrence_not_due", "A future maintenance occurrence cannot be generated yet")
    validate_context(db, user.company_id, schedule.customer_id, schedule.service_location_id, schedule.equipment_id, schedule.agreement_id, payload.occurrence_date)
    order = WorkOrder(
        company_id=user.company_id, customer_id=schedule.customer_id,
        service_location_id=schedule.service_location_id, equipment_id=schedule.equipment_id,
        agreement_id=schedule.agreement_id, maintenance_schedule_id=schedule.id,
        occurrence_date=payload.occurrence_date, work_order_number=create_work_order_number(db, user.company_id),
        title=schedule.name, description=schedule.description, priority="normal",
        scheduled_for=payload.occurrence_date, status="scheduled",
    )
    db.add(order)
    db.flush()
    add_order_event(db, order, user.id, "work_order.generated", detail={"schedule_id": str(schedule.id), "occurrence_date": payload.occurrence_date.isoformat()})
    schedule.next_due_date = next_occurrence(payload.occurrence_date, schedule.frequency)
    db.commit()
    db.refresh(order)
    return order


@work_orders_router.post("", response_model=WorkOrderRead, status_code=201)
def create_work_order(
    payload: WorkOrderCreate, user: User = Depends(require_roles("owner", "admin", "manager", "staff")),
    db: Session = Depends(get_db),
) -> WorkOrder:
    validate_context(db, user.company_id, payload.customer_id, payload.service_location_id, payload.equipment_id, payload.agreement_id, payload.scheduled_for)
    order = WorkOrder(
        company_id=user.company_id, customer_id=payload.customer_id, service_location_id=payload.service_location_id,
        equipment_id=payload.equipment_id, agreement_id=payload.agreement_id,
        work_order_number=create_work_order_number(db, user.company_id), title=payload.title.strip(),
        description=payload.description, priority=payload.priority, scheduled_for=payload.scheduled_for,
        appointment_start=payload.appointment_start, appointment_end=payload.appointment_end, status="scheduled",
    )
    db.add(order)
    db.flush()
    add_order_event(db, order, user.id, "work_order.created")
    db.commit()
    db.refresh(order)
    return order


@work_orders_router.get("", response_model=list[WorkOrderRead])
def list_work_orders(
    status: str | None = Query(default=None, pattern="^(scheduled|assigned|in_progress|completed|cancelled)$"),
    customer_id: UUID | None = None, scheduled_from: date | None = None, scheduled_to: date | None = None,
    limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> list[WorkOrder]:
    if scheduled_from and scheduled_to and scheduled_to < scheduled_from:
        raise DomainError(422, "invalid_date_range", "scheduled_to must be on or after scheduled_from")
    stmt = select(WorkOrder).where(WorkOrder.company_id == user.company_id)
    if status:
        stmt = stmt.where(WorkOrder.status == status)
    if customer_id:
        stmt = stmt.where(WorkOrder.customer_id == customer_id)
    if scheduled_from:
        stmt = stmt.where(WorkOrder.scheduled_for >= scheduled_from)
    if scheduled_to:
        stmt = stmt.where(WorkOrder.scheduled_for <= scheduled_to)
    return list(db.scalars(stmt.order_by(WorkOrder.scheduled_for, WorkOrder.created_at).limit(limit).offset(offset)).all())


@work_orders_router.get("/{order_id}", response_model=WorkOrderRead)
def get_work_order(order_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> WorkOrder:
    return scoped_order(db, user.company_id, order_id)


@work_orders_router.patch("/{order_id}", response_model=WorkOrderRead)
def update_work_order(
    order_id: UUID, payload: WorkOrderUpdate,
    user: User = Depends(require_roles("owner", "admin", "manager", "staff")),
    db: Session = Depends(get_db),
) -> WorkOrder:
    order = scoped_order(db, user.company_id, order_id)
    if order.status not in {"scheduled", "assigned"}:
        raise DomainError(409, "work_order_not_editable", "Only scheduled or assigned work orders can be edited")
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise DomainError(422, "empty_update", "At least one field must be provided")
    start = updates.get("appointment_start", order.appointment_start)
    end = updates.get("appointment_end", order.appointment_end)
    if (start is None) != (end is None) or (start is not None and end is not None and end <= start):
        raise DomainError(422, "invalid_appointment_window", "Appointment end must be after appointment start, and both must be supplied together")
    for key, value in updates.items():
        if key == "title":
            value = value.strip()
            if not value:
                raise DomainError(422, "invalid_field", "title cannot be blank")
        setattr(order, key, value)
    add_order_event(db, order, user.id, "work_order.updated", detail={"fields": list(updates)})
    db.commit()
    db.refresh(order)
    return order


@work_orders_router.post("/{order_id}/assign", response_model=WorkOrderRead)
def assign_technician(
    order_id: UUID, payload: AssignTechnician,
    user: User = Depends(require_roles("owner", "admin", "manager")),
    db: Session = Depends(get_db),
) -> WorkOrder:
    order = scoped_order(db, user.company_id, order_id)
    if order.status not in {"scheduled", "assigned"}:
        raise DomainError(409, "invalid_work_order_transition", "Only scheduled or assigned work orders can be assigned")
    tech = db.scalar(select(User).where(
        User.id == payload.technician_user_id, User.company_id == user.company_id,
        User.role == "technician", User.is_active.is_(True),
    ))
    if tech is None:
        raise DomainError(404, "technician_not_found", "Active technician not found in this company")
    previous = order.status
    order.assigned_to_user_id = tech.id
    order.assigned_at = datetime.now(UTC)
    order.status = "assigned"
    add_order_event(db, order, user.id, "work_order.assigned", previous, {"technician_user_id": str(tech.id)})
    db.commit()
    db.refresh(order)
    return order


@work_orders_router.post("/{order_id}/start", response_model=WorkOrderRead)
def start_work_order(
    order_id: UUID, user: User = Depends(require_roles("owner", "admin", "manager", "technician")),
    db: Session = Depends(get_db),
) -> WorkOrder:
    order = scoped_order(db, user.company_id, order_id)
    if user.role == "technician" and order.assigned_to_user_id != user.id:
        raise DomainError(403, "work_order_not_assigned", "Technicians can start only their own assigned work")
    if order.status != "assigned":
        raise DomainError(409, "invalid_work_order_transition", "Only assigned work orders can be started")
    previous = order.status
    order.status = "in_progress"
    order.started_at = datetime.now(UTC)
    add_order_event(db, order, user.id, "work_order.started", previous)
    db.commit()
    db.refresh(order)
    return order


@work_orders_router.post("/{order_id}/complete", response_model=WorkOrderRead)
def complete_work_order(
    order_id: UUID, payload: WorkOrderCompletion,
    user: User = Depends(require_roles("owner", "admin", "manager", "technician")),
    db: Session = Depends(get_db),
) -> WorkOrder:
    order = scoped_order(db, user.company_id, order_id)
    if user.role == "technician" and order.assigned_to_user_id != user.id:
        raise DomainError(403, "work_order_not_assigned", "Technicians can complete only their own assigned work")
    if order.status != "in_progress":
        raise DomainError(409, "invalid_work_order_transition", "Only in-progress work orders can be completed")
    if order.maintenance_schedule_id is not None:
        schedule = db.get(MaintenanceSchedule, order.maintenance_schedule_id)
        if schedule is not None:
            missing = [name for name in schedule.checklist_template if payload.checklist_results.get(name) is not True]
            if missing:
                raise DomainError(422, "checklist_incomplete", "Complete all required checklist items before closing the work order")
    previous = order.status
    order.status = "completed"
    order.completed_at = datetime.now(UTC)
    order.completion_notes = payload.completion_notes
    order.technician_findings = payload.technician_findings
    order.checklist_results = payload.checklist_results
    order.customer_signoff_name = payload.customer_signoff_name.strip() if payload.customer_signoff_name else None
    add_order_event(db, order, user.id, "work_order.completed", previous)
    db.commit()
    db.refresh(order)
    return order


@work_orders_router.post("/{order_id}/cancel", response_model=WorkOrderRead)
def cancel_work_order(
    order_id: UUID, payload: CancelWorkOrder,
    user: User = Depends(require_roles("owner", "admin", "manager")),
    db: Session = Depends(get_db),
) -> WorkOrder:
    order = scoped_order(db, user.company_id, order_id)
    if order.status not in {"scheduled", "assigned"}:
        raise DomainError(409, "invalid_work_order_transition", "Only scheduled or assigned work can be cancelled")
    previous = order.status
    order.status = "cancelled"
    order.cancellation_reason = payload.reason.strip()
    add_order_event(db, order, user.id, "work_order.cancelled", previous, {"reason": payload.reason})
    db.commit()
    db.refresh(order)
    return order


@work_orders_router.get("/{order_id}/events", response_model=list[WorkOrderEventRead])
def list_work_order_events(order_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[WorkOrderEvent]:
    scoped_order(db, user.company_id, order_id)
    return list(db.scalars(select(WorkOrderEvent).join(WorkOrder).where(
        WorkOrderEvent.work_order_id == order_id, WorkOrder.company_id == user.company_id
    ).order_by(WorkOrderEvent.created_at, WorkOrderEvent.id)).all())
