from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    app_name: str = "Service Agreement Manager API"
    app_env: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://sam:sam_dev_only@localhost:5432/service_agreements"
    jwt_secret_key: str = "unsafe-development-secret-change-this-please"
    access_token_minutes: int = 15
    refresh_token_days: int = 14
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    log_level: str = "INFO"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None
    smtp_starttls: bool = True
    smtp_timeout_seconds: int = 10
    notification_poll_seconds: int = 5
    notification_lease_seconds: int = 60
    notification_default_max_attempts: int = 5
    password_reset_token_minutes: int = 30
    password_reset_cooldown_seconds: int = 60
    password_reset_url: str = "http://localhost:3000/reset-password"

    def validate_production(self) -> None:
        if len(self.jwt_secret_key) < 32:
            raise ValueError("JWT_SECRET_KEY must contain at least 32 characters")
        if self.app_env.lower() == "production":
            if self.debug:
                raise ValueError("DEBUG must be false in production")
            if self.jwt_secret_key == "unsafe-development-secret-change-this-please" or len(self.jwt_secret_key) < 48:
                raise ValueError("Production requires a unique JWT_SECRET_KEY of at least 48 characters")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_production()
    return settings
