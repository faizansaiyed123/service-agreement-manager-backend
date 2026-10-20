from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

ALLOWED_WEBHOOK_EVENTS = {
    "customer.created",
    "customer.updated",
    "agreement.created",
    "agreement.status_changed",
    "work_order.created",
    "work_order.status_changed",
    "invoice.issued",
    "invoice.status_changed",
    "payment.received",
    "maintenance.work_order_generated",
}


def normalize_events(value: list[str]) -> list[str]:
    normalized = sorted({event.strip() for event in value if event.strip()})
    unknown = [event for event in normalized if event not in ALLOWED_WEBHOOK_EVENTS]
    if unknown:
        raise ValueError(f"Unsupported webhook event(s): {', '.join(unknown)}")
    if not normalized:
        raise ValueError("At least one webhook event is required")
    return normalized


class WebhookEndpointCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    url: HttpUrl
    events: list[str] = Field(min_length=1, max_length=50)
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be blank")
        return value

    @field_validator("url")
    @classmethod
    def require_https(cls, value: HttpUrl) -> HttpUrl:
        if value.scheme != "https":
            raise ValueError("Webhook URL must use HTTPS")
        if value.username or value.password:
            raise ValueError("Webhook URL must not embed credentials")
        if value.port not in (None, 443):
            raise ValueError("Webhook URL must use the standard HTTPS port 443")
        return value

    @field_validator("events")
    @classmethod
    def validate_events(cls, value: list[str]) -> list[str]:
        return normalize_events(value)


class WebhookEndpointRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    url: str
    subscribed_events: list[str]
    is_active: bool
    last_delivery_at: datetime | None
    last_delivery_status: str | None
    created_at: datetime
    updated_at: datetime


class WebhookEndpointCreated(WebhookEndpointRead):
    secret: str


class WebhookEndpointUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    url: HttpUrl | None = None
    events: list[str] | None = Field(default=None, max_length=50)
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be blank")
        return value

    @field_validator("url")
    @classmethod
    def require_https(cls, value: HttpUrl | None) -> HttpUrl | None:
        if value is not None:
            if value.scheme != "https":
                raise ValueError("Webhook URL must use HTTPS")
            if value.username or value.password:
                raise ValueError("Webhook URL must not embed credentials")
            if value.port not in (None, 443):
                raise ValueError("Webhook URL must use the standard HTTPS port 443")
        return value

    @field_validator("events")
    @classmethod
    def validate_events(cls, value: list[str] | None) -> list[str] | None:
        return normalize_events(value) if value is not None else None


class WebhookDeliveryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    endpoint_id: UUID
    event_id: UUID
    event_type: str
    payload: dict[str, Any]
    status: str
    attempt_count: int
    max_attempts: int
    next_attempt_at: datetime
    locked_until: datetime | None
    http_status: int | None
    response_body: str | None
    last_error: str | None
    delivered_at: datetime | None
    created_at: datetime
    updated_at: datetime


class WebhookDeliveryAttemptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    delivery_id: UUID
    attempt_number: int
    status: str
    http_status: int | None
    response_body: str | None
    error_message: str | None
    started_at: datetime
    finished_at: datetime | None
