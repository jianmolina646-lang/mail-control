from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException, Response

from mail_control.api import gmail, microsoft
from mail_control.api.mail_oauth import (
    MailOAuthFailure,
    bind_browser,
    cookie_name,
    finish_redirect,
    validate_callback_actor,
    validate_target_identity,
)
from mail_control.modules.identity.models import RoleName, TenantStatus
from mail_control.modules.mail.models import AccountStatus, MailProvider
from tests.test_settings import base_settings


@pytest.mark.parametrize("provider", list(MailProvider))
def test_oauth_browser_cookie_is_private_and_flow_specific(provider):
    settings = base_settings(app_env="production")
    response = Response()
    bind_browser(
        response, provider, "https://example.invalid/authorize?state=one", "nonce", settings
    )
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=lax" in cookie
    assert f"Path=/v1/providers/{provider.value}/callback" in cookie
    assert cookie_name(provider, "one") != cookie_name(provider, "two")
    assert response.headers["cache-control"] == "no-store"


def test_oauth_error_redirect_is_local_and_never_contains_provider_description():
    settings = base_settings(frontend_url="https://panel.example.invalid")
    response = finish_redirect(settings, MailProvider.GMAIL, "state", error="account_mismatch")
    assert response.status_code == 303
    assert response.headers["location"] == (
        "https://panel.example.invalid/cuentas?oauth_error=account_mismatch"
    )
    assert "Max-Age=0" in response.headers["set-cookie"]


@pytest.mark.asyncio
async def test_callback_rejects_other_browser_before_database_or_token_exchange():
    session = AsyncMock()
    with pytest.raises(MailOAuthFailure, match="browser_mismatch"):
        await validate_callback_actor(
            SimpleNamespace(cookies={}),
            session,
            provider=MailProvider.GMAIL,
            state="state",
            nonce="nonce",
            tenant_id=uuid4(),
            user_id=uuid4(),
        )
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "role,active,tenant_status",
    [
        (RoleName.VIEWER, True, TenantStatus.ACTIVE),
        (RoleName.OPERATOR, False, TenantStatus.ACTIVE),
        (RoleName.OWNER, True, TenantStatus.SUSPENDED),
    ],
)
async def test_callback_rechecks_current_user_permission(role, active, tenant_status):
    session = AsyncMock()
    session.scalar.side_effect = [SimpleNamespace(role=role, is_active=active), tenant_status]
    request = SimpleNamespace(cookies={cookie_name(MailProvider.GMAIL, "state"): "nonce"})
    with pytest.raises(MailOAuthFailure, match="permission_changed"):
        await validate_callback_actor(
            request,
            session,
            provider=MailProvider.GMAIL,
            state="state",
            nonce="nonce",
            tenant_id=uuid4(),
            user_id=uuid4(),
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "module,provider", [(gmail, MailProvider.GMAIL), (microsoft, MailProvider.MICROSOFT)]
)
async def test_provider_cancellation_redirects_without_exchanging_code(
    monkeypatch, module, provider
):
    state = SimpleNamespace(tenant_id=uuid4(), user_id=uuid4(), browser_nonce="nonce")
    oauth = SimpleNamespace(consume_state=AsyncMock(return_value=state), exchange_code=AsyncMock())
    monkeypatch.setattr(module, "configured_oauth", lambda *args: oauth)
    monkeypatch.setattr(module, "get_settings", base_settings)
    monkeypatch.setattr(module, "validate_callback_actor", AsyncMock())
    response = await module.callback(
        SimpleNamespace(), AsyncMock(), state="state", code=None, error="access_denied"
    )
    assert response.status_code == 303
    assert response.headers["location"].endswith("oauth_error=cancelled")
    oauth.exchange_code.assert_not_awaited()


@pytest.mark.asyncio
async def test_reauthorization_cannot_replace_selected_identity(monkeypatch):
    from mail_control.api import mail_oauth

    original = SimpleNamespace(provider_account_id="original@example.invalid")
    monkeypatch.setattr(mail_oauth, "target_account", AsyncMock(return_value=original))
    with pytest.raises(MailOAuthFailure, match="account_mismatch"):
        await validate_target_identity(
            AsyncMock(),
            tenant_id=uuid4(),
            account_id=uuid4(),
            provider=MailProvider.GMAIL,
            provider_account_id="different@example.invalid",
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "module,wrong_provider", [(gmail, MailProvider.MICROSOFT), (microsoft, MailProvider.GMAIL)]
)
async def test_sync_route_rejects_wrong_provider_without_publishing(
    monkeypatch, module, wrong_provider
):
    mailbox = SimpleNamespace(provider=wrong_provider, status=AccountStatus.CONNECTED)
    repo = SimpleNamespace(account_by_id=AsyncMock(return_value=mailbox))
    monkeypatch.setattr(module, "MailRepository", lambda session: repo)
    enqueue = AsyncMock()
    monkeypatch.setattr(module, "enqueue", enqueue)
    principal = SimpleNamespace(claims=SimpleNamespace(tenant_id=uuid4()))
    with pytest.raises(HTTPException) as error:
        await module.request_sync(uuid4(), SimpleNamespace(), principal, AsyncMock())
    assert error.value.status_code == 404
    enqueue.assert_not_awaited()
