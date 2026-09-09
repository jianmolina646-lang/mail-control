from __future__ import annotations

import base64
import copy
import hashlib
from dataclasses import dataclass
from typing import Any, cast

import httpx
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from mail_control.infrastructure.resources import Resources
from mail_control.modules.dashboard.schemas import AttachmentItem, Mailbox, MessageContent
from mail_control.modules.mail.content import (
    MAX_BODY_BYTES,
    message_body,
    message_html,
    message_recipients,
    part_headers,
)
from mail_control.modules.mail.gmail import GmailClient, GmailError
from mail_control.modules.mail.microsoft import MicrosoftError, MicrosoftGraphClient
from mail_control.modules.mail.models import EmailMessage, MailAccount, MailProvider
from mail_control.modules.mail.token_manager import provider_client
from mail_control.settings import Settings

MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024
MAX_ATTACHMENTS = 200
INLINE_IMAGE_TYPES = frozenset({"image/png", "image/jpeg", "image/gif", "image/webp"})
CONTENT_ERRORS = (ValueError, GmailError, MicrosoftError, httpx.HTTPError, OSError,
                  RuntimeError, RedisError)


class ContentLimitError(ValueError):
    pass


class AttachmentNotFound(ValueError):
    pass


def decode_attachment(value: str, limit: int = MAX_ATTACHMENT_BYTES) -> bytes:
    if len(value) > ((limit + 2) // 3) * 4 + 8:
        raise ContentLimitError("attachment exceeds the download limit")
    decoded = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
    if len(decoded) > limit:
        raise ContentLimitError("attachment exceeds the download limit")
    return decoded


def _parts(payload: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    pending = [(payload, 0)]
    while pending:
        part, depth = pending.pop()
        if depth > 30 or len(result) >= 2000:
            raise ContentLimitError("message has too many MIME parts")
        result.append(part)
        pending.extend((child, depth + 1) for child in reversed(part.get("parts", []))
                       if isinstance(child, dict))
    return result


@dataclass
class AttachmentRef:
    item: AttachmentItem
    provider_id: str | None
    data: str | None = None
    graph: bool = False


def _attachment_item(message: EmailMessage, key: str, *, filename: str,
                     content_type: str, size: int, content_id: str | None,
                     is_inline: bool) -> AttachmentItem:
    url = f"/v1/mail/messages/{message.id}/attachments/{key}"
    return AttachmentItem(id=key, filename=filename or "attachment",
                          content_type=content_type or "application/octet-stream",
                          size=max(size, 0), content_id=content_id, is_inline=is_inline,
                          download_url=url,
                          inline_url=f"{url}?inline=true"
                          if is_inline and content_type in INLINE_IMAGE_TYPES else None)


def gmail_attachments(message: EmailMessage, payload: dict[str, Any]) -> list[AttachmentRef]:
    refs = []
    for index, part in enumerate(_parts(payload.get("payload", {}))):
        headers = part_headers(part)
        filename = str(part.get("filename") or "")
        content_id = headers.get("content-id", "").strip().strip("<>") or None
        disposition = headers.get("content-disposition", "").casefold()
        if not filename and "attachment" not in disposition and not content_id:
            continue
        body = part.get("body", {})
        key = f"gmail-{index}"
        item = _attachment_item(message, key, filename=filename,
                                content_type=str(part.get("mimeType") or ""),
                                size=int(body.get("size") or 0), content_id=content_id,
                                is_inline=bool(content_id) and "attachment" not in disposition)
        refs.append(AttachmentRef(item, body.get("attachmentId"), body.get("data")))
        if len(refs) > MAX_ATTACHMENTS:
            raise ContentLimitError("message has too many attachments")
    return refs


def detected_image_type(content: bytes) -> str | None:
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "image/webp"
    return None


class MessageContentService:
    """Read content only after callers resolve both message and account in their tenant."""

    def __init__(self, session: AsyncSession, resources: Resources, settings: Settings) -> None:
        self.session = session
        self.resources = resources
        self.settings = settings
        self.clients: dict[str, GmailClient | MicrosoftGraphClient] = {}

    async def _client(self, account: MailAccount) -> GmailClient | MicrosoftGraphClient:
        key = str(account.id)
        if key not in self.clients:
            self.clients[key] = await provider_client(
                account, self.session, self.resources, self.settings
            )
        return self.clients[key]

    async def _payload(self, message: EmailMessage, account: MailAccount) -> dict[str, Any]:
        payload = cast(dict[str, Any], copy.deepcopy(message.payload))
        if account.provider == MailProvider.GMAIL:
            total = 0
            for part in _parts(payload.get("payload", {})):
                headers = part_headers(part)
                if (part.get("mimeType") not in {"text/plain", "text/html"}
                        or part.get("filename")
                        or "attachment" in headers.get("content-disposition", "").casefold()):
                    continue
                body = part.get("body", {})
                if body.get("attachmentId") and not body.get("data"):
                    if int(body.get("size") or 0) > MAX_BODY_BYTES - total:
                        raise ContentLimitError("message body exceeds the 2 MiB limit")
                    client = cast(GmailClient, await self._client(account))
                    data = await client.get_attachment(message.provider_message_id,
                                                       str(body["attachmentId"]))
                    body["data"] = data.get("data", "")
                if isinstance(body.get("data"), str):
                    total += len(decode_attachment(body["data"], MAX_BODY_BYTES - total))
                    if total > MAX_BODY_BYTES:
                        raise ContentLimitError("message body exceeds the 2 MiB limit")
        else:
            content = payload.get("body", {}).get("content", "")
            if len(str(content).encode("utf-8")) > MAX_BODY_BYTES:
                raise ContentLimitError("message body exceeds the 2 MiB limit")
        return payload

    async def attachments(self, message: EmailMessage, account: MailAccount,
                          payload: dict[str, Any] | None = None) -> list[AttachmentRef]:
        payload = payload or message.payload
        if account.provider == MailProvider.GMAIL:
            return gmail_attachments(message, payload)
        # Graph excludes inline-only images from hasAttachments.
        if not payload.get("hasAttachments") and "cid:" not in (message_html(
                payload, account.provider) or "").casefold():
            return []
        client = cast(MicrosoftGraphClient, await self._client(account))
        refs: list[AttachmentRef] = []
        page_url: str | None = None
        seen: set[str] = set()
        for _ in range(20):
            page = await client.attachments(message.provider_message_id, page_url=page_url)
            for item in page.get("value", []):
                if item.get("@odata.type") not in {None, "#microsoft.graph.fileAttachment"}:
                    continue
                provider_id = str(item["id"])
                key = "graph-" + hashlib.sha256(provider_id.encode()).hexdigest()
                metadata = _attachment_item(
                    message, key, filename=str(item.get("name") or ""),
                    content_type=str(item.get("contentType") or ""),
                    size=int(item.get("size") or 0),
                    content_id=str(item["contentId"]).strip("<>")
                    if item.get("contentId") else None, is_inline=bool(item.get("isInline")),
                )
                refs.append(AttachmentRef(metadata, provider_id, graph=True))
                if len(refs) > MAX_ATTACHMENTS:
                    raise ContentLimitError("message has too many attachments")
            page_url = page.get("@odata.nextLink")
            if not page_url:
                return refs
            if page_url in seen:
                raise ContentLimitError("attachment pagination did not advance")
            seen.add(page_url)
        raise ContentLimitError("message has too many attachment pages")

    async def content(self, message: EmailMessage, account: MailAccount) -> MessageContent:
        warning = None
        attachments_error = None
        try:
            payload = await self._payload(message, account)
        except CONTENT_ERRORS:
            payload = cast(dict[str, Any], message.payload)
            warning = "No se pudo cargar el cuerpo completo. Se muestra el contenido guardado."
        try:
            body = message_body(payload, account.provider, message.snippet)
            body_html = message_html(payload, account.provider)
            if any(len(value.encode("utf-8")) > MAX_BODY_BYTES for value in (
                    body or "", body_html or "")):
                raise ContentLimitError("message body exceeds the 2 MiB limit")
        except CONTENT_ERRORS:
            body, body_html = message.snippet, None
            warning = "No se pudo cargar el cuerpo completo. Se muestra solo la vista previa."
        try:
            refs = await self.attachments(message, account, payload)
        except CONTENT_ERRORS:
            refs = []
            attachments_error = "No se pudieron consultar los adjuntos. Vuelve a intentarlo."
        to, cc = message_recipients(payload, account.provider)
        return MessageContent(
            id=message.id, account_id=account.id, provider=account.provider,
            account_email=account.email, sender=message.sender, to=to, cc=cc,
            subject=message.subject, received_at=message.received_at,
            is_read=message.is_read, is_starred=message.is_starred,
            mailbox=cast(Mailbox, message.mailbox), thread_id=message.thread_id,
            body=body, body_html=body_html,
            attachments=[ref.item for ref in refs],
            content_warning=warning, attachments_error=attachments_error,
        )

    async def html(self, message: EmailMessage, account: MailAccount) -> str | None:
        return message_html(await self._payload(message, account), account.provider)

    async def download(self, message: EmailMessage, account: MailAccount,
                       attachment_id: str) -> tuple[bytes, AttachmentItem]:
        refs = await self.attachments(message, account)
        ref = next((item for item in refs if item.item.id == attachment_id), None)
        if ref is None:
            raise AttachmentNotFound("attachment not found")
        if ref.item.size > MAX_ATTACHMENT_BYTES:
            raise ContentLimitError("attachment exceeds the 20 MiB download limit")
        data = ref.data
        if data is None and ref.provider_id:
            client = await self._client(account)
            response = await client.attachment(message.provider_message_id, ref.provider_id)
            data = response.get("contentBytes" if ref.graph else "data")
        if not isinstance(data, str):
            raise AttachmentNotFound("attachment content unavailable")
        return decode_attachment(data), ref.item
