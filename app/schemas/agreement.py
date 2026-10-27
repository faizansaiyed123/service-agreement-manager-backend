from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AgreementLineInput(BaseModel):
    catalog_item_id: UUID | None = None
    name: str | None = Field(default=None, min_length=2, max_length=160)
    service_code: str | None = Field(default=None, min_length=2, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")
    description: str | None = Field(default=None, max_length=5000)
    quantity: Decimal = Field(default=Decimal("1.00"), gt=0, max_digits=10, decimal_places=2)
    unit_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)

    @model_validator(mode="after")
    def validate_line(self):
        if self.catalog_item_id is None and (not self.name or self.unit_price is None):
            raise ValueError("Custom lines require a name and unit_price")
        if self.catalog_item_id is not None and self.unit_price is not None:
            raise ValueError("Catalog-backed price is read from the service catalog")
        return self


class AgreementCreate(BaseModel):
    customer_id: UUID
    service_location_id: UUID
    title: str = Field(min_length=2, max_length=180)
    start_date: date
    end_date: date
    billing_frequency: Literal["monthly", "quarterly", "semi_annual", "annual", "one_time"] = "annual"
    auto_renew: bool = False
    renewal_notice_days: int = Field(default=30, ge=0, le=365)
    terms_text: str = Field(default="", max_length=20000)
    lines: list[AgreementLineInput] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def valid_date_range(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class AgreementUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=180)
    start_date: date | None = None
    end_date: date | None = None
    billing_frequency: Literal["monthly", "quarterly", "semi_annual", "annual", "one_time"] | None = None
    auto_renew: bool | None = None
    renewal_notice_days: int | None = Field(default=None, ge=0, le=365)
    terms_text: str | None = Field(default=None, max_length=20000)
    lines: list[AgreementLineInput] | None = Field(default=None, min_length=1, max_length=100)


class AcceptanceEvidence(BaseModel):
    accepted_by_name: str = Field(min_length=2, max_length=160)
    method: Literal["manual", "electronic"]
    reference: str | None = Field(default=None, max_length=255)


class ReasonRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)


class AgreementLineRead(ORMModel):
    id: UUID
    catalog_item_id: UUID | None
    service_code: str
    name: str
    description: str | None
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal


class AgreementRead(ORMModel):
    id: UUID
    company_id: UUID
    customer_id: UUID
    service_location_id: UUID
    agreement_number: str
    title: str
    status: str
    start_date: date
    end_date: date
    billing_frequency: str
    currency: str
    auto_renew: bool
    renewal_notice_days: int
    terms_text: str
    total_amount: Decimal
    accepted_by_name: str | None
    accepted_at: datetime | None
    acceptance_method: str | None
    acceptance_reference: str | None
    cancelled_at: datetime | None
    cancellation_reason: str | None
    version_number: int
    created_at: datetime
    updated_at: datetime
    lines: list[AgreementLineRead]


class AgreementVersionRead(ORMModel):
    id: UUID
    agreement_id: UUID
    version_number: int
    snapshot: dict
    change_reason: str
    created_by: UUID | None
    created_at: datetime


class AgreementEventRead(ORMModel):
    id: UUID
    agreement_id: UUID
    actor_user_id: UUID | None
    event_type: str
    from_status: str | None
    to_status: str | None
    detail: dict | None
    created_at: datetime
