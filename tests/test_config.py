import pytest

from app.core.config import Settings


def valid_production_settings(**overrides) -> Settings:
    values = {
        "app_env": "production",
        "debug": False,
        "jwt_secret_key": "production-secret-value-that-is-longer-than-forty-eight-characters",
        "smtp_host": "smtp.example.com",
        "smtp_from_email": "no-reply@example.com",
        "smtp_starttls": True,
        "password_reset_url": "https://app.example.com/reset-password",
    }
    values.update(overrides)
    return Settings(**values)


def test_production_settings_require_secure_recovery_delivery():
    valid_production_settings().validate_production()

    with pytest.raises(ValueError, match="SMTP_HOST and SMTP_FROM_EMAIL"):
        valid_production_settings(smtp_host=None, smtp_from_email=None).validate_production()

    with pytest.raises(ValueError, match="PASSWORD_RESET_URL"):
        valid_production_settings(password_reset_url="http://app.example.com/reset-password").validate_production()

    with pytest.raises(ValueError, match="PASSWORD_RESET_URL"):
        valid_production_settings(password_reset_url="https://localhost/reset-password").validate_production()

    with pytest.raises(ValueError, match="SMTP_PASSWORD"):
        valid_production_settings(smtp_username="mailer").validate_production()


def test_production_settings_reject_debug_and_weak_jwt_secret():
    with pytest.raises(ValueError, match="DEBUG must be false"):
        valid_production_settings(debug=True).validate_production()

    with pytest.raises(ValueError, match="at least 48 characters"):
        valid_production_settings(jwt_secret_key="x" * 40).validate_production()
