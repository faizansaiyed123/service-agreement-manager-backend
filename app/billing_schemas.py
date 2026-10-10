from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class InvoiceLineInput(BaseModel):
    service_code: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")
    description: str = Field(min_length=2, max_length=240)
    details: str | None = Field(default=None, max_length=5000)
    quantity: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    unit_price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)


class InvoiceCreate(BaseModel):
    customer_id: UUID
    service_location_id: UUID | None = None
    agreement_id: UUID | None = None
    invoice_date: date = Field(default_factory=date.today)
    due_date: date
    notes: str | None = Field(default=None, max_length=10000)
    lines: list[InvoiceLineInput] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.due_date < self.invoice_date:
            raise ValueError("due_date must be on or after invoice_date")
        return self


class InvoiceUpdate(BaseModel):
    invoice_date: date | None = None
    due_date: date | None = None
    notes: str | None = Field(default=None, max_length=10000)
    lines: list[InvoiceLineInput] | None = Field(default=None, min_length=1, max_length=100)


class VoidInvoice(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)


class PaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    payment_method: Literal["cash", "check", "bank_transfer", "card", "other"]
    reference: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=5000)


class InvoiceLineRead(ORMModel):
    id: UUID
    service_code: str
    description: str
    details: str | None
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal


class InvoiceBaseRead(ORMModel):
    id: UUID
    company_id: UUID
    customer_id: UUID
    service_location_id: UUID | None
    agreement_id: UUID | None
    invoice_number: str
    status: str
    invoice_date: date
    due_date: date
    currency: str
    subtotal: Decimal
    total_amount: Decimal
    notes: str | None
    issued_at: datetime | None
    voided_at: datetime | None
    void_reason: str | None
    created_at: datetime
    updated_at: datetime
    lines: list[InvoiceLineRead]


class InvoiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    company_id: UUID
    customer_id: UUID
    service_location_id: UUID | None
    agreement_id: UUID | None
    invoice_number: str
    status: str
    invoice_date: date
    due_date: date
    currency: str
    subtotal: Decimal
    total_amount: Decimal
    notes: str | None
    issued_at: datetime | None
    voided_at: datetime | None
    void_reason: str | None
    created_at: datetime
    updated_at: datetime
    lines: list[InvoiceLineRead]
    amount_paid: Decimal
    balance_due: Decimal
    is_overdue: bool


class PaymentRead(ORMModel):
    id: UUID
    company_id: UUID
    invoice_id: UUID
    amount: Decimal
    payment_method: str
    reference: str | None
    received_at: datetime
    notes: str | None


class InvoiceEventRead(ORMModel):
    id: UUID
    invoice_id: UUID
    actor_user_id: UUID | None
    event_type: str
    from_status: str | None
    to_status: str | None
    detail: dict | None
    created_at: datetime
