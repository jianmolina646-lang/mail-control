"""Configuración central del sistema (variables de entorno)."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- App ---
    APP_NAME: str = "Mail Control - TEAM JHELIZ"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me"  # JWT signing
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12

    # --- Encriptación de credenciales IMAP (Fernet, base64 de 32 bytes) ---
    CREDENTIALS_ENCRYPTION_KEY: str = ""

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

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
