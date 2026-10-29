from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class AgreementPortalSend(BaseModel):
    contact_id: UUID | None = None


class AgreementPortalSendRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    notification_id: UUID
    notification_status: str
    recipient_name: str
    recipient_email: EmailStr
    agreement_version: int
    expires_at: str


class AgreementPortalResponse(BaseModel):
    decision: Literal["accept", "reject"]
    rejection_reason: str | None = Field(default=None, max_length=2000)
    acceptance_confirmation: bool = False

    @model_validator(mode="after")
    def validate_rejection_reason(self):
        if self.decision == "accept" and not self.acceptance_confirmation:
            raise ValueError("Acceptance confirmation is required")
        if self.decision == "reject" and self.rejection_reason is not None:
            reason = self.rejection_reason.strip()
            if reason:
                self.rejection_reason = reason
            else:
                self.rejection_reason = None
        elif self.decision == "accept" and self.rejection_reason:
            raise ValueError("rejection_reason is only valid when rejecting an agreement")
        return self


class AgreementPortalLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    service_code: str
    name: str
    description: str | None
    quantity: str
    unit_price: str
    line_total: str


class AgreementPortalRead(BaseModel):
    agreement_number: str
    title: str
    company_name: str
    customer_name: str
    recipient_name: str
    recipient_email: EmailStr
    service_location_name: str
    service_location_city: str
    service_location_region: str | None
    service_location_country: str
    start_date: str
    end_date: str
    billing_frequency: str
    currency: str
    auto_renew: bool
    terms_text: str
    total_amount: str
    version_number: int
    expires_at: str
    portal_status: Literal["pending", "accepted", "rejected", "unavailable"]
    accepted_at: str | None = None
    rejected_at: str | None = None
    rejection_reason: str | None = None
    lines: list[AgreementPortalLineRead]
