from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class RegisterRequest(BaseModel):
    company_name: str = Field(min_length=2, max_length=160)
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class UserRead(ORMModel):
    id: UUID
    company_id: UUID
    email: EmailStr
    full_name: str
    role: str
    is_active: bool


class CompanyRead(ORMModel):
    id: UUID
    name: str
    legal_name: str | None
    timezone: str
    currency: str
    is_active: bool


class CompanyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    legal_name: str | None = Field(default=None, max_length=200)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    currency: str | None = Field(default=None, min_length=3, max_length=3)


class CustomerCreate(BaseModel):
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


class CustomerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=180)
    kind: Literal["residential", "commercial"] | None = None
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    notes: str | None = Field(default=None, max_length=5000)
    status: Literal["active", "inactive"] | None = None


class CustomerRead(ORMModel):
    id: UUID
    company_id: UUID
    customer_number: str
    kind: str
    name: str
    email: EmailStr | None
    phone: str | None
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime


class ContactCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=160)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    is_billing_contact: bool = False


class ContactRead(ORMModel):
    id: UUID
    customer_id: UUID
    full_name: str
    email: EmailStr | None
    phone: str | None
    is_billing_contact: bool


class ServiceLocationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    address_line1: str = Field(min_length=1, max_length=180)
    address_line2: str | None = Field(default=None, max_length=180)
    city: str = Field(min_length=1, max_length=100)
    region: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=24)
    country_code: str = Field(default="US", min_length=2, max_length=2)
    access_instructions: str | None = Field(default=None, max_length=5000)


class ServiceLocationRead(ORMModel):
    id: UUID
    customer_id: UUID
    name: str
    address_line1: str
    address_line2: str | None
    city: str
    region: str | None
    postal_code: str | None
    country_code: str
    access_instructions: str | None
    is_active: bool
