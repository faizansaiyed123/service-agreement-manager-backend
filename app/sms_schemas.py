from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SmsCreate(BaseModel):
    event_type: str = Field(min_length=2, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    recipient_phone: str = Field(min_length=6, max_length=40)
    body: str = Field(min_length=1, max_length=1600)
    payload: dict = Field(default_factory=dict)
    scheduled_at: datetime | None = None


class SmsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    event_type: str
    recipient_phone: str
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
