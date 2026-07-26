"""Extracción restringida de códigos de verificación para el agente local."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import settings
from ..models.models import AgentCodeReceipt, MailAccount, Message

SERVICE_SENDERS = {
    "netflix": ("netflix.com",),
    "prime": ("amazon.com",),
    "amazon": ("amazon.com",),
    "max": ("max.com", "hbomax.com"),
    "crunchyroll": ("crunchyroll.com",),
}
CODE_PATTERNS = (
    re.compile(r"(?i)(?:c[oó]digo|code|verification|verificaci[oó]n|inicio de sesi[oó]n)"
               r"[^0-9]{0,40}([0-9]{4,8})"),
    re.compile(r"\b([0-9]{6})\b"),
)


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _extract_code(message: Message) -> str | None:
    text = " ".join((message.subject, message.snippet, message.body_text))
    for pattern in CODE_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1)
    return None


def claim_recent_code(
    db: Session,
    *,
    job_id: str,
    account_email: str,
    service: str,
    not_before: datetime,
) -> tuple[str, Message] | None:
    service = service.strip().lower()
    allowed_domains = SERVICE_SENDERS.get(service)
    if not allowed_domains:
        raise ValueError("Servicio no permitido")

    now = datetime.now(timezone.utc)
    earliest = now - timedelta(seconds=settings.MAIL_AGENT_CODE_MAX_AGE_SECONDS)
    not_before = max(_utc(not_before), earliest)
    account = db.scalar(
        select(MailAccount).where(
            MailAccount.email.ilike(account_email.strip()),
            MailAccount.is_enabled.is_(True),
        )
    )
    if not account:
        return None

    messages = db.scalars(
        select(Message)
        .where(
            Message.account_id == account.id,
            Message.received_at >= not_before,
            Message.received_at <= now + timedelta(minutes=1),
            Message.sender_trusted.is_(True),
        )
        .order_by(Message.received_at.desc(), Message.id.desc())
        .limit(25)
    ).all()
    for message in messages:
        sender = message.from_addr.strip().lower()
        if not any(sender.endswith("@" + domain) or sender.endswith("." + domain)
                   for domain in allowed_domains):
            continue
        code = _extract_code(message)
        if not code:
            continue
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        used = db.scalar(
            select(AgentCodeReceipt.id).where(
                AgentCodeReceipt.message_id == message.id,
                AgentCodeReceipt.code_hash == code_hash,
            )
        )
        if used:
            continue
        db.add(AgentCodeReceipt(job_id=job_id, message_id=message.id, code_hash=code_hash))
        db.commit()
        return code, message
    return None
