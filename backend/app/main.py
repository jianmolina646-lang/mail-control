"""Mail Control — Panel privado de correos masivos (TEAM JHELIZ)."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import inspect, text

from .api.routes import router
from .api.agent_routes import router as agent_router
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
allowed_origins = [
    origin.strip()
    for origin in settings.ALLOWED_ORIGINS.split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)
app.include_router(router)
app.include_router(agent_router)


@app.middleware("http")
async def security_headers(request, call_next):
    if request.method in {"POST", "PATCH", "PUT", "DELETE"}:
        origin = request.headers.get("origin")
        if origin and origin not in allowed_origins:
            return JSONResponse(
                status_code=403,
                content={"detail": "Origen no permitido"},
            )
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=()"
    )
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Strict-Transport-Security"] = (
        "max-age=31536000; includeSubDomains"
    )
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )
    return response


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_oauth_columns()
    _ensure_message_folder_columns()
    _ensure_message_security_columns()
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


def _ensure_message_folder_columns() -> None:
    """Permite guardar UIDs independientes para cada carpeta IMAP."""
    columns = {
        item["name"] for item in inspect(engine).get_columns("messages")
    }
    if "folder_name" not in columns:
        with engine.begin() as connection:
            connection.execute(text(
                "ALTER TABLE messages ADD COLUMN folder_name VARCHAR(512) "
                "NOT NULL DEFAULT 'INBOX'"
            ))
            connection.execute(text(
                "ALTER TABLE messages DROP CONSTRAINT IF EXISTS "
                "uq_message_account_uid"
            ))
            connection.execute(text(
                "ALTER TABLE messages ADD CONSTRAINT "
                "uq_message_account_folder_uid "
                "UNIQUE (account_id, folder_name, uid)"
            ))
        logger.info("Esquema actualizado para sincronización IMAP multicarpeta")


def _ensure_message_security_columns() -> None:
    """Añade indicadores de confianza del remitente a instalaciones existentes."""
    columns = {
        item["name"] for item in inspect(engine).get_columns("messages")
    }
    statements = []
    if "sender_trusted" not in columns:
        statements.append(
            "ALTER TABLE messages ADD COLUMN sender_trusted BOOLEAN "
            "NOT NULL DEFAULT TRUE"
        )
    if "security_warning" not in columns:
        statements.append(
            "ALTER TABLE messages ADD COLUMN security_warning VARCHAR(500) "
            "NOT NULL DEFAULT ''"
        )
    if statements:
        with engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))
        logger.info("Esquema actualizado con protección contra suplantación")


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
