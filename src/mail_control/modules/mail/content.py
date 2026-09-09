from __future__ import annotations

import base64
from email.message import Message
from email.utils import formataddr, getaddresses
from html.parser import HTMLParser
from typing import Any

from mail_control.modules.mail.models import MailProvider


class _TextExtractor(HTMLParser):
    block_tags = {"br", "div", "p", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in self.block_tags:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self.block_tags:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def text(self) -> str:
        lines = (" ".join(line.split()) for line in "".join(self.parts).splitlines())
        return "\n".join(line for line in lines if line).strip()


def html_to_text(value: str) -> str:
    parser = _TextExtractor()
    parser.feed(value)
    parser.close()
    return parser.text()


MAX_BODY_BYTES = 2 * 1024 * 1024


def _decode_gmail_data(data: str, charset: str = "utf-8") -> str:
    if len(data) > (MAX_BODY_BYTES * 4 // 3) + 8:
        raise ValueError("message body exceeds the 2 MiB limit")
    padding = "=" * (-len(data) % 4)
    decoded = base64.urlsafe_b64decode(data + padding)
    try:
        return decoded.decode(charset, errors="replace").strip()
    except LookupError:
        return decoded.decode("utf-8", errors="replace").strip()


def part_headers(part: dict[str, Any]) -> dict[str, str]:
    return {str(header.get("name", "")).casefold(): str(header.get("value", ""))
            for header in part.get("headers", []) if isinstance(header, dict)}


def message_recipients(payload: dict[str, Any], provider: MailProvider) -> tuple[
    list[str], list[str]
]:
    if provider == MailProvider.GMAIL:
        headers = payload.get("payload", {}).get("headers", [])
        def gmail_values(name: str) -> list[str]:
            values = [str(header.get("value", "")) for header in headers
                      if isinstance(header, dict)
                      and str(header.get("name", "")).casefold() == name]
            return [formataddr((display, address)) for display, address in getaddresses(values)
                    if address]
        return gmail_values("to"), gmail_values("cc")

    def graph_values(name: str) -> list[str]:
        result = []
        for recipient in payload.get(name, []):
            address = recipient.get("emailAddress", {})
            if address.get("address"):
                result.append(formataddr((address.get("name") or "", address["address"])))
        return result
    return graph_values("toRecipients"), graph_values("ccRecipients")


def _gmail_part(
    payload: dict[str, Any],
    mime_type: str,
    *,
    preserve_html: bool = False,
    depth: int = 0,
) -> str | None:
    if depth > 30:
        return None
    filename = payload.get("filename")
    headers = payload.get("headers")
    disposition = ""
    if isinstance(headers, list):
        disposition = " ".join(
            str(header.get("value", ""))
            for header in headers
            if isinstance(header, dict)
            and str(header.get("name", "")).lower() == "content-disposition"
        ).lower()
    if filename or "attachment" in disposition:
        return None
    if payload.get("mimeType") == mime_type:
        body = payload.get("body")
        if isinstance(body, dict) and isinstance(body.get("data"), str):
            mime_header = Message()
            mime_header["content-type"] = part_headers(payload).get("content-type", mime_type)
            decoded = _decode_gmail_data(body["data"], mime_header.get_content_charset() or "utf-8")
            if mime_type == "text/html" and not preserve_html:
                return html_to_text(decoded)
            return decoded
    parts = payload.get("parts")
    if isinstance(parts, list):
        for part in parts:
            if isinstance(part, dict):
                result = _gmail_part(part, mime_type, preserve_html=preserve_html, depth=depth + 1)
                if result:
                    return result
    return None


def message_html(payload: dict[str, Any], provider: MailProvider) -> str | None:
    if provider == MailProvider.GMAIL:
        gmail_payload = payload.get("payload")
        if isinstance(gmail_payload, dict):
            return _gmail_part(gmail_payload, "text/html", preserve_html=True)
    else:
        body = payload.get("body")
        if isinstance(body, dict) and str(body.get("contentType", "")).lower() == "html":
            content = body.get("content")
            if isinstance(content, str):
                return content
    return None


def message_body(
    payload: dict[str, Any],
    provider: MailProvider,
    snippet: str | None,
) -> str | None:
    if provider == MailProvider.GMAIL:
        gmail_payload = payload.get("payload")
        if isinstance(gmail_payload, dict):
            return (
                _gmail_part(gmail_payload, "text/plain")
                or _gmail_part(gmail_payload, "text/html")
                or snippet
            )
    else:
        body = payload.get("body")
        if isinstance(body, dict) and isinstance(body.get("content"), str):
            content = body["content"]
            return html_to_text(content) if body.get("contentType") == "html" else content.strip()
    return snippet
