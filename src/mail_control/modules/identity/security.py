from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from mail_control.modules.identity.models import RoleName
from mail_control.settings import Settings

password_hasher = PasswordHasher()


@dataclass(frozen=True, slots=True)
class AccessClaims:
    user_id: UUID
    tenant_id: UUID
    role: RoleName


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (InvalidHashError, VerifyMismatchError):
        return False


def create_access_token(
    settings: Settings,
    *,
    user_id: UUID,
    tenant_id: UUID,
    role: RoleName,
) -> tuple[str, int]:
    now = datetime.now(UTC)
    ttl = timedelta(minutes=settings.access_token_ttl_minutes)
    payload = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "role": role.value,
        "type": "access",
        "iss": settings.jwt_issuer,
        "iat": now,
        "exp": now + ttl,
        "jti": secrets.token_urlsafe(16),
    }
    token = jwt.encode(payload, settings.app_secret_key, algorithm="HS256")
    return token, int(ttl.total_seconds())


def decode_access_token(settings: Settings, token: str) -> AccessClaims:
    payload: dict[str, Any] = jwt.decode(
        token,
        settings.app_secret_key,
        algorithms=["HS256"],
        issuer=settings.jwt_issuer,
        options={"require": ["sub", "tenant_id", "role", "type", "exp", "iat"]},
    )
    if payload["type"] != "access":
        raise jwt.InvalidTokenError("unexpected token type")
    return AccessClaims(
        user_id=UUID(payload["sub"]),
        tenant_id=UUID(payload["tenant_id"]),
        role=RoleName(payload["role"]),
    )


def create_refresh_token(tenant_id: UUID) -> tuple[str, str]:
    token = f"{tenant_id}.{secrets.token_urlsafe(48)}"
    return token, hash_refresh_token(token)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def refresh_token_tenant(token: str) -> UUID:
    tenant_id, separator, secret = token.partition(".")
    if not separator or not secret:
        raise ValueError("malformed refresh token")
    return UUID(tenant_id)
