import pytest
from pydantic import ValidationError

from app.email_verification_schemas import EmailVerificationConfirm
from app.password_recovery_schemas import PasswordRecoveryConfirm
from app.schemas import RegisterRequest
from app.user_schemas import PasswordChange, PasswordReset, UserCreate


@pytest.mark.parametrize("model,values", [
    (RegisterRequest, {"company_name": "Example HVAC", "full_name": "Test Owner", "email": "owner@example.com", "password": " " * 12}),
    (UserCreate, {"full_name": "Team Member", "email": "team@example.com", "password": " " * 12}),
    (PasswordReset, {"new_password": " " * 12}),
    (PasswordChange, {"current_password": "old-password", "new_password": " " * 12}),
    (EmailVerificationConfirm, {"token": "x" * 43, "new_password": " " * 12}),
    (PasswordRecoveryConfirm, {"token": "x" * 43, "new_password": " " * 12}),
])
def test_password_inputs_reject_whitespace_only_values(model, values):
    with pytest.raises(ValidationError):
        model(**values)
