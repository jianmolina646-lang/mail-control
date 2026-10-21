from __future__ import annotations

import asyncio
import base64
import imaplib
from datetime import UTC, datetime
from email import policy
from email.message import EmailMessage, Message
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from typing import Any, cast


class GmailImapError(ValueError):
    pass


def _encoded(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _part(message: Message) -> dict[str, Any]:
    headers = [{"name": key, "value": str(value)} for key, value in message.items()]
    result: dict[str, Any] = {
        "mimeType": message.get_content_type(), "filename": message.get_filename() or "",
        "headers": headers, "body": {},
    }
    if message.is_multipart():
        result["parts"] = [_part(child) for child in cast(EmailMessage, message).iter_parts()]
    else:
        content = cast(bytes, message.get_payload(decode=True) or b"")
        result["body"] = {"size": len(content), "data": _encoded(content)}
    return result


def _plain_text(message: Message) -> str:
    for part in message.walk():
        if part.get_content_type() == "text/plain" and not part.get_filename():
            raw = cast(bytes, part.get_payload(decode=True) or b"")
            return raw.decode(part.get_content_charset() or "utf-8", errors="replace")
    return ""


def _gmail_payload(
    uid: int, raw: bytes, flags: set[str], internal_date: datetime,
) -> dict[str, Any]:
    message = BytesParser(policy=policy.default).parsebytes(raw)
    labels = ["INBOX"]
    if "\\Seen" not in flags:
        labels.append("UNREAD")
    if "\\Flagged" in flags:
        labels.append("STARRED")
    message_id = str(message.get("Message-ID") or f"imap-{uid}").strip("<>")
    received = message.get("Date")
    try:
        received_at = parsedate_to_datetime(str(received)) if received else internal_date
    except (TypeError, ValueError):
        received_at = internal_date
    if received_at.tzinfo is None:
        received_at = received_at.replace(tzinfo=UTC)
    return {
        "id": f"imap-{uid}", "threadId": message_id, "historyId": str(uid),
        "internalDate": str(int(received_at.timestamp() * 1000)),
        "labelIds": labels, "snippet": " ".join(_plain_text(message).split())[:300],
        "sizeEstimate": len(raw), "payload": _part(message),
    }


class GmailImapClient:
    def __init__(self, email: str, app_password: str) -> None:
        self.email = email.strip().casefold()
        self.password = app_password.replace(" ", "").strip()

    async def verify(self) -> None:
        await asyncio.to_thread(self._verify)

    def _verify(self) -> None:
        try:
            connection = imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=30)
            connection.login(self.email, self.password)
            connection.logout()
        except (imaplib.IMAP4.error, OSError) as error:
            raise GmailImapError(
                "Google rechazó el correo o la contraseña de aplicación."
            ) from error

    async def messages(
        self, after_uid: int | None = None,
    ) -> tuple[list[dict[str, Any]], int | None]:
        return await asyncio.to_thread(self._messages, after_uid)

    def _messages(self, after_uid: int | None) -> tuple[list[dict[str, Any]], int | None]:
        try:
            connection = imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=45)
            connection.login(self.email, self.password)
            status, _ = connection.select("INBOX", readonly=True)
            if status != "OK":
                raise GmailImapError("No se pudo abrir la bandeja de Gmail.")
            # imaplib accepts None for an omitted SEARCH charset; stubs only allow str.
            status, data = cast(Any, connection).uid("search", None, "ALL")
            if status != "OK":
                raise GmailImapError("No se pudo consultar Gmail.")
            uids = [int(value) for value in (data[0] or b"").split()]
            cursor = max(uids, default=after_uid)
            pending = [uid for uid in uids if after_uid is None or uid > after_uid]
            if after_uid is None:
                pending = pending[-2000:]
            result: list[dict[str, Any]] = []
            for uid in pending:
                status, rows = connection.uid("fetch", str(uid), "(RFC822 FLAGS INTERNALDATE)")
                if status != "OK" or not rows or not isinstance(rows[0], tuple):
                    continue
                metadata, raw = rows[0]
                flags = {item.decode(errors="ignore") for item in imaplib.ParseFlags(metadata)}
                parsed = imaplib.Internaldate2tuple(metadata)
                internal = (
                    datetime.fromtimestamp(__import__("time").mktime(parsed), UTC)
                    if parsed else datetime.now(UTC)
                )
                result.append(_gmail_payload(uid, raw, flags, internal))
            connection.logout()
            return result, cursor
        except GmailImapError:
            raise
        except (imaplib.IMAP4.error, OSError) as error:
            raise GmailImapError("No se pudo conectar con Gmail mediante IMAP.") from error
