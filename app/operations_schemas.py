from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ScheduleCreate(BaseModel):
    customer_id: UUID
    service_location_id: UUID
    equipment_id: UUID | None = None
    agreement_id: UUID | None = None
    name: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=5000)
    frequency: Literal["monthly", "quarterly", "semi_annual", "annual"]
    next_due_date: date
    checklist_template: list[str] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def normalize_checklist(self):
        self.name = self.name.strip()
        self.checklist_template = [item.strip() for item in self.checklist_template]
        if not self.name or any(not item for item in self.checklist_template):
            raise ValueError("Name and checklist entries cannot be blank")
        if len(set(self.checklist_template)) != len(self.checklist_template):
            raise ValueError("Checklist entries must be unique")
        return self


class ScheduleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=5000)
    frequency: Literal["monthly", "quarterly", "semi_annual", "annual"] | None = None
    next_due_date: date | None = None
    checklist_template: list[str] | None = Field(default=None, max_length=50)
    is_active: bool | None = None


class ScheduleRead(ORMModel):
    id: UUID
    company_id: UUID
    customer_id: UUID
    service_location_id: UUID
    equipment_id: UUID | None
    agreement_id: UUID | None
    created_by: UUID | None
    name: str
    description: str | None
    frequency: str
    next_due_date: date
    checklist_template: list[str]
    is_active: bool
    last_generation_attempt_at: datetime | None
    last_generation_error: str | None
    created_at: datetime
    updated_at: datetime


class GenerateOccurrence(BaseModel):
    occurrence_date: date


class WorkOrderCreate(BaseModel):
    customer_id: UUID
    service_location_id: UUID
    equipment_id: UUID | None = None
    agreement_id: UUID | None = None
    title: str = Field(min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=10000)
    priority: Literal["low", "normal", "high", "emergency"] = "normal"
    scheduled_for: date
    appointment_start: datetime | None = None
    appointment_end: datetime | None = None

    @model_validator(mode="after")
    def validate_appointment(self):
        validate_appointment_window(self.appointment_start, self.appointment_end)
        self.title = self.title.strip()
        if not self.title:
            raise ValueError("title cannot be blank")
        return self


class WorkOrderUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=10000)
    priority: Literal["low", "normal", "high", "emergency"] | None = None
    scheduled_for: date | None = None
    appointment_start: datetime | None = None
    appointment_end: datetime | None = None

    @model_validator(mode="after")
    def validate_appointment(self):
        if "appointment_start" in self.model_fields_set or "appointment_end" in self.model_fields_set:
            validate_appointment_window(self.appointment_start, self.appointment_end)
        return self


def validate_appointment_window(start: datetime | None, end: datetime | None) -> None:
    if (start is None) != (end is None):
        raise ValueError("appointment_start and appointment_end must be supplied together")
    if start is not None and end is not None:
        if start.tzinfo is None or start.utcoffset() is None or end.tzinfo is None or end.utcoffset() is None:
            raise ValueError("Appointment datetimes must include a timezone")
        if end <= start:
            raise ValueError("appointment_end must be later than appointment_start")


class AssignTechnician(BaseModel):
    technician_user_id: UUID


class WorkOrderCompletion(BaseModel):
    completion_notes: str | None = Field(default=None, max_length=10000)
    technician_findings: str | None = Field(default=None, max_length=10000)
    checklist_results: dict[str, bool] = Field(default_factory=dict)
    customer_signoff_name: str | None = Field(default=None, max_length=160)


class CancelWorkOrder(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)


class WorkOrderRead(ORMModel):
    id: UUID
    company_id: UUID
    customer_id: UUID
    service_location_id: UUID
    equipment_id: UUID | None
    agreement_id: UUID | None
    maintenance_schedule_id: UUID | None
    occurrence_date: date | None
    work_order_number: str
    title: str
    description: str | None
    status: str
    priority: str
    scheduled_for: date
    appointment_start: datetime | None
    appointment_end: datetime | None
    assigned_to_user_id: UUID | None
    assigned_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    completion_notes: str | None
    technician_findings: str | None
    checklist_results: dict | None
    customer_signoff_name: str | None
    cancellation_reason: str | None
    created_at: datetime
    updated_at: datetime


class WorkOrderEventRead(ORMModel):
    id: UUID
    work_order_id: UUID
    actor_user_id: UUID | None
    event_type: str
    from_status: str | None
    to_status: str | None
    detail: dict | None
    created_at: datetime
