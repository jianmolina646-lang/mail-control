"""Controles HTTP compartidos por el middleware de seguridad."""

from __future__ import annotations

import hmac
import logging
import secrets
import time

import redis

from .config import settings

logger = logging.getLogger("mail_control.security")
_redis = redis.Redis.from_url(settings.REDIS_URL, socket_timeout=1)

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
ALLOWED_METHODS = SAFE_METHODS | {"POST", "PATCH", "DELETE"}
CSRF_COOKIE_NAME = "mailctl_csrf"
CSRF_HEADER_NAME = "x-csrf-token"
BODY_CONTENT_TYPES = {
    "application/json",
    "application/x-www-form-urlencoded",
    "multipart/form-data",
}


def client_ip(headers, client_host: str | None) -> str:
    forwarded = headers.get("x-forwarded-for", "")
    return (
        (forwarded.split(",")[0].strip() if forwarded else "")
        or headers.get("x-real-ip", "")
        or client_host
        or "unknown"
    )


def content_type_allowed(method: str, content_length: int, content_type: str) -> bool:
    if method in SAFE_METHODS or content_length == 0:
        return True
    media_type = content_type.split(";", 1)[0].strip().lower()
    return media_type in BODY_CONTENT_TYPES


def csrf_valid(cookie_token: str, header_token: str) -> bool:
    return bool(cookie_token and header_token) and hmac.compare_digest(
        cookie_token,
        header_token,
    )


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def rate_limit(ip: str, path: str, method: str) -> tuple[bool, int]:
    """Ventana fija en Redis; ante una caída de Redis no bloquea la aplicación."""
    if path == "/api/health":
        return True, 0
    if path == "/api/auth/login":
        limit, window, bucket = settings.HTTP_LOGIN_RATE_LIMIT, 60, "login"
    elif path.startswith("/api/internal/agent/"):
        limit, window, bucket = settings.HTTP_AGENT_RATE_LIMIT, 60, "agent"
    elif method not in SAFE_METHODS:
        limit, window, bucket = settings.HTTP_WRITE_RATE_LIMIT, 60, "write"
    else:
        limit, window, bucket = settings.HTTP_RATE_LIMIT, 60, "general"
    slot = int(time.time()) // window
    key = f"mailctl:http-rate:{bucket}:{ip}:{slot}"
    try:
        count = _redis.incr(key)
        if count == 1:
            _redis.expire(key, window + 2)
        return count <= limit, max(0, window - (int(time.time()) % window))
    except redis.RedisError:
        logger.warning("rate_limit_unavailable ip=%s path=%s", ip, path)
        return True, 0


def audit_rejection(ip: str, method: str, path: str, reason: str) -> None:
    logger.warning(
        "request_rejected ip=%s method=%s path=%s reason=%s",
        ip,
        method,
        path[:300],
        reason,
    )
