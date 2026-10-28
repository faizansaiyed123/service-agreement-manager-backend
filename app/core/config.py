import json
from functools import lru_cache
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr
from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    app_name: str = "Service Agreement Manager API"
    app_env: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    database_url: str = Field(..., description="PostgreSQL connection URL")
    postgres_password: SecretStr | None = None
    jwt_secret_key: str = Field(..., min_length=32, description="JWT signing secret (min 32 chars)")
    access_token_minutes: int = 15
    refresh_token_days: int = 14
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000", "http://localhost:5173"]
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    allow_public_registration: bool = True
    redis_url: str | None = None
    log_level: str = "INFO"
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None
    smtp_starttls: bool = True
    smtp_timeout_seconds: int = Field(default=10, ge=1, le=60)
    notification_poll_seconds: int = 5
    notification_lease_seconds: int = 60
    notification_default_max_attempts: int = 5
    password_reset_token_minutes: int = Field(default=30, ge=1, le=1440)
    password_reset_cooldown_seconds: int = Field(default=60, ge=0, le=86400)
    password_reset_url: str = "http://localhost:3000/reset-password"
    email_verification_token_minutes: int = Field(default=60, ge=5, le=1440)
    email_verification_cooldown_seconds: int = Field(default=60, ge=0, le=86400)
    email_verification_url: str = "http://localhost:3000/verify-email"
    storage_backend: str = "local"
    storage_root: str = "./storage"
    storage_max_file_bytes: int = Field(default=25 * 1024 * 1024, ge=1, le=500 * 1024 * 1024)
    storage_bucket: str | None = None
    storage_region: str = "us-east-1"
    storage_endpoint_url: str | None = None
    storage_access_key_id: str | None = None
    storage_secret_access_key: str | None = None
webhook_encryption_key: str = Field(..., min_length=32, description="Webhook payload encryption key")
    notification_encryption_key: str = Field(..., min_length=32, description="Notification payload encryption key")
    webhook_poll_seconds: int = Field(default=5, ge=1, le=300)
    webhook_lease_seconds: int = Field(default=60, ge=5, le=3600)
    webhook_default_max_attempts: int = Field(default=8, ge=1, le=20)
    sms_provider: str = "disabled"
    sms_api_url: str | None = None
    sms_api_token: str | None = None
    sms_from: str | None = None
    sms_timeout_seconds: int = Field(default=10, ge=1, le=60)
    sms_poll_seconds: int = Field(default=10, ge=1, le=300)
    sms_lease_seconds: int = Field(default=60, ge=5, le=3600)
    sms_default_max_attempts: int = Field(default=5, ge=1, le=10)
    billing_poll_seconds: int = Field(default=60, ge=5, le=3600)
    stripe_enabled: bool = False
    stripe_secret_key: str | None = None
    stripe_publishable_key: str | None = None
    stripe_webhook_secret: str | None = None

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("["):
                parsed = json.loads(stripped)
                if not isinstance(parsed, list):
                    raise ValueError("CORS_ORIGINS must be a JSON array or comma-separated list")
                return parsed
            return [origin.strip() for origin in stripped.split(",") if origin.strip()]
        return value

    @staticmethod
    def _is_secret_placeholder(value: str) -> bool:
        normalized = value.strip().lower()
        return any(marker in normalized for marker in ("replace-with-", "change-this", "unsafe-development"))

    def validate_production(self) -> None:
        if len(self.jwt_secret_key) < 32:
            raise ValueError("JWT_SECRET_KEY must contain at least 32 characters")
        if self.app_env.lower() == "production":
            if self.debug:
                raise ValueError("DEBUG must be false in production")
            if self._is_secret_placeholder(self.jwt_secret_key) or len(self.jwt_secret_key) < 48:
                raise ValueError("Production requires a unique JWT_SECRET_KEY of at least 48 characters")
            if self._is_secret_placeholder(self.webhook_encryption_key) or len(self.webhook_encryption_key) < 32:
                raise ValueError("Production requires a unique WEBHOOK_ENCRYPTION_KEY of at least 32 characters")
            if self._is_secret_placeholder(self.notification_encryption_key) or len(self.notification_encryption_key) < 32:
                raise ValueError("Production requires a unique NOTIFICATION_ENCRYPTION_KEY of at least 32 characters")
            database = urlsplit(self.database_url)
            database_host = (database.hostname or "").lower()
            database_password = database.password or ""
            if (
                database.scheme != "postgresql+psycopg"
                or not database_host
                or not database.username
                or len(database_password) < 32
                or self._is_secret_placeholder(database_password)
            ):
                raise ValueError("Production DATABASE_URL must use PostgreSQL credentials with a non-placeholder password of at least 32 characters")
            if database_host in {"localhost", "127.0.0.1", "::1"} or database_host.endswith(".localhost"):
                raise ValueError("Production DATABASE_URL cannot point to localhost")
            if database_host == "db":
                compose_password = self.postgres_password.get_secret_value() if self.postgres_password else ""
                if (
                    len(compose_password) < 32
                    or not compose_password.isalnum()
                    or self._is_secret_placeholder(compose_password)
                    or database_password != compose_password
                    or compose_password in {self.jwt_secret_key, self.webhook_encryption_key, self.notification_encryption_key}
                ):
                    raise ValueError(
                        "Production Compose requires a unique POSTGRES_PASSWORD of at least 32 URL-safe alphanumeric characters matching DATABASE_URL"
                    )
            elif not database_host.endswith(".internal"):
                database_options = dict(item.split("=", 1) for item in database.query.split("&") if "=" in item)
                if database_options.get("sslmode") not in {"require", "verify-ca", "verify-full"}:
                    raise ValueError("Production external PostgreSQL connections must use sslmode=require or stronger")
            if not self.redis_url:
                raise ValueError("Production requires REDIS_URL for shared authentication rate limits")
            redis = urlsplit(self.redis_url)
            redis_host = (redis.hostname or "").lower()
            if (
                redis.scheme not in {"redis", "rediss"}
                or not redis_host
                or redis_host in {"localhost", "127.0.0.1", "::1"}
                or redis_host.endswith(".localhost")
                or not redis.password
                or len(redis.password) < 32
                or self._is_secret_placeholder(redis.password)
            ):
                raise ValueError("Production REDIS_URL must use Redis authentication and a non-local host")
            if redis.scheme == "redis" and redis_host not in {"redis"} and not redis_host.endswith(".internal"):
                raise ValueError("Production external Redis services must use TLS (rediss://)")
            if not self.cors_origins:
                raise ValueError("Production CORS_ORIGINS must include the public HTTPS app origin for cookie-session CSRF protection")
            if "*" in self.cors_origins:
                raise ValueError("Production CORS_ORIGINS cannot contain wildcard origins when credentials are enabled")
            for origin in self.cors_origins:
                parsed_origin = urlsplit(origin)
                hostname = (parsed_origin.hostname or "").lower()
                if (
                    parsed_origin.scheme != "https"
                    or not hostname
                    or hostname in {"localhost", "127.0.0.1", "::1"}
                    or hostname.endswith(".localhost")
                    or parsed_origin.path
                    or parsed_origin.query
                    or parsed_origin.fragment
                    or parsed_origin.username
                    or parsed_origin.password
                ):
                    raise ValueError(
                        "Production CORS_ORIGINS must contain only public HTTPS origins "
                        "without paths, credentials, queries, or fragments"
                    )
            if self.storage_backend.lower() in {"s3", "s3-compatible"}:
                if not self.storage_bucket:
                    raise ValueError("S3 storage requires STORAGE_BUCKET in production")
                if self.storage_endpoint_url and urlsplit(self.storage_endpoint_url).scheme != "https":
                    raise ValueError("Production S3-compatible storage endpoints must use HTTPS")
            if self.sms_provider == "http":
                if not self.sms_api_url or not self.sms_from:
                    raise ValueError("HTTP SMS provider requires SMS_API_URL and SMS_FROM")
                if urlsplit(self.sms_api_url).scheme != "https":
                    raise ValueError("Production SMS_API_URL must use HTTPS")
            if not self.smtp_host or not self.smtp_from_email:
                raise ValueError("Production requires SMTP_HOST and SMTP_FROM_EMAIL for account recovery delivery")
            if not self.smtp_starttls:
                raise ValueError("SMTP_STARTTLS must be enabled in production")
            if self.smtp_username and not self.smtp_password:
                raise ValueError("SMTP_PASSWORD is required when SMTP_USERNAME is configured")
            trusted_origins = {origin.lower() for origin in self.cors_origins}
            for value in (self.password_reset_url, self.email_verification_url):
                page = urlsplit(value)
                origin = (page.scheme + "://" + page.netloc).lower()
                invalid_local_host = not page.hostname or page.hostname.lower() in {"localhost", "127.0.0.1", "::1"} or page.hostname.lower().endswith(".localhost")
                if page.scheme != "https" or page.username or page.password or invalid_local_host or page.query or page.fragment or origin not in trusted_origins:
                    raise ValueError("Production recovery and verification URLs must use HTTPS on a trusted CORS_ORIGINS host and have no query or fragment")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_production()
    return settings
