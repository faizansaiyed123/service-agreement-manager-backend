from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.billing_schemas import InvoiceLineInput


class RecurringInvoiceCreate(BaseModel):
    customer_id: UUID
    service_location_id: UUID | None = None
    agreement_id: UUID | None = None
    name: str = Field(min_length=2, max_length=160)
    frequency: Literal["monthly", "quarterly", "semi_annual", "annual"]
    next_invoice_date: date
    due_days: int = Field(default=30, ge=0, le=365)
    discount_percent: Decimal = Field(default=Decimal("0.00"), ge=0, le=100, max_digits=5, decimal_places=2)
    tax_percent: Decimal = Field(default=Decimal("0.00"), ge=0, le=100, max_digits=5, decimal_places=2)
    notes: str | None = Field(default=None, max_length=10000)
    lines: list[InvoiceLineInput] = Field(min_length=1, max_length=100)
    auto_issue: bool = True

    @model_validator(mode="after")
    def normalize(self):
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("name cannot be blank")
        return self


class RecurringInvoiceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    frequency: Literal["monthly", "quarterly", "semi_annual", "annual"] | None = None
    next_invoice_date: date | None = None
    due_days: int | None = Field(default=None, ge=0, le=365)
    discount_percent: Decimal | None = Field(default=None, ge=0, le=100, max_digits=5, decimal_places=2)
    tax_percent: Decimal | None = Field(default=None, ge=0, le=100, max_digits=5, decimal_places=2)
    notes: str | None = Field(default=None, max_length=10000)
    lines: list[InvoiceLineInput] | None = Field(default=None, min_length=1, max_length=100)
    auto_issue: bool | None = None
    is_active: bool | None = None


class RecurringInvoiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    customer_id: UUID
    service_location_id: UUID | None
    agreement_id: UUID | None
    created_by_user_id: UUID | None
    name: str
    frequency: str
    next_invoice_date: date
    due_days: int
    currency: str
    discount_percent: Decimal
    tax_percent: Decimal
    notes: str | None
    line_templates: list
    auto_issue: bool
    is_active: bool
    last_invoice_id: UUID | None
    last_run_at: datetime | None
    last_run_error: str | None
    created_at: datetime
    updated_at: datetime
