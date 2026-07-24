"""Mail Control — Panel privado de correos masivos (TEAM JHELIZ)."""

import logging

from fastapi import FastAPI
from sqlalchemy import inspect, text

from .api.routes import router
from .core.config import settings
from .core.db import Base, SessionLocal, engine
from .core.security import hash_password

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url=None,
    openapi_url="/api/openapi.json" if settings.DEBUG else None,
)
app.include_router(router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_oauth_columns()
    _ensure_admin()


def _ensure_oauth_columns() -> None:
    """Migración compatible con instalaciones existentes sin Alembic."""
    columns = {
        item["name"] for item in inspect(engine).get_columns("mail_accounts")
    }
    statements = []
    if "auth_method" not in columns:
        statements.append(
            "ALTER TABLE mail_accounts ADD COLUMN auth_method VARCHAR(20) "
            "NOT NULL DEFAULT 'password'"
        )
    if "encrypted_oauth_cache" not in columns:
        statements.append(
            "ALTER TABLE mail_accounts ADD COLUMN encrypted_oauth_cache TEXT NULL"
        )
    if statements:
        with engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))
        logger.info("Esquema actualizado para Microsoft OAuth2")


def _ensure_admin() -> None:
    """Crea el usuario admin inicial si no existe (ADMIN_EMAIL/ADMIN_PASSWORD)."""
    from .models.models import User

    if not settings.ADMIN_PASSWORD:
        return
    db = SessionLocal()
    try:
        if db.query(User).filter(User.email == settings.ADMIN_EMAIL).first():
            return
        db.add(
            User(
                email=settings.ADMIN_EMAIL,
                hashed_password=hash_password(settings.ADMIN_PASSWORD),
                is_admin=True,
            )
        )
        db.commit()
        logger.info("Usuario admin creado: %s", settings.ADMIN_EMAIL)
    finally:
        db.close()
