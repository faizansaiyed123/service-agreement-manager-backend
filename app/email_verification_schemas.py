from pydantic import BaseModel, EmailStr, Field


class RegistrationPending(BaseModel):
    message: str


class EmailVerificationRequest(BaseModel):
    email: EmailStr


class EmailVerificationConfirm(BaseModel):
    token: str = Field(min_length=32, max_length=256)
