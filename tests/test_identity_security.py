from __future__ import annotations

from uuid import uuid4

import jwt
import pytest

from mail_control.modules.identity.models import RoleName
from mail_control.modules.identity.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    hash_password,
    hash_refresh_token,
    refresh_token_tenant,
    verify_password,
)
from mail_control.settings import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        app_secret_key="a-secure-test-key-with-at-least-32-characters",
        database_url="postgresql+asyncpg://test:test@localhost/test",
        redis_url="redis://localhost:6379/0",
        rabbitmq_url="amqp://guest:guest@localhost/",
    )


def test_password_hash_is_not_reversible() -> None:
    password = "Correct-Horse-Battery-Staple"
    password_hash = hash_password(password)
    assert password not in password_hash
    assert verify_password(password_hash, password)
    assert not verify_password(password_hash, "incorrect-password")


def test_access_token_preserves_tenant_boundary(settings: Settings) -> None:
    user_id = uuid4()
    tenant_id = uuid4()
    token, expires_in = create_access_token(
        settings,
        user_id=user_id,
        tenant_id=tenant_id,
        role=RoleName.ADMIN,
    )
    claims = decode_access_token(settings, token)
    assert expires_in == 900
    assert claims.user_id == user_id
    assert claims.tenant_id == tenant_id
    assert claims.role is RoleName.ADMIN


def test_access_token_rejects_wrong_signing_key(settings: Settings) -> None:
    token, _ = create_access_token(
        settings,
        user_id=uuid4(),
        tenant_id=uuid4(),
        role=RoleName.VIEWER,
    )
    wrong_settings = settings.model_copy(
        update={"app_secret_key": "a-different-secure-key-with-32-characters"}
    )
    with pytest.raises(jwt.InvalidSignatureError):
        decode_access_token(wrong_settings, token)


def test_refresh_token_contains_tenant_but_hash_hides_secret() -> None:
    tenant_id = uuid4()
    token, token_hash = create_refresh_token(tenant_id)
    assert refresh_token_tenant(token) == tenant_id
    assert token_hash == hash_refresh_token(token)
    assert token not in token_hash


def test_malformed_refresh_token_is_rejected() -> None:
    with pytest.raises(ValueError):
        refresh_token_tenant("not-a-refresh-token")
