from pydantic import BaseModel, EmailStr, Field, field_validator


class PasswordRecoveryRequest(BaseModel):
    email: EmailStr


class PasswordRecoveryConfirm(BaseModel):
    token: str = Field(min_length=32, max_length=256)
    new_password: str = Field(min_length=12, max_length=128)

    @field_validator("new_password")
    @classmethod
    def reject_blank_password(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Password cannot be blank")
        return value
