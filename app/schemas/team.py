from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class TechnicianInvitationCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    branch_ids: list[UUID] = Field(default_factory=list, max_length=100)
    skills: list[str] = Field(default_factory=list, max_length=25)

    @field_validator("full_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Name cannot be blank")
        return value

    @field_validator("email")
    @classmethod
    def clean_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()

    @field_validator("skills")
    @classmethod
    def clean_skills(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            clean = " ".join(value.split())
            normalized = clean.casefold()
            if not clean or len(clean) > 80:
                raise ValueError("Skills must contain 1–80 nonblank characters")
            if normalized not in seen:
                result.append(clean)
                seen.add(normalized)
        return result


class TechnicianInvitationAccept(BaseModel):
    password: str = Field(min_length=12, max_length=128)

    @field_validator("password")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Password cannot be blank")
        return value


class TechnicianInvitationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: EmailStr
    full_name: str
    branch_ids: list
    skills: list
    status: str
    expires_at: datetime
    created_at: datetime


class TechnicianInvitePreview(BaseModel):
    email: EmailStr
    full_name: str
    company_name: str
    expires_at: datetime


class TechnicianProfileRead(BaseModel):
    id: UUID
    full_name: str
    email: EmailStr
    is_active: bool
    skills: list[str]
    branch_ids: list[UUID]
    branch_names: list[str]


class TechnicianProfileUpdate(BaseModel):
    branch_ids: list[UUID] = Field(min_length=1, max_length=100)
    skills: list[str] = Field(default_factory=list, max_length=25)

    @field_validator("skills")
    @classmethod
    def clean_profile_skills(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            clean = " ".join(value.split())
            normalized = clean.casefold()
            if not clean or len(clean) > 80:
                raise ValueError("Skills must contain 1–80 nonblank characters")
            if normalized not in seen:
                result.append(clean)
                seen.add(normalized)
        return result
