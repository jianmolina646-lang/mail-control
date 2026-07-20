"""Lectura IMAP eficiente para VPS de baja memoria.

Estrategia anti-OOM:
- Una conexión IMAP por cuenta, abierta y cerrada de inmediato (context manager).
- Solo se traen los últimos IMAP_FETCH_LIMIT correos por cuenta.
- Se descarga el cuerpo acotado y se libera; no se mantienen sockets abiertos.
"""

from __future__ import annotations

import email
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime
from datetime import datetime, timezone

from bs4 import BeautifulSoup
from imapclient import IMAPClient

from ..core.config import settings


def _decode(value) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return str(value)


def _html_to_text(html: str) -> str:
    try:
        return BeautifulSoup(html, "lxml").get_text(" ", strip=True)
    except Exception:
        return ""


def _extract_bodies(msg: email.message.Message) -> tuple[str, str]:
    """Devuelve (texto_plano, html). Acota el tamaño para no reventar RAM."""
    text_parts: list[str] = []
    html_parts: list[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition") or "")
            if "attachment" in disp:
                continue
            if ctype == "text/plain":
                text_parts.append(_payload(part))
            elif ctype == "text/html":
                html_parts.append(_payload(part))
    else:
        if msg.get_content_type() == "text/html":
            html_parts.append(_payload(msg))
        else:
            text_parts.append(_payload(msg))

    html = "\n".join(p for p in html_parts if p)[:200_000]
    text = "\n".join(p for p in text_parts if p)
    if not text and html:
        text = _html_to_text(html)
    return text[:100_000], html


def _payload(part) -> str:
    try:
        raw = part.get_payload(decode=True)
        if raw is None:
            return ""
        charset = part.get_content_charset() or "utf-8"
        return raw.decode(charset, errors="replace")
    except Exception:
        return ""


class ParsedMessage:
    __slots__ = (
        "uid", "message_id", "from_addr", "from_name", "to_addr",
        "subject", "snippet", "body_text", "body_html", "received_at",
    )

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))


def fetch_recent(account, limit: int | None = None) -> list[ParsedMessage]:
    """Trae los últimos `limit` correos de la casilla. Abre y cierra la conexión.

    `account` debe exponer imap_host, imap_port, imap_user y una property
    `password` ya desencriptada.
    """
    limit = limit or settings.IMAP_FETCH_LIMIT
    results: list[ParsedMessage] = []

    with IMAPClient(
        host=account.imap_host,
        port=account.imap_port,
        use_uid=True,
        ssl=True,
        timeout=settings.IMAP_TIMEOUT,
    ) as server:
        server.login(account.imap_user or account.email, account.password)
        server.select_folder("INBOX", readonly=True)
        uids = server.search(["ALL"])
        if not uids:
            return results
        uids = sorted(uids)[-limit:]

        response = server.fetch(uids, ["RFC822", "INTERNALDATE"])
        for uid, data in response.items():
            raw = data.get(b"RFC822")
            if not raw:
                continue
            msg = email.message_from_bytes(raw)
            name, addr = parseaddr(msg.get("From", ""))
            _, to_addr = parseaddr(msg.get("To", ""))
            subject = _decode(msg.get("Subject", ""))
            body_text, body_html = _extract_bodies(msg)
            received = data.get(b"INTERNALDATE")
            if received is None:
                try:
                    received = parsedate_to_datetime(msg.get("Date"))
                except Exception:
                    received = datetime.now(timezone.utc)
            if received.tzinfo is None:
                received = received.replace(tzinfo=timezone.utc)

            results.append(
                ParsedMessage(
                    uid=str(uid),
                    message_id=(msg.get("Message-ID") or "")[:512],
                    from_addr=addr[:512],
                    from_name=_decode(name)[:255],
                    to_addr=to_addr[:512],
                    subject=subject[:1000],
                    snippet=(body_text or "").strip().replace("\n", " ")[:300],
                    body_text=body_text,
                    body_html=body_html,
                    received_at=received,
                )
            )
    return results


def test_connection(host: str, port: int, user: str, password: str) -> None:
    """Valida credenciales IMAP. Lanza excepción si fallan."""
    with IMAPClient(host=host, port=port, use_uid=True, ssl=True,
                    timeout=settings.IMAP_TIMEOUT) as server:
        server.login(user, password)
        server.select_folder("INBOX", readonly=True)
