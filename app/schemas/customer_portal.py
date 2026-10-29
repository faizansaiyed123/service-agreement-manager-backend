from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class CustomerPortalInviteCreate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=160)

    @field_validator("full_name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = " ".join(value.split())
        if not value:
            raise ValueError("Name cannot be blank")
        return value


class CustomerPortalInviteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: EmailStr
    full_name: str
    status: str
    expires_at: datetime


class CustomerPortalInvitePreview(BaseModel):
    email: EmailStr
    full_name: str
    company_name: str
    customer_name: str
    expires_at: datetime


class CustomerPortalAccept(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("full_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Name cannot be blank")
        return value

    @field_validator("password")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Password cannot be blank")
        return value


class CustomerPortalMembershipRead(BaseModel):
    membership_id: UUID
    customer_id: UUID
    company_id: UUID
    company_name: str
    customer_name: str


class CustomerPortalMe(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str
    memberships: list[CustomerPortalMembershipRead]


class CustomerPortalLocationRead(BaseModel):
    id: UUID
    name: str
    address_line1: str
    address_line2: str | None
    city: str
    region: str | None
    postal_code: str | None
    country_code: str
    is_active: bool


class CustomerPortalOverview(BaseModel):
    company_name: str
    customer_name: str
    customer_number: str
    customer_kind: str
    locations: list[CustomerPortalLocationRead]
    agreement_count: int
    open_work_order_count: int
    unpaid_invoice_count: int


class CustomerPortalAgreementLineRead(BaseModel):
    service_code: str
    name: str
    description: str | None
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal


class CustomerPortalAgreementRead(BaseModel):
    id: UUID
    agreement_number: str
    title: str
    status: str
    start_date: str
    end_date: str
    billing_frequency: str
    currency: str
    total_amount: Decimal
    terms_text: str
    lines: list[CustomerPortalAgreementLineRead]


class CustomerPortalEquipmentRead(BaseModel):
    id: UUID
    asset_number: str
    service_location_id: UUID
    category: str
    manufacturer: str | None
    model_number: str | None
    serial_number: str | None
    installed_on: str | None
    warranty_expires_on: str | None
    status: str


class CustomerPortalWorkOrderRead(BaseModel):
    id: UUID
    work_order_number: str
    title: str
    status: str
    priority: str
    scheduled_for: str
    appointment_start: datetime | None
    appointment_end: datetime | None
    service_location_name: str
    service_location_city: str
    equipment_label: str | None


class CustomerPortalInvoiceLineRead(BaseModel):
    service_code: str
    description: str
    details: str | None
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal


class CustomerPortalInvoiceRead(BaseModel):
    id: UUID
    invoice_number: str
    status: str
    invoice_date: str
    due_date: str
    currency: str
    subtotal: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    amount_paid: Decimal
    amount_refunded: Decimal
    credits_applied: Decimal
    balance_due: Decimal
    notes: str | None
    is_overdue: bool
    lines: list[CustomerPortalInvoiceLineRead]
    portal_status: Literal["payable", "paid"]


class CustomerPortalPaymentIntentRead(BaseModel):
    payment_intent_id: str
    client_secret: str
    amount: str
    currency: str
    test_mode: bool


class CustomerPortalPaymentConfirm(BaseModel):
    payment_intent_id: str = Field(min_length=1, max_length=255)


class CustomerPortalAccessRead(BaseModel):
    has_access: bool
    invited_email: EmailStr | None = None
    invitation_status: Literal["pending", "accepted", "revoked", "expired"] | None = None


class CustomerPortalRefundRead(BaseModel):
    id: UUID
    amount: Decimal
    refund_method: str
    reference: str | None
    reason: str
    refunded_at: datetime


class CustomerPortalPaymentRead(BaseModel):
    id: UUID
    invoice_id: UUID
    invoice_number: str
    amount: Decimal
    payment_method: str
    reference: str | None
    received_at: datetime
    refunds: list[CustomerPortalRefundRead]


class CustomerPortalAttachmentRead(BaseModel):
    id: UUID
    entity_type: Literal["customer", "service_location", "equipment", "agreement", "work_order", "invoice"]
    entity_id: UUID
    original_filename: str
    content_type: str
    size_bytes: int
    description: str | None
    created_at: datetime
