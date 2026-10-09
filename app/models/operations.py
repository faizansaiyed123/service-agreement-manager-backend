from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, JSON, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import Timestamped, UUIDPrimaryKey


class MaintenanceSchedule(Base, UUIDPrimaryKey, Timestamped):
    __tablename__ = "maintenance_schedules"
    __table_args__ = (
        CheckConstraint("frequency in ('monthly','quarterly','semi_annual','annual')", name="valid_frequency"),
    )
    company_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False)
    customer_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("customers.id", ondelete="RESTRICT"), index=True, nullable=False)
    service_location_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("service_locations.id", ondelete="RESTRICT"), nullable=False)
    equipment_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("equipment.id", ondelete="RESTRICT"))
    agreement_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("agreements.id", ondelete="RESTRICT"))
    created_by: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    frequency: Mapped[str] = mapped_column(String(24), nullable=False)
    next_due_date: Mapped[date] = mapped_column(Date(), nullable=False, index=True)
    checklist_template: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class WorkOrder(Base, UUIDPrimaryKey, Timestamped):
    __tablename__ = "work_orders"
    __table_args__ = (
        CheckConstraint("status in ('scheduled','assigned','in_progress','completed','cancelled')", name="valid_status"),
        CheckConstraint("priority in ('low','normal','high','emergency')", name="valid_priority"),
        CheckConstraint("((appointment_start is null and appointment_end is null) or (appointment_start is not null and appointment_end is not null and appointment_end > appointment_start))", name="valid_appointment_window"),
        UniqueConstraint("company_id", "work_order_number", name="company_work_order_number"),
        UniqueConstraint("maintenance_schedule_id", "occurrence_date", name="schedule_occurrence"),
    )
    company_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False)
    customer_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("customers.id", ondelete="RESTRICT"), index=True, nullable=False)
    service_location_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("service_locations.id", ondelete="RESTRICT"), nullable=False)
    equipment_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("equipment.id", ondelete="RESTRICT"))
    agreement_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("agreements.id", ondelete="RESTRICT"))
    maintenance_schedule_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("maintenance_schedules.id", ondelete="RESTRICT"), index=True)
    occurrence_date: Mapped[date | None] = mapped_column(Date())
    work_order_number: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="scheduled", nullable=False, index=True)
    priority: Mapped[str] = mapped_column(String(24), default="normal", nullable=False)
    scheduled_for: Mapped[date] = mapped_column(Date(), nullable=False, index=True)
    appointment_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    appointment_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assigned_to_user_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completion_notes: Mapped[str | None] = mapped_column(Text)
    technician_findings: Mapped[str | None] = mapped_column(Text)
    checklist_results: Mapped[dict | None] = mapped_column(JSON)
    customer_signoff_name: Mapped[str | None] = mapped_column(String(160))
    cancellation_reason: Mapped[str | None] = mapped_column(Text)


class WorkOrderEvent(Base, UUIDPrimaryKey):
    __tablename__ = "work_order_events"
    work_order_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("work_orders.id", ondelete="CASCADE"), index=True, nullable=False)
    actor_user_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(24))
    to_status: Mapped[str | None] = mapped_column(String(24))
    detail: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
