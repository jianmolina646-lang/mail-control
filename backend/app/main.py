"""Mail Control — Panel privado de correos masivos (TEAM JHELIZ)."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy import inspect, text

from .api.routes import router
from .api.agent_routes import router as agent_router
from .core.config import settings
from .core.db import Base, SessionLocal, engine
from .core.security import hash_password
from .core import request_security

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
allowed_hosts = [
    host.strip()
    for host in settings.ALLOWED_HOSTS.split(",")
    if host.strip()
]
app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "X-CSRF-Token"],
)
app.include_router(router)
app.include_router(agent_router)


@app.middleware("http")
async def security_headers(request, call_next):
    method = request.method.upper()
    path = request.url.path
    ip = request_security.client_ip(
        request.headers,
        request.client.host if request.client else None,
    )

    def reject(status_code: int, detail: str, reason: str, **headers):
        request_security.audit_rejection(ip, method, path, reason)
        return JSONResponse(
            status_code=status_code,
            content={"detail": detail},
            headers={key: str(value) for key, value in headers.items()},
        )

    if method not in request_security.ALLOWED_METHODS:
        return reject(405, "Método no permitido", "method")

    raw_length = request.headers.get("content-length", "0")
    try:
        content_length = int(raw_length)
    except ValueError:
        return reject(400, "Content-Length inválido", "content_length_invalid")
    if content_length < 0 or content_length > settings.HTTP_MAX_BODY_BYTES:
        return reject(413, "Petición demasiado grande", "body_too_large")
    if not request_security.content_type_allowed(
        method,
        content_length,
        request.headers.get("content-type", ""),
    ):
        return reject(415, "Content-Type no permitido", "content_type")

    allowed, retry_after = request_security.rate_limit(ip, path, method)
    if not allowed:
        return reject(
            429,
            "Demasiadas peticiones. Intenta nuevamente en unos segundos.",
            "rate_limit",
            **{"Retry-After": retry_after},
        )

    if method not in request_security.SAFE_METHODS:
        origin = request.headers.get("origin")
        if origin and origin not in allowed_origins:
            return reject(403, "Origen no permitido", "origin")
        has_session = bool(request.cookies.get(settings.SESSION_COOKIE_NAME))
        is_internal_agent = path.startswith("/api/internal/agent/")
        if (
            has_session
            and path != "/api/auth/login"
            and not is_internal_agent
            and not request_security.csrf_valid(
                request.cookies.get(request_security.CSRF_COOKIE_NAME, ""),
                request.headers.get(request_security.CSRF_HEADER_NAME, ""),
            )
        ):
            return reject(403, "Token CSRF inválido", "csrf")

    response = await call_next(request)
    if (
        not request.cookies.get(request_security.CSRF_COOKIE_NAME)
        and (method in request_security.SAFE_METHODS or path == "/api/auth/login")
    ):
        response.set_cookie(
            key=request_security.CSRF_COOKIE_NAME,
            value=request_security.new_csrf_token(),
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            secure=settings.SESSION_COOKIE_SECURE,
            httponly=False,
            samesite="strict",
            path="/",
        )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=()"
    )
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    response.headers["Cache-Control"] = "no-store"
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
    _ensure_user_totp_columns()
    _ensure_admin()


def _ensure_user_totp_columns() -> None:
    columns = {item["name"] for item in inspect(engine).get_columns("users")}
    statements = []
    if "totp_secret_encrypted" not in columns:
        statements.append(
            "ALTER TABLE users ADD COLUMN totp_secret_encrypted TEXT NOT NULL DEFAULT ''"
        )
    if "totp_enabled" not in columns:
        statements.append(
            "ALTER TABLE users ADD COLUMN totp_enabled BOOLEAN NOT NULL DEFAULT FALSE"
        )
    if "recovery_code_hashes" not in columns:
        statements.append(
            "ALTER TABLE users ADD COLUMN recovery_code_hashes TEXT NOT NULL DEFAULT '[]'"
        )
    if statements:
        with engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))
        logger.info("Esquema actualizado para autenticación TOTP")


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
