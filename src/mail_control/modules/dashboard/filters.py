from __future__ import annotations

import shlex
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import String, cast, func, or_, text
from sqlalchemy.dialects.postgresql import JSONB, JSONPATH
from sqlalchemy.sql.elements import ColumnElement

from mail_control.modules.analysis.models import EmailAnalysis, RiskLevel
from mail_control.modules.mail.models import EmailMessage, MailAccount, MailProvider

CATEGORY_GROUPS = {
    "pagos": ("pagos", "pago", "payment", "payments", "billing"),
    "codigos": ("codigos", "códigos", "codigo", "código", "code", "codes", "verification"),
    "cuentas": ("cuentas", "cuenta", "account", "accounts"),
    "seguridad": ("seguridad", "security"),
    "renovaciones": ("renovaciones", "renovacion", "renewal", "renewals"),
    "accesos": ("accesos", "acceso", "access", "login"),
    "otros": ("otros", "other", "general"),
}


def category_key(value: str) -> str:
    value = value.casefold()
    return next((key for key, values in CATEGORY_GROUPS.items() if value in values), value)


def _date(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError:
        raise ValueError("invalid search date; use ISO 8601") from None


@dataclass
class MessageFilters:
    search: str | None = None
    account_id: UUID | None = None
    provider: str | None = None
    category: str | None = None
    risk_level: str | None = None
    is_read: bool | None = None
    is_starred: bool | None = None
    account: str | None = None
    sender: str | None = None
    recipient: str | None = None
    platform: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    has_attachments: bool | None = None

    def conditions(self) -> list[ColumnElement[bool]]:
        # Legacy search operators are consumed here, never passed into full-text SQL.
        values = dict(vars(self))
        free: list[str] = []
        operators = {
            "proveedor": "provider", "provider": "provider", "riesgo": "risk_level",
            "risk": "risk_level", "categoria": "category", "categoría": "category",
            "category": "category", "cuenta": "account", "account": "account",
            "de": "sender", "from": "sender", "para": "recipient", "to": "recipient",
            "plataforma": "platform", "platform": "platform", "despues": "date_from",
            "after": "date_from", "antes": "date_to", "before": "date_to",
        }
        try:
            tokens = shlex.split(self.search or "")
        except ValueError:
            raise ValueError("unclosed search quote") from None
        for token in tokens:
            name, separator, value = token.partition(":")
            key = operators.get(name.casefold())
            if separator and key:
                if not value:
                    raise ValueError(f"missing value for {name}")
                if values[key] is None:
                    values[key] = value
            elif separator and name.casefold() in {"es", "is", "estado"}:
                states = {
                    "unread": ("is_read", False), "no-leido": ("is_read", False),
                    "no_leido": ("is_read", False), "read": ("is_read", True),
                    "leido": ("is_read", True), "starred": ("is_starred", True),
                    "destacado": ("is_starred", True),
                }
                state = states.get(value.casefold())
                if state is None:
                    raise ValueError("invalid message state filter")
                if values[state[0]] is None:
                    values[state[0]] = state[1]
            else:
                free.append(f'"{token}"' if " " in token else token)
        conditions: list[ColumnElement[bool]] = []
        if free:
            conditions.append(text(
                "email_messages.search_vector @@ websearch_to_tsquery('simple', :search)"
            ).bindparams(search=" ".join(free)))  # type: ignore[arg-type]
        if self.account_id:
            conditions.append(EmailMessage.mail_account_id == self.account_id)
        if values["provider"]:
            provider = str(values["provider"]).casefold()
            if provider in {"outlook", "hotmail", "live"}:
                conditions.append(func.lower(MailAccount.email).like(f"%@{provider}.%"))
                provider = "microsoft"
            if provider not in {"gmail", "microsoft"}:
                raise ValueError("invalid mail provider")
            conditions.append(MailAccount.provider == MailProvider(provider))
        if values["category"]:
            category = category_key(str(values["category"]))
            if category in {"sin-analizar", "unanalyzed"}:
                conditions.append(EmailAnalysis.id.is_(None))
            else:
                conditions.append(func.lower(EmailAnalysis.category).in_(
                    CATEGORY_GROUPS.get(category, (category,))
                ))
        if values["risk_level"]:
            aliases = {"alto": "high", "medio": "medium", "bajo": "low",
                       "critico": "critical", "crítico": "critical"}
            try:
                risks = [RiskLevel(aliases.get(value.casefold(), value.casefold()))
                         for value in str(values["risk_level"]).split(",")]
            except ValueError:
                raise ValueError("invalid risk level") from None
            conditions.append(EmailAnalysis.risk_level.in_(risks))
        for name in ("is_read", "is_starred"):
            if values[name] is not None:
                conditions.append(getattr(EmailMessage, name).is_(values[name]))
        for name, column in (("account", MailAccount.email), ("sender", EmailMessage.sender),
                             ("recipient", cast(EmailMessage.recipients, String))):
            if values[name]:
                conditions.append(column.icontains(str(values[name]), autoescape=True))
        if values["platform"]:
            value = str(values["platform"])
            conditions.append(or_(EmailAnalysis.platform.icontains(value, autoescape=True),
                                  EmailAnalysis.service.icontains(value, autoescape=True)))
        if self.has_attachments is not None:
            attached = func.coalesce(or_(
                EmailMessage.payload["hasAttachments"].as_boolean().is_(True),
                func.jsonb_path_exists(cast(EmailMessage.payload, JSONB),
                                       cast('$.payload.** ? (@.filename != "")', JSONPATH)),
            ), False)
            conditions.append(attached if self.has_attachments else ~attached)
        start, end = _date(values["date_from"]), _date(values["date_to"])
        if start and end and start >= end:
            raise ValueError("date_from must be before date_to")
        if start:
            conditions.append(func.coalesce(EmailMessage.received_at,
                                           EmailMessage.created_at) >= start)
        if end:
            conditions.append(func.coalesce(EmailMessage.received_at,
                                           EmailMessage.created_at) < end)
        return conditions
