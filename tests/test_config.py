import pytest

from app.core.config import Settings


def valid_production_settings(**overrides) -> Settings:
    values = {
        "app_env": "production",
        "database_url": "postgresql+psycopg://sam:uniqueCiDatabasePasswordLongEnough123456@db:5432/service_agreements",
        "postgres_password": "uniqueCiDatabasePasswordLongEnough123456",
        "debug": False,
        "allow_public_registration": True,
        "cors_origins": ["https://app.example.com"],
        "jwt_secret_key": "production-secret-value-that-is-longer-than-forty-eight-characters",
        "redis_url": "redis://:unique-ci-redis-password-at-least-32-chars-123456@redis:6379/0",
        "smtp_host": "smtp.example.com",
        "smtp_from_email": "no-reply@example.com",
        "smtp_starttls": True,
        "password_reset_url": "https://app.example.com/reset-password",
        "email_verification_url": "https://app.example.com/verify-email",
        "webhook_encryption_key": "production-webhook-secret-value-that-is-at-least-32-chars",
        "notification_encryption_key": "production-notification-secret-value-over-32-characters",
    }
    values.update(overrides)
    return Settings(**values)


def test_production_settings_allow_signup_when_verification_is_configured():
    valid_production_settings(allow_public_registration=True).validate_production()

    with pytest.raises(ValueError, match="recovery and verification URLs"):
        valid_production_settings(email_verification_url="http://app.example.com/verify-email").validate_production()

    with pytest.raises(ValueError, match="recovery and verification URLs"):
        valid_production_settings(email_verification_url="https://untrusted.example/verify-email").validate_production()


def test_production_settings_require_authenticated_private_or_tls_redis():
    with pytest.raises(ValueError, match="REDIS_URL"):
        valid_production_settings(redis_url=None).validate_production()

    with pytest.raises(ValueError, match="REDIS_URL"):
        valid_production_settings(redis_url="redis://redis:6379/0").validate_production()

    with pytest.raises(ValueError, match="TLS"):
        valid_production_settings(redis_url="redis://:long-secure-ci-redis-password-1234567890@cache.example.com:6379/0").validate_production()

    valid_production_settings(redis_url="rediss://:long-secure-ci-redis-password-1234567890@cache.example.com:6379/0").validate_production()


def test_production_settings_require_strong_database_credentials_and_tls():
    with pytest.raises(ValueError, match="DATABASE_URL"):
        valid_production_settings(database_url="postgresql+psycopg://sam:sam_dev_only@localhost:5432/service_agreements").validate_production()

    with pytest.raises(ValueError, match="localhost"):
        valid_production_settings(
            database_url="postgresql+psycopg://sam:uniqueCiDatabasePasswordLongEnough123456@localhost:5432/service_agreements"
        ).validate_production()

    with pytest.raises(ValueError, match="sslmode"):
        valid_production_settings(
            database_url="postgresql+psycopg://sam:uniqueCiDatabasePasswordLongEnough123456@db.example.com:5432/service_agreements"
        ).validate_production()

    valid_production_settings(
        database_url="postgresql+psycopg://sam:uniqueCiDatabasePasswordLongEnough123456@db.example.com:5432/service_agreements?sslmode=verify-full"
    ).validate_production()


def test_production_settings_require_secure_recovery_delivery():
    valid_production_settings().validate_production()

    with pytest.raises(ValueError, match="SMTP_HOST and SMTP_FROM_EMAIL"):
        valid_production_settings(smtp_host=None, smtp_from_email=None).validate_production()

    with pytest.raises(ValueError, match="recovery and verification URLs"):
        valid_production_settings(password_reset_url="http://app.example.com/reset-password").validate_production()

    with pytest.raises(ValueError, match="recovery and verification URLs"):
        valid_production_settings(password_reset_url="https://localhost/reset-password").validate_production()

    with pytest.raises(ValueError, match="SMTP_PASSWORD"):
        valid_production_settings(smtp_username="mailer").validate_production()


def test_production_settings_reject_debug_and_weak_jwt_secret():
    with pytest.raises(ValueError, match="DEBUG must be false"):
        valid_production_settings(debug=True).validate_production()

    with pytest.raises(ValueError, match="at least 48 characters"):
        valid_production_settings(jwt_secret_key="x" * 40).validate_production()



def test_cors_origins_accept_comma_separated_and_json_environment_values():
    comma_separated = Settings(cors_origins="http://localhost:3000,http://localhost:5173")
    assert comma_separated.cors_origins == ["http://localhost:3000", "http://localhost:5173"]

    json_array = Settings(cors_origins='["https://app.example.com","https://admin.example.com"]')
    assert json_array.cors_origins == ["https://app.example.com", "https://admin.example.com"]



def test_production_settings_require_secure_external_endpoints():
    with pytest.raises(ValueError, match="CORS_ORIGINS"):
        valid_production_settings(cors_origins=["*"]).validate_production()

    with pytest.raises(ValueError, match="public HTTPS origins"):
        valid_production_settings(cors_origins=["http://app.example.com"]).validate_production()

    with pytest.raises(ValueError, match="public HTTPS origins"):
        valid_production_settings(cors_origins=["https://localhost:5173"]).validate_production()

    with pytest.raises(ValueError, match="public HTTPS origins"):
        valid_production_settings(cors_origins=["https://app.example.com/dashboard"]).validate_production()

    valid_production_settings(cors_origins=["https://app.example.com"]).validate_production()
    valid_production_settings(cookie_samesite="lax").validate_production()
    with pytest.raises(ValueError, match="CORS_ORIGINS must include"):
        valid_production_settings(cors_origins=[]).validate_production()

    with pytest.raises(ValueError, match="S3-compatible storage endpoints"):
        valid_production_settings(
            storage_backend="s3-compatible",
            storage_bucket="service-agreement-files",
            storage_endpoint_url="http://minio.example.com",
        ).validate_production()

    with pytest.raises(ValueError, match="SMS_API_URL"):
        valid_production_settings(
            sms_provider="http",
            sms_api_url="http://sms.example.com/send",
            sms_from="+15550000000",
        ).validate_production()



def test_production_compose_requires_a_strong_matching_database_password():
    password = "A9" * 32
    database_url = f"postgresql+psycopg://sam:{password}@db:5432/service_agreements"
    valid_production_settings(database_url=database_url, postgres_password=password).validate_production()

    with pytest.raises(ValueError, match="POSTGRES_PASSWORD"):
        valid_production_settings(
            database_url=database_url,
            postgres_password="B8" * 32,
        ).validate_production()

    with pytest.raises(ValueError, match="POSTGRES_PASSWORD"):
        valid_production_settings(
            database_url="postgresql+psycopg://sam:REPLACE_WITH_URL_SAFE_RANDOM_PASSWORD@db:5432/service_agreements",
            postgres_password="REPLACE_WITH_URL_SAFE_RANDOM_PASSWORD",
        ).validate_production()

def test_production_settings_reject_secret_placeholders():
    with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
        valid_production_settings(
            jwt_secret_key="replace-with-a-random-secret-of-at-least-64-characters-000000000000"
        ).validate_production()

    with pytest.raises(ValueError, match="WEBHOOK_ENCRYPTION_KEY"):
        valid_production_settings(
            webhook_encryption_key="replace-with-a-random-webhook-secret-of-at-least-64-characters"
        ).validate_production()

    with pytest.raises(ValueError, match="NOTIFICATION_ENCRYPTION_KEY"):
        valid_production_settings(
            notification_encryption_key="replace-with-a-random-notification-secret-of-at-least-64-characters"
        ).validate_production()
