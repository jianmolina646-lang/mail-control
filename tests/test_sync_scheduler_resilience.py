from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import aio_pika
import pytest

from mail_control.modules.mail.models import AccountStatus, MailProvider
from mail_control.sync_scheduler import GMAIL_COOLDOWN_PREFIX, enqueue_due_accounts


def mock_resources(rows, redis_values=None):
    """All dependencies are in-memory mocks; no database or broker is opened."""
    values = redis_values if redis_values is not None else {}
    session = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(all=lambda: rows)))
    session_context = MagicMock()
    session_context.__aenter__ = AsyncMock(return_value=session)
    session_context.__aexit__ = AsyncMock(return_value=False)

    async def mget(keys):
        return [values.get(key) for key in keys]

    channel = SimpleNamespace(
        default_exchange=SimpleNamespace(publish=AsyncMock()),
        close=AsyncMock(),
    )
    resources = SimpleNamespace(
        system_database=SimpleNamespace(session_factory=MagicMock(return_value=session_context)),
        redis=SimpleNamespace(mget=AsyncMock(side_effect=mget)),
        rabbitmq=SimpleNamespace(channel=AsyncMock(return_value=channel)),
    )
    return resources, session, channel


@pytest.mark.asyncio
async def test_query_recovers_syncing_but_excludes_disconnected_and_reauthorization():
    resources, session, _channel = mock_resources([])
    before = datetime.now(UTC) - timedelta(seconds=300)

    assert await enqueue_due_accounts(resources, 300) == 0

    statement = session.execute.call_args.args[0]
    compiled = statement.compile()
    assert compiled.params["status_1"] == [
        AccountStatus.CONNECTED, AccountStatus.ERROR, AccountStatus.SYNCING,
    ]
    assert AccountStatus.REAUTH_REQUIRED not in compiled.params["status_1"]
    assert AccountStatus.DISCONNECTED not in compiled.params["status_1"]
    assert "mail_accounts.last_synced_at IS NULL" in str(compiled)
    assert before <= compiled.params["last_synced_at_1"] <= datetime.now(UTC)
    resources.redis.mget.assert_not_awaited()
    resources.rabbitmq.channel.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", [MailProvider.GMAIL, MailProvider.MICROSOFT])
async def test_orphaned_sync_is_queued_without_resetting_account_or_credentials(provider):
    account_id, tenant_id = uuid4(), uuid4()
    resources, _session, channel = mock_resources([(account_id, tenant_id, provider)])

    assert await enqueue_due_accounts(resources, 300) == 1

    call = channel.default_exchange.publish.call_args
    message = call.args[0]
    assert json.loads(message.body) == {
        "tenant_id": str(tenant_id), "mail_account_id": str(account_id),
    }
    assert message.delivery_mode == aio_pika.DeliveryMode.PERSISTENT
    assert call.kwargs["routing_key"] == f"mail.sync.{provider.value}"
    channel.close.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", [MailProvider.GMAIL, MailProvider.MICROSOFT])
async def test_active_import_lease_prevents_scheduling(provider):
    account_id, tenant_id = uuid4(), uuid4()
    resources, _session, channel = mock_resources(
        [(account_id, tenant_id, provider)],
        {f"sync:{provider.value}:{account_id}": b"current-worker-token"},
    )

    assert await enqueue_due_accounts(resources, 300) == 0

    channel.default_exchange.publish.assert_not_awaited()
    resources.rabbitmq.channel.assert_not_awaited()


@pytest.mark.asyncio
async def test_crashed_workers_expired_lease_allows_recovery_on_next_scheduler_pass():
    account_id, tenant_id = uuid4(), uuid4()
    lock_key = f"sync:gmail:{account_id}"
    redis_values = {lock_key: b"dead-worker-token"}
    resources, _session, channel = mock_resources(
        [(account_id, tenant_id, MailProvider.GMAIL)], redis_values,
    )

    assert await enqueue_due_accounts(resources, 300) == 0
    channel.default_exchange.publish.assert_not_awaited()
    # Simulate expiry in the fake Redis. The scheduler never deletes a lease.
    redis_values.clear()
    assert await enqueue_due_accounts(resources, 300) == 1
    channel.default_exchange.publish.assert_awaited_once()


@pytest.mark.asyncio
async def test_gmail_cooldown_still_blocks_recovery_after_import_lease_expires():
    account_id, tenant_id = uuid4(), uuid4()
    redis_values = {f"{GMAIL_COOLDOWN_PREFIX}{account_id}": b"1"}
    resources, _session, channel = mock_resources(
        [(account_id, tenant_id, MailProvider.GMAIL)], redis_values,
    )

    assert await enqueue_due_accounts(resources, 300) == 0
    channel.default_exchange.publish.assert_not_awaited()
    redis_values.clear()
    assert await enqueue_due_accounts(resources, 300) == 1
    channel.default_exchange.publish.assert_awaited_once()


@pytest.mark.asyncio
async def test_overlapping_lease_and_cooldown_are_not_double_counted():
    blocked, ready_gmail, ready_microsoft, tenant_id = uuid4(), uuid4(), uuid4(), uuid4()
    resources, _session, channel = mock_resources(
        [
            (blocked, tenant_id, MailProvider.GMAIL),
            (ready_gmail, tenant_id, MailProvider.GMAIL),
            (ready_microsoft, tenant_id, MailProvider.MICROSOFT),
        ],
        {
            f"sync:gmail:{blocked}": b"worker-token",
            f"{GMAIL_COOLDOWN_PREFIX}{blocked}": b"1",
        },
    )

    assert await enqueue_due_accounts(resources, 300) == 2

    published = {
        json.loads(call.args[0].body)["mail_account_id"]
        for call in channel.default_exchange.publish.call_args_list
    }
    assert published == {str(ready_gmail), str(ready_microsoft)}
    assert channel.default_exchange.publish.await_count == 2


@pytest.mark.asyncio
async def test_cannot_read_lease_state_does_not_publish_unverified_work():
    resources, _session, channel = mock_resources([(uuid4(), uuid4(), MailProvider.GMAIL)])
    resources.redis.mget.side_effect = ConnectionError("fake Redis unavailable")

    with pytest.raises(ConnectionError, match="fake Redis unavailable"):
        await enqueue_due_accounts(resources, 300)

    channel.default_exchange.publish.assert_not_awaited()
    resources.rabbitmq.channel.assert_not_awaited()


@pytest.mark.asyncio
async def test_failed_publish_closes_the_channel_and_leaves_recovery_for_next_pass():
    resources, _session, channel = mock_resources([(uuid4(), uuid4(), MailProvider.GMAIL)])
    channel.default_exchange.publish.side_effect = ConnectionError("fake broker unavailable")

    with pytest.raises(ConnectionError, match="fake broker unavailable"):
        await enqueue_due_accounts(resources, 300)

    channel.close.assert_awaited_once()
