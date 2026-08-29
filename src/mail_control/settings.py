from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Mail Control Enterprise"
    app_env: str = "local"
    app_secret_key: str = Field(min_length=32)
    database_url: str
    system_database_url: str | None = None
    redis_url: str
    rabbitmq_url: str
    allowed_origins: Annotated[tuple[str, ...], NoDecode] = ("http://localhost:5173",)
    frontend_url: str = "http://localhost:5173"
    log_level: str = "INFO"
    access_token_ttl_minutes: int = Field(default=15, ge=5, le=60)
    refresh_token_ttl_days: int = Field(default=30, ge=1, le=90)
    session_idle_minutes: int = Field(default=30, ge=15, le=240)
    session_absolute_hours: int = Field(default=12, ge=1, le=72)
    jwt_issuer: str = "mail-control-enterprise"
    credential_encryption_key: str | None = None
    credential_encryption_key_file: str | None = None
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str = "http://localhost:8000/v1/providers/gmail/callback"
    microsoft_client_id: str | None = None
    microsoft_client_secret: str | None = None
    microsoft_redirect_uri: str = "http://localhost:8000/v1/providers/microsoft/callback"
    microsoft_graph_webhook_enabled: bool = False
    microsoft_graph_notification_url: str | None = None
    microsoft_graph_lifecycle_url: str | None = None
    microsoft_graph_subscription_hours: int = Field(default=144, ge=1, le=168)
    microsoft_graph_subscription_renewal_hours: int = Field(default=24, ge=1, le=72)
    microsoft_graph_webhook_dedupe_seconds: int = Field(default=120, ge=10, le=86400)
    google_login_redirect_uri: str = "http://localhost:8000/v1/auth/oauth/google/callback"
    microsoft_login_redirect_uri: str = "http://localhost:8000/v1/auth/oauth/microsoft/callback"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_use_tls: bool = True
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.6-flash"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5.4-nano"
    ai_provider: str = "openai"
    telegram_alerts_file: str | None = None
    telegram_account_alert_dedupe_seconds: int = Field(default=3600, ge=60, le=604800)
    gmail_push_enabled: bool = False
    gmail_pubsub_topic: str | None = None
    gmail_pubsub_audience: str | None = None
    gmail_pubsub_service_account: str | None = None
    gmail_pubsub_verification_token: str | None = None
    gmail_watch_label_ids: Annotated[tuple[str, ...], NoDecode] = ("INBOX",)
    gmail_watch_renewal_hours: int = Field(default=24, ge=1, le=144)
    gmail_push_dedupe_seconds: int = Field(default=120, ge=10, le=86400)

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(item.strip() for item in value.split(",") if item.strip())
        return value

    @field_validator("gmail_watch_label_ids", mode="before")
    @classmethod
    def split_gmail_watch_label_ids(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(item.strip() for item in value.split(",") if item.strip())
        return value

    @field_validator("ai_provider")
    @classmethod
    def validate_ai_provider(cls, value: str) -> str:
        normalized = value.strip().casefold()
        if normalized not in {"openai", "gemini"}:
            raise ValueError("AI_PROVIDER must be openai or gemini")
        return normalized

    @model_validator(mode="after")
    def load_credential_encryption_key_file(self) -> Settings:
        if not self.credential_encryption_key_file:
            return self
        path = Path(self.credential_encryption_key_file)
        try:
            key = path.read_text(encoding="utf-8").strip()
        except OSError as error:
            raise ValueError("credential encryption key file cannot be read") from error
        if len(key) < 32:
            raise ValueError("credential encryption key file must contain at least 32 characters")
        self.credential_encryption_key = key
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env.casefold() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
