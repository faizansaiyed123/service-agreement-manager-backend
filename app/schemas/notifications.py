from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class NotificationCreate(BaseModel):
    event_type: str = Field(min_length=2, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    recipient_email: EmailStr
    subject: str = Field(min_length=1, max_length=250)
    body: str = Field(min_length=1, max_length=100000)
    payload: dict = Field(default_factory=dict)
    scheduled_at: datetime | None = None

    @field_validator("subject")
    @classmethod
    def safe_subject(cls, value: str) -> str:
        value = value.strip()
        if not value or "\r" in value or "\n" in value:
            raise ValueError("subject must be nonblank and contain no newlines")
        return value

    @field_validator("body")
    @classmethod
    def nonblank_body(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("body cannot be blank")
        return value

    @model_validator(mode="after")
    def require_timezone(self):
        if self.scheduled_at is not None and (
            self.scheduled_at.tzinfo is None or self.scheduled_at.utcoffset() is None
        ):
            raise ValueError("scheduled_at must include a timezone")
        return self


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    company_id: UUID
    created_by_user_id: UUID | None
    event_type: str
    channel: str
    recipient_email: EmailStr
    subject: str
    body: str
    payload: dict
    idempotency_key: str
    status: str
    scheduled_at: datetime
    next_attempt_at: datetime
    locked_until: datetime | None
    attempt_count: int
    max_attempts: int
    last_error: str | None
    provider_message_id: str | None
    sent_at: datetime | None
    created_at: datetime
    updated_at: datetime


class NotificationAttemptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    notification_id: UUID
    attempt_number: int
    status: str
    provider: str
    provider_message_id: str | None
    error_message: str | None
    started_at: datetime
    finished_at: datetime | None
