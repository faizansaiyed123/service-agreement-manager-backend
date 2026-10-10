from datetime import date, datetime, time
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

BranchCode = Annotated[str, Field(min_length=2, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")]


def checked_timezone(value: str) -> str:
    value = value.strip()
    try:
        ZoneInfo(value)
    except (ValueError, ZoneInfoNotFoundError):
        raise ValueError("timezone must be a valid IANA time-zone name") from None
    return value


class BranchCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    code: BranchCode
    timezone: str = Field(default="UTC", min_length=1, max_length=64)
    address_line1: str | None = Field(default=None, max_length=180)
    address_line2: str | None = Field(default=None, max_length=180)
    city: str | None = Field(default=None, max_length=100)
    region: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=24)
    country_code: str = Field(default="US", min_length=2, max_length=2)
    phone: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None
    is_primary: bool = False

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name cannot be blank")
        return value

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        return checked_timezone(value)

    @field_validator("country_code")
    @classmethod
    def normalize_country_code(cls, value: str) -> str:
        value = value.strip().upper()
        if len(value) != 2 or not value.isalpha():
            raise ValueError("country_code must be a two-letter country code")
        return value


class BranchUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    code: BranchCode | None = None
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    address_line1: str | None = Field(default=None, max_length=180)
    address_line2: str | None = Field(default=None, max_length=180)
    city: str | None = Field(default=None, max_length=100)
    region: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=24)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    phone: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None
    is_primary: bool | None = None
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("name cannot be blank")
        return value

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str | None) -> str | None:
        return value.strip().upper() if value is not None else None

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str | None) -> str | None:
        return checked_timezone(value) if value is not None else None

    @field_validator("country_code")
    @classmethod
    def normalize_country_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().upper()
        if len(value) != 2 or not value.isalpha():
            raise ValueError("country_code must be a two-letter country code")
        return value


class BranchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    company_id: UUID
    name: str
    code: str
    timezone: str
    address_line1: str | None
    address_line2: str | None
    city: str | None
    region: str | None
    postal_code: str | None
    country_code: str
    phone: str | None
    email: EmailStr | None
    is_primary: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class BusinessHoursEntry(BaseModel):
    day_of_week: int = Field(ge=0, le=6, description="Monday=0 through Sunday=6")
    is_closed: bool = True
    opens_at: time | None = None
    closes_at: time | None = None

    @model_validator(mode="after")
    def validate_hours(self):
        if self.is_closed:
            if self.opens_at is not None or self.closes_at is not None:
                raise ValueError("Closed days must not define opens_at or closes_at")
        elif self.opens_at is None or self.closes_at is None or self.closes_at <= self.opens_at:
            raise ValueError("Open days require opens_at and closes_at with closing later than opening")
        return self


class BusinessHoursReplace(BaseModel):
    hours: list[BusinessHoursEntry] = Field(min_length=7, max_length=7)

    @model_validator(mode="after")
    def require_every_weekday_once(self):
        days = [item.day_of_week for item in self.hours]
        if set(days) != set(range(7)) or len(set(days)) != 7:
            raise ValueError("hours must contain each weekday exactly once (Monday=0 through Sunday=6)")
        self.hours.sort(key=lambda item: item.day_of_week)
        return self


class BusinessHoursRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    branch_id: UUID
    day_of_week: int
    is_closed: bool
    opens_at: time | None
    closes_at: time | None
    created_at: datetime
    updated_at: datetime


class BranchClosureCreate(BaseModel):
    closure_date: date
    name: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name cannot be blank")
        return value


class BranchClosureRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    branch_id: UUID
    closure_date: date
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
