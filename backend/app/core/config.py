"""Configuración central del sistema (variables de entorno)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- App ---
    APP_NAME: str = "Mail Control - TEAM JHELIZ"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me"  # JWT signing
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12
    ALLOWED_ORIGINS: str = "https://panel.ecormecejhelizstore.com"
    LOGIN_MAX_FAILURES: int = 5
    LOGIN_BLOCK_SECONDS: int = 15 * 60
    SESSION_COOKIE_NAME: str = "__Host-mailctl_session"
    SESSION_COOKIE_SECURE: bool = True
    # Token independiente para el agente local. Nunca reutilizar SECRET_KEY/JWT.
    MAIL_AGENT_API_TOKEN: str = ""
    MAIL_AGENT_CODE_MAX_AGE_SECONDS: int = 600

    # --- Bot privado de Telegram ---
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_ADMIN_CHAT_ID: int = 0
    TELEGRAM_NOTIFY_ALERTS: bool = True
    TELEGRAM_NOTIFY_ACCOUNT_ERRORS: bool = True
    TELEGRAM_DAILY_SUMMARY: bool = True
    TELEGRAM_SYSTEM_MONITORING: bool = True
    SYSTEM_DISK_ALERT_PERCENT: int = 80
    SYSTEM_MEMORY_ALERT_PERCENT: int = 90
    SYSTEM_QUEUE_ALERT_SIZE: int = 50

    # --- Encriptación de credenciales IMAP (Fernet, base64 de 32 bytes) ---
    CREDENTIALS_ENCRYPTION_KEY: str = ""

    # --- Microsoft OAuth2 / Entra ID ---
    MICROSOFT_CLIENT_ID: str = ""
    MICROSOFT_TENANT_ID: str = "common"
    MICROSOFT_CLIENT_SECRET: str = ""
    MICROSOFT_REDIRECT_URI: str = ""
    FRONTEND_URL: str = "http://localhost:5173"

    # --- DB / Redis ---
    DATABASE_URL: str = "postgresql+psycopg2://mailctl:mailctl@db:5432/mailctl"
    REDIS_URL: str = "redis://redis:6379/0"

    # --- Admin inicial ---
    ADMIN_EMAIL: str = "admin@ecormecejhelizstore.com"
    ADMIN_PASSWORD: str = ""

    # --- Límites de hardware (VPS 1 vCPU / 2 GB) ---
    # Máximo de conexiones IMAP concurrentes en TODO el sistema.
    IMAP_MAX_CONCURRENCY: int = 50
    # Cuántas cuentas procesa cada tarea de Celery por lote (chunk).
    IMAP_CHUNK_SIZE: int = 10
    # Correos máximos a traer por cuenta en cada ciclo (AUMENTADO para ver más historia).
    IMAP_FETCH_LIMIT: int = 100
    # Timeout de conexión IMAP en segundos (reducido para no bloquear workers).
    IMAP_TIMEOUT: int = 15
    # Cada cuántos minutos se cicla el escaneo completo de cuentas.
    SCAN_INTERVAL_MINUTES: int = 5

@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
