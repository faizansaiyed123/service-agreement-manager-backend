from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RenewalLineInput(BaseModel):
    service_code: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=5000)
    quantity: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    unit_price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)


class RenewalOfferCreate(BaseModel):
    proposed_start_date: date
    proposed_end_date: date
    expires_on: date
    title: str | None = Field(default=None, min_length=2, max_length=180)
    terms_text: str | None = Field(default=None, max_length=20000)
    billing_frequency: Literal["monthly", "quarterly", "semi_annual", "annual", "one_time"] | None = None
    auto_renew: bool | None = None
    renewal_notice_days: int | None = Field(default=None, ge=0, le=365)
    lines: list[RenewalLineInput] | None = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_term(self):
        if self.proposed_end_date < self.proposed_start_date:
            raise ValueError("proposed_end_date must be on or after proposed_start_date")
        if self.expires_on >= self.proposed_start_date:
            raise ValueError("expires_on must be before the proposed renewal start date")
        return self


class RenewalAcceptance(BaseModel):
    accepted_by_name: str = Field(min_length=2, max_length=160)
    method: Literal["manual", "electronic"]
    reference: str | None = Field(default=None, max_length=255)


class RenewalDecline(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)


class RenewalOfferRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    company_id: UUID
    source_agreement_id: UUID
    renewed_agreement_id: UUID | None
    offered_by_user_id: UUID | None
    status: str
    proposed_start_date: date
    proposed_end_date: date
    expires_on: date
    snapshot: dict
    accepted_by_name: str | None
    accepted_at: datetime | None
    acceptance_method: str | None
    acceptance_reference: str | None
    decline_reason: str | None
    created_at: datetime
    updated_at: datetime


class AgreementLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    catalog_item_id: UUID | None
    service_code: str
    name: str
    description: str | None
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal


class AgreementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
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
