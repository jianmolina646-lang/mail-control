from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql

from mail_control.api import dashboard
from mail_control.modules.dashboard.schemas import AttachmentItem
from mail_control.modules.mail.content import message_recipients
from mail_control.modules.mail.content_service import (
    AttachmentNotFound,
    ContentLimitError,
    MessageContentService,
    decode_attachment,
)
from mail_control.modules.mail.models import EmailMessage, MailAccount, MailProvider


def encoded(value: bytes | str) -> str:
    return base64.urlsafe_b64encode(value.encode() if isinstance(value, str) else value).decode()


def fixtures(provider=MailProvider.GMAIL, payload=None):
    account = MailAccount(id=uuid4(), tenant_id=uuid4(), provider=provider,
                          email="account@example.invalid")
    message = EmailMessage(
        id=uuid4(), tenant_id=account.tenant_id, mail_account_id=account.id,
        provider_message_id="provider-message", thread_id="same-thread",
        sender="sender@test.invalid",
        subject="Synthetic mail", snippet="preview", payload=payload or {},
        received_at=datetime(2026, 9, 7, tzinfo=UTC), is_read=False, is_starred=True,
        mailbox="inbox",
    )
    service = MessageContentService(Mock(), Mock(), Mock())
    return message, account, service


async def test_gmail_body_parts_fetched_on_demand_with_headers_and_cid():
    payload = {"payload": {"mimeType": "multipart/mixed", "headers": [
        {"name": "To", "value": "alias@example.invalid, second@example.invalid"},
        {"name": "Cc", "value": "copy@example.invalid"},
    ], "parts": [
        {"mimeType": "text/html", "body": {"attachmentId": "body-id", "size": 50}},
        {"mimeType": "image/png", "filename": "logo.png", "headers": [
            {"name": "Content-ID", "value": "<logo>"},
        ], "body": {"attachmentId": "image-id", "size": 20}},
    ]}}
    message, account, service = fixtures(payload=payload)
    client = AsyncMock()
    client.get_attachment.return_value = {"data": encoded('<p>Full body<img src="cid:logo"></p>')}
    service.clients[str(account.id)] = client
    result = await service.content(message, account)
    assert result.body_html == '<p>Full body<img src="cid:logo"></p>'
    assert result.to == ["alias@example.invalid", "second@example.invalid"]
    assert result.cc == ["copy@example.invalid"]
    assert result.account_email == "account@example.invalid"
    assert result.attachments[0].content_id == "logo"
    assert result.attachments[0].inline_url.endswith("?inline=true")
    assert result.content_warning is None
    client.get_attachment.assert_awaited_once_with("provider-message", "body-id")
    client.attachment.assert_not_awaited()
    assert "data" not in payload["payload"]["parts"][0]["body"]


async def test_external_body_failure_keeps_preview_with_explicit_warning():
    payload = {"payload": {"mimeType": "text/plain", "body": {"attachmentId": "body-id"}}}
    message, account, service = fixtures(payload=payload)
    client = AsyncMock()
    client.get_attachment.side_effect = httpx.ConnectError("synthetic provider unavailable")
    service.clients[str(account.id)] = client
    result = await service.content(message, account)
    assert result.body == "preview"
    assert result.content_warning
    assert "synthetic provider" not in result.content_warning


@pytest.mark.parametrize("error", [httpx.ConnectError("private detail"), RuntimeError("busy")])
async def test_graph_auxiliary_failure_preserves_full_body(error):
    message, account, service = fixtures(MailProvider.MICROSOFT, {
        "body": {"contentType": "html", "content": "<p>Saved full body</p>"},
        "hasAttachments": True,
    })
    client = AsyncMock()
    client.attachments.side_effect = error
    service.clients[str(account.id)] = client
    result = await service.content(message, account)
    assert result.body_html == "<p>Saved full body</p>"
    assert result.attachments_error
    assert result.content_warning is None
    assert result.attachments == []


async def test_graph_attachment_pages_and_inline_only_image():
    message, account, service = fixtures(MailProvider.MICROSOFT, {
        "body": {"contentType": "html", "content": '<img src="cid:graph-logo">'},
        "hasAttachments": False,
    })
    client = AsyncMock()
    client.attachments.side_effect = [
        {"value": [{"id": "inline-id", "name": "logo.png", "size": 12,
                    "contentType": "image/png", "isInline": True, "contentId": "graph-logo"}],
         "@odata.nextLink": "https://graph.microsoft.com/v1.0/next"},
        {"value": [{"id": "document-id", "name": "document.pdf", "size": 44,
                    "contentType": "application/pdf", "isInline": False}]},
    ]
    service.clients[str(account.id)] = client
    result = await service.content(message, account)
    assert len(result.attachments) == 2
    assert result.attachments[0].content_id == "graph-logo"
    assert result.attachments[0].inline_url
    assert result.attachments[1].inline_url is None
    assert client.attachments.await_count == 2
    client.attachment.assert_not_awaited()


async def test_download_rejects_unknown_id_without_fetching_content():
    message, account, service = fixtures(payload={"payload": {"mimeType": "text/plain"}})
    client = AsyncMock()
    service.clients[str(account.id)] = client
    with pytest.raises(AttachmentNotFound):
        await service.download(message, account, "other-message-attachment")
    client.attachment.assert_not_awaited()


async def test_download_fetches_only_listed_gmail_attachment():
    payload = {"payload": {"mimeType": "application/pdf", "filename": "a.pdf",
                           "body": {"size": 8, "attachmentId": "scoped-provider-id"}}}
    message, account, service = fixtures(payload=payload)
    client = AsyncMock()
    client.attachment.return_value = {"data": encoded("pdf-data")}
    service.clients[str(account.id)] = client
    content, metadata = await service.download(message, account, "gmail-0")
    assert content == b"pdf-data"
    assert metadata.filename == "a.pdf"
    client.attachment.assert_awaited_once_with("provider-message", "scoped-provider-id")


def test_attachment_limit_checks_actual_bytes_even_if_size_metadata_is_false():
    with pytest.raises(ContentLimitError):
        decode_attachment(encoded("more than 3 bytes"), limit=3)
    with pytest.raises(ValueError):
        decode_attachment("not valid base64!!!")


def test_graph_headers_use_to_and_cc_separately():
    to, cc = message_recipients({
        "toRecipients": [{"emailAddress": {"address": "alias@test.invalid"}}],
        "ccRecipients": [{"emailAddress": {"address": "copy@test.invalid"}}],
    }, MailProvider.MICROSOFT)
    assert to == ["alias@test.invalid"]
    assert cc == ["copy@test.invalid"]


@pytest.mark.parametrize("endpoint", [dashboard.message_content, dashboard.message_thread,
                                     dashboard.message_attachment])
async def test_content_endpoints_reject_foreign_scope_before_any_provider_access(endpoint):
    tenant_id, account_id, message_id = uuid4(), uuid4(), uuid4()
    result = Mock()
    result.one_or_none.return_value = None
    session = AsyncMock()
    session.execute.return_value = result
    principal = SimpleNamespace(claims=SimpleNamespace(tenant_id=tenant_id))
    kwargs = {"message_id": message_id, "request": Mock(), "principal": principal,
              "session": session, "account_id": account_id}
    if endpoint is dashboard.message_attachment:
        kwargs["attachment_id"] = "gmail-1"
    with pytest.raises(HTTPException) as error:
        await endpoint(**kwargs)
    assert error.value.status_code == 404
    statement = session.execute.await_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect(),
                                compile_kwargs={"literal_binds": True}))
    assert "email_messages.tenant_id =" in sql and "mail_accounts.tenant_id =" in sql
    assert str(tenant_id) in sql and str(account_id) in sql


async def test_thread_pages_complete_bodies_with_account_scope(monkeypatch):
    first, account, service = fixtures(payload={"payload": {"mimeType": "text/plain",
                                                            "body": {"data": encoded("full 1")}}})
    messages = [first]
    for index in (2, 3):
        message, _, _ = fixtures(payload={"payload": {"mimeType": "text/plain",
                                                     "body": {"data": encoded(f"full {index}")}}})
        message.mail_account_id = account.id
        message.tenant_id = account.tenant_id
        message.received_at = first.received_at + timedelta(hours=index)
        messages.append(message)
    monkeypatch.setattr(dashboard, "_message_account", AsyncMock(return_value=(first, account)))
    monkeypatch.setattr(dashboard, "_content_service", lambda *_: service)
    session = AsyncMock()
    session.scalar.return_value = 3
    session.scalars.return_value = Mock(all=Mock(return_value=messages))
    page = await dashboard.message_thread(first.id, Mock(), SimpleNamespace(
        claims=SimpleNamespace(tenant_id=account.tenant_id)), session, limit=2)
    assert [item.body for item in page.items] == ["full 1", "full 2"]
    assert page.total_count == 3
    assert page.next_cursor
    sql = str(session.scalars.await_args.args[0].compile(
        dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert str(account.id) in sql and str(account.tenant_id) in sql
    assert "mailbox =" not in sql
    assert " ASC" in sql


@pytest.mark.parametrize("inline,content_type,data,expected", [
    (False, "text/html", b"<html>active</html>", 200),
    (True, "text/html", b"<html>active</html>", 415),
    (True, "image/png", b"<html>disguised</html>", 415),
    (True, "image/png", b"\x89PNG\r\n\x1a\nimage", 200),
])
async def test_download_disposition_prevents_active_html(monkeypatch, inline, content_type,
                                                       data, expected):
    message, account, _ = fixtures()
    metadata = AttachmentItem(id="id", filename="untrusted\r\nname.html", content_type=content_type,
                              size=len(data), is_inline=True, download_url="/attachment",
                              inline_url="/attachment?inline=true" if content_type == "image/png"
                              else None)
    service = Mock(download=AsyncMock(return_value=(data, metadata)))
    monkeypatch.setattr(dashboard, "_message_account", AsyncMock(return_value=(message, account)))
    monkeypatch.setattr(dashboard, "_content_service", lambda *_: service)
    principal = SimpleNamespace(claims=SimpleNamespace(tenant_id=account.tenant_id))
    if expected == 415:
        with pytest.raises(HTTPException) as error:
            await dashboard.message_attachment(message.id, "id", Mock(), principal, Mock(),
                                                 inline=inline)
        assert error.value.status_code == 415
    else:
        response = await dashboard.message_attachment(message.id, "id", Mock(), principal, Mock(),
                                                       inline=inline)
        assert response.headers["x-content-type-options"] == "nosniff"
        assert "\r" not in response.headers["content-disposition"]
        if not inline:
            assert response.headers["content-disposition"].startswith("attachment;")
            assert response.media_type == "application/octet-stream"
