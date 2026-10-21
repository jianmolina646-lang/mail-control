from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest

from mail_control.microsoft_worker import start_transient_cooldown
from mail_control.modules.mail.microsoft import (
    MicrosoftGraphClient,
    MicrosoftOAuth,
    MicrosoftTransientError,
    microsoft_retry_at,
)
from mail_control.modules.mail.models import MailProvider
from mail_control.sync_scheduler import enqueue_due_accounts
from tests.test_sync_scheduler_resilience import mock_resources


@pytest.mark.parametrize("value", ["nan", "inf", "1e999", "9" * 200, "wrong", "-10"])
def test_invalid_retry_headers_do_not_crash_or_create_infinite_wait(value):
    response = httpx.Response(429, headers={"Retry-After": value})
    assert microsoft_retry_at(response) is None


def test_retry_after_http_date_and_delta_seconds():
    now = datetime.now(UTC)
    deadline = microsoft_retry_at(httpx.Response(429, headers={"Retry-After": "120"}))
    assert now + timedelta(seconds=120) <= deadline <= datetime.now(UTC) + timedelta(seconds=120)
    date = datetime(2099, 1, 1, tzinfo=UTC)
    assert microsoft_retry_at(httpx.Response(503, headers={
        "Retry-After": format_datetime(date, usegmt=True),
    })) == date


@pytest.mark.asyncio
@pytest.mark.parametrize("oauth", [False, True])
async def test_long_retry_after_survives_provider_error_and_sets_worker_cooldown(
    monkeypatch, oauth,
):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(429, json={"error": "invalid_grant"}, headers={"Retry-After": "600"})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real_client(
        transport=httpx.MockTransport(handler), **kw,
    ))
    sleep = AsyncMock(side_effect=AssertionError("long waits must release the worker"))
    monkeypatch.setattr("mail_control.modules.mail.microsoft.asyncio.sleep", sleep)
    with pytest.raises(MicrosoftTransientError) as caught:
        if oauth:
            await MicrosoftOAuth(None, client_id="fake", client_secret="fake",
                                 redirect_uri="https://example.invalid").refresh_access_token("fake")
        else:
            await MicrosoftGraphClient("fake").profile()
    assert len(requests) == 1
    assert caught.value.retry_at is not None
    resources = SimpleNamespace(redis=SimpleNamespace(set=AsyncMock()))
    account_id = uuid4()
    cooldown = await start_transient_cooldown(resources, account_id, caught.value)
    assert 600 <= cooldown <= 602
    resources.redis.set.assert_awaited_once_with(
        f"mail:sync:cooldown:microsoft:{account_id}", "1", ex=cooldown,
    )


@pytest.mark.asyncio
async def test_microsoft_scheduler_respects_provider_cooldown_then_resumes():
    account_id, tenant_id = uuid4(), uuid4()
    values = {f"mail:sync:cooldown:microsoft:{account_id}": b"1"}
    resources, _session, channel = mock_resources(
        [(account_id, tenant_id, MailProvider.MICROSOFT)], values,
    )
    assert await enqueue_due_accounts(resources, 60) == 0
    channel.default_exchange.publish.assert_not_awaited()
    values.clear()
    assert await enqueue_due_accounts(resources, 60) == 1
    channel.default_exchange.publish.assert_awaited_once()


@pytest.mark.asyncio
async def test_short_graph_retry_then_success_and_permanent_403(monkeypatch):
    statuses = [429, 200, 403]
    real_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real_client(
        transport=httpx.MockTransport(lambda request: httpx.Response(
            statuses.pop(0), json={"id": "fake"}, headers={"Retry-After": "2"},
        )), **kw,
    ))
    sleep = AsyncMock()
    monkeypatch.setattr("mail_control.modules.mail.microsoft.asyncio.sleep", sleep)
    assert await MicrosoftGraphClient("fake").profile() == {"id": "fake"}
    sleep.assert_awaited_once_with(2.0)
    with pytest.raises(httpx.HTTPStatusError):
        await MicrosoftGraphClient("fake").profile()
    assert statuses == []
