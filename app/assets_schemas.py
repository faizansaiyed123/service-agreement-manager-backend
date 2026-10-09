from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class EquipmentCreate(BaseModel):
    customer_id: UUID
    service_location_id: UUID
    category: str = Field(min_length=2, max_length=60)
    manufacturer: str | None = Field(default=None, max_length=120)
    model_number: str | None = Field(default=None, max_length=120)
    serial_number: str | None = Field(default=None, max_length=120)
    installed_on: date | None = None
    warranty_expires_on: date | None = None
    notes: str | None = Field(default=None, max_length=5000)


class EquipmentUpdate(BaseModel):
    category: str | None = Field(default=None, min_length=2, max_length=60)
    manufacturer: str | None = Field(default=None, max_length=120)
    model_number: str | None = Field(default=None, max_length=120)
    serial_number: str | None = Field(default=None, max_length=120)
    installed_on: date | None = None
    warranty_expires_on: date | None = None
    status: Literal["active", "inactive", "decommissioned"] | None = None
    notes: str | None = Field(default=None, max_length=5000)


class EquipmentRead(ORMModel):
    id: UUID
    company_id: UUID
    customer_id: UUID
    service_location_id: UUID
    asset_number: str
    category: str
    manufacturer: str | None
    model_number: str | None
    serial_number: str | None
    installed_on: date | None
    warranty_expires_on: date | None
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime


class ServiceCatalogCreate(BaseModel):
    service_code: str = Field(min_length=2, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=2, max_length=160)
    category: str = Field(min_length=2, max_length=60)
    description: str | None = Field(default=None, max_length=5000)
    unit_price: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=12, decimal_places=2)
    duration_minutes: int = Field(default=0, ge=0, le=100000)


class ServiceCatalogUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    category: str | None = Field(default=None, min_length=2, max_length=60)
    description: str | None = Field(default=None, max_length=5000)
    unit_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    duration_minutes: int | None = Field(default=None, ge=0, le=100000)
    is_active: bool | None = None


class ServiceCatalogRead(ORMModel):
    id: UUID
    company_id: UUID
    service_code: str
    name: str
    category: str
    description: str | None
    unit_price: Decimal
    duration_minutes: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
