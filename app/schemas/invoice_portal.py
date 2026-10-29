from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class InvoicePortalSend(BaseModel):
    contact_id: UUID | None = None


class InvoicePortalSendRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    notification_id: UUID
    notification_status: str
    recipient_name: str
    recipient_email: EmailStr
    balance_due: str
    expires_at: str


class InvoicePortalPaymentIntentRequest(BaseModel):
    # The server calculates the amount and creates its own idempotency key.
    model_config = ConfigDict(extra="forbid")


class InvoicePortalPaymentConfirm(BaseModel):
    payment_intent_id: str = Field(min_length=1, max_length=255)


class InvoicePortalPaymentIntentRead(BaseModel):
    payment_intent_id: str
    client_secret: str
    amount: str
    currency: str
    test_mode: bool


class InvoicePortalLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    service_code: str
    description: str
    details: str | None
    quantity: str
    unit_price: str
    line_total: str


class InvoicePortalRead(BaseModel):
    invoice_number: str
    company_name: str
    customer_name: str
    recipient_name: str
    recipient_email: EmailStr
    invoice_date: str
    due_date: str
    issued_at: str | None
    currency: str
    status: str
    subtotal: str
    discount_amount: str
    tax_amount: str
    total_amount: str
    amount_paid: str
    amount_refunded: str
    credits_applied: str
    balance_due: str
    notes: str | None
    expires_at: str
    portal_status: Literal["payable", "paid"]
    lines: list[InvoicePortalLineRead]
