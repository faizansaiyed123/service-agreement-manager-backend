from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class CustomerImportRowInput(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    kind: Literal["residential", "commercial"] = "residential"
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    notes: str | None = Field(default=None, max_length=5000)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be blank")
        return value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr | None) -> EmailStr | None:
        return value.lower() if value else None


class CustomerImportRequest(BaseModel):
    rows: list[CustomerImportRowInput] = Field(min_length=1, max_length=2000)


class CustomerImportPreviewRow(BaseModel):
    row_number: int
    valid: bool
    data: CustomerImportRowInput | None = None
    error_code: str | None = None
    error_message: str | None = None


class CustomerImportPreview(BaseModel):
    total_rows: int
    valid_rows: int
    invalid_rows: int
    rows: list[CustomerImportPreviewRow]


class CustomerImportRowRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    row_number: int
    status: str
    payload: dict
    customer_id: UUID | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class CustomerImportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    status: str
    total_rows: int
    imported_rows: int
    failed_rows: int
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CustomerImportDetail(CustomerImportRead):
    rows: list[CustomerImportRowRead]
