from __future__ import annotations

import base64

from mail_control.modules.mail.content import message_body, message_html
from mail_control.modules.mail.models import MailProvider


def encoded(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")


def test_extracts_nested_gmail_plain_text() -> None:
    payload = {
        "payload": {
            "mimeType": "multipart/alternative",
            "parts": [
                {"mimeType": "text/plain", "body": {"data": encoded("Mensaje completo")}},
                {"mimeType": "text/html", "body": {"data": encoded("<p>HTML</p>")}},
            ],
        }
    }
    assert message_body(payload, MailProvider.GMAIL, "preview") == "Mensaje completo"


def test_extracts_microsoft_html_as_safe_text() -> None:
    payload = {"body": {"contentType": "html", "content": "<p>Hola <b>cliente</b></p>"}}
    assert message_body(payload, MailProvider.MICROSOFT, "preview") == "Hola cliente"
    assert message_html(payload, MailProvider.MICROSOFT) == "<p>Hola <b>cliente</b></p>"


def test_falls_back_to_snippet() -> None:
    assert message_body({}, MailProvider.GMAIL, "preview") == "preview"
    assert message_html({}, MailProvider.GMAIL) is None


def test_ignores_gmail_html_attachment() -> None:
    payload = {
        "payload": {
            "mimeType": "multipart/mixed",
            "parts": [
                {
                    "mimeType": "text/html",
                    "filename": "report.html",
                    "body": {"data": encoded("<p>attachment</p>")},
                },
                {"mimeType": "text/plain", "body": {"data": encoded("real body")}},
            ],
        }
    }
    assert message_html(payload, MailProvider.GMAIL) is None
    assert message_body(payload, MailProvider.GMAIL, "preview") == "real body"
