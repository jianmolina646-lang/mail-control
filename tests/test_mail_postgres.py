"""Real PostgreSQL regressions, only on an explicitly supplied disposable DB."""

import os
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from mail_control.api.dashboard import _message_account, update_message_state
from mail_control.infrastructure.database.session import Database  # noqa: F401
from mail_control.infrastructure.database.tenant import set_tenant_context
from mail_control.modules.dashboard.filters import MessageFilters
from mail_control.modules.dashboard.repository import DashboardRepository
from mail_control.modules.dashboard.schemas import MessageStateUpdate
from mail_control.modules.identity.models import RoleName, Tenant, TenantStatus, User
from mail_control.modules.mail.models import AccountStatus, EmailMessage, MailAccount, MailProvider
from mail_control.modules.mail.repository import MailRepository

TEST_DATABASE_URL = os.environ.get("MAIL_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="requires isolated PostgreSQL")


@pytest.fixture
async def dataset():
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    async with engine.connect() as connection:
        outer = await connection.begin()
        session = AsyncSession(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        tenants = [
            Tenant(
                id=uuid4(),
                name="Synthetic audit",
                slug=f"audit-{uuid4()}",
                status=TenantStatus.ACTIVE,
            )
            for _ in range(2)
        ]
        session.add_all(tenants)
        await session.flush()
        users = [
            User(
                id=uuid4(),
                tenant_id=t.id,
                email="test@example.invalid",
                email_normalized="test@example.invalid",
                display_name="Test",
                password_hash="not-a-password",
                role=RoleName.OWNER,
                is_active=True,
            )
            for t in tenants
        ]
        session.add_all(users)
        await session.flush()
        accounts = []
        for index, (owner, provider, email) in enumerate(
            [
                (0, MailProvider.GMAIL, "one@gmail.com"),
                (0, MailProvider.GMAIL, "two@gmail.com"),
                (0, MailProvider.MICROSOFT, "three@hotmail.com"),
                (0, MailProvider.MICROSOFT, "four@outlook.com"),
                (1, MailProvider.GMAIL, "private@gmail.com"),
            ]
        ):
            accounts.append(
                MailAccount(
                    id=uuid4(),
                    tenant_id=tenants[owner].id,
                    connected_by_user_id=users[owner].id,
                    provider=provider,
                    email=email,
                    provider_account_id=f"synthetic-{index}",
                    encrypted_refresh_token="never-used",
                    status=AccountStatus.CONNECTED,
                )
            )
        session.add_all(accounts)
        await session.flush()
        messages = []
        for index, account_index in enumerate([0, 0, 1, 2, 3, 4]):
            account = accounts[account_index]
            messages.append(
                EmailMessage(
                    id=uuid4(),
                    tenant_id=account.tenant_id,
                    mail_account_id=account.id,
                    provider_message_id=f"synthetic-message-{index}",
                    thread_id="same-thread-id",
                    sender="service@example.invalid",
                    subject="Netflix synthetic message",
                    snippet="Contenido ficticio",
                    received_at=datetime.now(UTC),
                    payload={"id": f"synthetic-message-{index}", "payload": {"headers": []}},
                    is_read=index == 0,
                    is_starred=False,
                    mailbox="inbox",
                )
            )
        session.add_all(messages)
        await session.flush()
        try:
            yield SimpleNamespace(
                session=session,
                connection=connection,
                tenants=tenants,
                users=users,
                accounts=accounts,
                messages=messages,
            )
        finally:
            await session.close()
            await outer.rollback()
    await engine.dispose()


async def page(data, **overrides):
    values = dict(
        search=None,
        account_id=None,
        provider=None,
        category=None,
        risk_level=None,
        mailbox="inbox",
        cursor=None,
        limit=50,
    )
    values.update(overrides)
    return await DashboardRepository(data.session, data.tenants[0].id).messages(**values)


async def test_pg_account_isolation_counts_and_stable_pagination(dataset):
    items = await DashboardRepository(dataset.session, dataset.tenants[0].id).accounts()
    assert len(items) == 4
    first = await page(dataset, account_id=dataset.accounts[0].id, limit=1)
    second = await page(
        dataset, account_id=dataset.accounts[0].id, limit=1, cursor=first.next_cursor
    )
    assert first.total_count == 2
    assert first.unread_count == 1
    assert len(first.items) == len(second.items) == 1
    assert first.items[0].id != second.items[0].id
    assert first.items[0].account_id == second.items[0].account_id == dataset.accounts[0].id
    assert not (await page(dataset, account_id=dataset.accounts[-1].id)).items


async def test_pg_operator_queries_do_not_search_operator_words(dataset):
    result = await page(dataset, search="proveedor:gmail estado:no-leido")
    assert len(result.items) == 2
    assert {item.provider for item in result.items} == {MailProvider.GMAIL}
    assert not any(item.is_read for item in result.items)


async def test_pg_hotmail_filter_excludes_outlook_and_gmail(dataset):
    result = await page(dataset, search="proveedor:hotmail")
    assert len(result.items) == 1
    assert result.items[0].account_id == dataset.accounts[2].id


async def test_pg_no_attachment_filter_includes_messages_without_provider_flag(dataset):
    result = await page(dataset, filters=MessageFilters(has_attachments=False))
    assert len(result.items) == 5


async def test_pg_foreign_message_content_is_not_loaded(dataset):
    with pytest.raises(HTTPException) as error:
        await _message_account(dataset.messages[-1].id, dataset.tenants[0].id, dataset.session)
    assert error.value.status_code == 404


async def test_pg_local_overrides_survive_provider_updates(dataset):
    item = dataset.messages[1]
    principal = SimpleNamespace(claims=SimpleNamespace(tenant_id=dataset.tenants[0].id))
    await update_message_state(
        item.id, MessageStateUpdate(is_read=True, mailbox="archive"), principal, dataset.session
    )
    await MailRepository(dataset.session).upsert_message(
        {
            "tenant_id": item.tenant_id,
            "mail_account_id": item.mail_account_id,
            "provider_message_id": item.provider_message_id,
            "payload": {},
            "provider_is_read": False,
            "provider_is_starred": False,
            "provider_mailbox": "inbox",
            "is_read": False,
            "is_starred": False,
            "mailbox": "inbox",
            "label_ids": [],
        }
    )
    await dataset.session.refresh(item)
    assert item.is_read is True and item.local_is_read is True
    assert item.mailbox == item.local_mailbox == "archive"
    assert item.provider_mailbox == "inbox"


async def test_pg_rls_blocks_cross_tenant_even_without_query_filter(dataset):
    # Identifier is generated by this test, never supplied by a user.
    role = "mail_test_" + uuid4().hex
    await dataset.session.execute(text(f'CREATE ROLE "{role}" NOSUPERUSER NOBYPASSRLS'))
    await dataset.session.execute(text(f'GRANT USAGE ON SCHEMA public TO "{role}"'))
    await dataset.session.execute(text(f'GRANT SELECT ON ALL TABLES IN SCHEMA public TO "{role}"'))
    await dataset.session.execute(text(f'SET LOCAL ROLE "{role}"'))
    await set_tenant_context(dataset.session, dataset.tenants[0].id)
    ids = (await dataset.session.scalars(select(EmailMessage.id))).all()
    assert len(ids) == 5
    assert dataset.messages[-1].id not in ids
