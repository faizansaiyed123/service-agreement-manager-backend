from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

AttachmentEntityType = Literal[
    "customer",
    "service_location",
    "equipment",
    "agreement",
    "work_order",
    "invoice",
]


class AttachmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    entity_type: AttachmentEntityType
    entity_id: UUID
    original_filename: str
    content_type: str
    size_bytes: int
    sha256: str
    storage_key: str
    status: str
    customer_visible: bool
    deleted_at: datetime | None
    description: str | None
    uploaded_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime


class AttachmentUpdate(BaseModel):
    description: str | None = Field(default=None, max_length=4000)
    customer_visible: bool | None = None
