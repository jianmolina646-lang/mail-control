from __future__ import annotations

import email
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime
from datetime import datetime, timezone
import ssl

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
    if not html:
        return ""
    try:
        # Usar html.parser para evitar errores si lxml no está instalado en el sistema
        return BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    except Exception:
        try:
            return BeautifulSoup(html, "lxml").get_text(" ", strip=True)
        except Exception:
            return ""


def _payload(part) -> str:
    try:
        raw = part.get_payload(decode=True)
        if raw is None:
            return ""
        charset = part.get_content_charset() or "utf-8"
        return raw.decode(charset, errors="replace")
    except Exception:
        return ""


def _extract_bodies(msg: email.message.Message) -> tuple[str, str]:
    """Devuelve (texto_plano, html). Acota el tamaño para no reventar RAM."""
    text_parts: list[str] = []
    html_parts: list[str] = []

    if msg.is_multipart():
        for part in msg.walk():
            # Omitir partes contenedoras multipartes
            if part.is_multipart():
                continue
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


class ParsedMessage:
    __slots__ = (
        "uid", "message_id", "from_addr", "from_name", "to_addr",
        "subject", "snippet", "body_text", "body_html", "received_at",
    )

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))


def get_imap_username(account) -> str:
    """Asegura devolver el correo completo requerido por servidores como Outlook.com."""
    user = getattr(account, "imap_user", None) or getattr(account, "email", "")
    if "@" not in user and hasattr(account, "email") and "@" in account.email:
        return account.email
    return user


def fetch_recent(account, limit: int | None = None) -> list[ParsedMessage]:
    """Trae los últimos limit correos de la casilla. Abre y cierra la conexión.

    account debe exponer imap_host, imap_port, imap_user, email y una property
    password ya desencriptada. También puede exponer oauth_token opcional.
    """
    limit = limit or getattr(settings, "IMAP_FETCH_LIMIT", 10)
    timeout = getattr(settings, "IMAP_TIMEOUT", 30)
    results: list[ParsedMessage] = []

    username = get_imap_username(account)

    # Crear contexto SSL por defecto para mejor compatibilidad TLS/SSL con Outlook/Office365
    ssl_context = ssl.create_default_context()

    with IMAPClient(
        host=account.imap_host,
        port=account.imap_port or 993,
        use_uid=True,
        ssl=True,
        ssl_context=ssl_context,
        timeout=timeout,
    ) as server:
        # Soporte para OAuth2 si la cuenta lo provee (Requerido para cuentas Microsoft modernas)
        oauth_token = getattr(account, "oauth_token", None)
        if oauth_token:
            server.oauth2_login(username, oauth_token)
        else:
            server.login(username, account.password)

        server.select_folder("INBOX", readonly=True)
        uids = server.search(["ALL"])
        if not uids:
            return results
        uids = sorted(uids)[-limit:]

        # Usar BODY.PEEK[] en lugar de RFC822 para no marcar los correos como leídos en Outlook
        response = server.fetch(uids, ["BODY.PEEK[]", "INTERNALDATE"])
        for uid, data in response.items():
            # IMAPClient puede retornar llaves como bytes o str según la versión
            raw = (
                data.get(b"BODY.PEEK[]")
                or data.get("BODY.PEEK[]")
                or data.get(b"RFC822")
                or data.get("RFC822")
            )
            if not raw:
                continue

            msg = email.message_from_bytes(raw)
            name, addr = parseaddr(msg.get("From", ""))
            _, to_addr = parseaddr(msg.get("To", ""))
            subject = _decode(msg.get("Subject", ""))
            body_text, body_html = _extract_bodies(msg)

            received = data.get(b"INTERNALDATE") or data.get("INTERNALDATE")
            if received is None:
                try:
                    received = parsedate_to_datetime(msg.get("Date"))
                except Exception:
                    received = datetime.now(timezone.utc)
            elif isinstance(received, str):
                try:
                    received = parsedate_to_datetime(received)
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


def test_connection(host_or_account, port: int | None = None, user: str | None = None, password: str | None = None) -> None:
    """Valida credenciales IMAP. Acepta (host, port, user, password) o un objeto account."""
    if isinstance(host_or_account, str):
        host = host_or_account
        port = port or 993
        username = user or ""
        pwd = password or ""
        oauth_token = None
    else:
        host = host_or_account.imap_host
        port = host_or_account.imap_port or 993
        username = get_imap_username(host_or_account)
        pwd = getattr(host_or_account, "password", "")
        oauth_token = getattr(host_or_account, "oauth_token", None)

    timeout = getattr(settings, "IMAP_TIMEOUT", 30)
    ssl_context = ssl.create_default_context()

    with IMAPClient(
        host=host,
        port=port,
        use_uid=True,
        ssl=True,
        ssl_context=ssl_context,
        timeout=timeout,
    ) as server:
        if oauth_token:
            server.oauth2_login(username, oauth_token)
        else:
            server.login(username, pwd)
        server.select_folder("INBOX", readonly=True)
