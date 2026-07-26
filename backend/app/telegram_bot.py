"""Bot privado de consulta para el administrador de Mail Control."""

from __future__ import annotations

import html
import json
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from urllib import parse, request

import redis as redis_lib
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from .core.config import settings
from .core.db import SessionLocal
from .models.models import Alert, MailAccount, Message, Subscription
from .services.telegram_notifier import send_message

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mail_control.telegram")
_redis = redis_lib.Redis.from_url(settings.REDIS_URL)
_CODE_RE = re.compile(
    r"(?<!\d)(\d{4,8})(?!\d)",
)


def _api(method: str, payload: dict[str, object] | None = None, timeout: int = 40) -> dict:
    data = parse.urlencode(payload or {}).encode()
    req = request.Request(
        f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/{method}",
        data=data,
        method="POST",
    )
    with request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode())


def _menu() -> dict:
    return {
        "keyboard": [
            [{"text": "📊 Resumen"}, {"text": "🚨 Alertas"}],
            [{"text": "📬 Cuentas"}, {"text": "❓ Ayuda"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def _help() -> str:
    return (
        "🤖 <b>MAIL CONTROL</b>\n\n"
        "Consulta privada del sistema:\n"
        "/resumen — estado general\n"
        "/alertas — alertas pendientes\n"
        "/cuentas — cuentas conectadas\n"
        "/buscar correo@dominio.com — últimos correos de una cuenta\n"
        "/codigo correo@dominio.com — último código reciente y confiable\n\n"
        "Solo el administrador autorizado puede utilizar este bot."
    )


def _summary() -> str:
    db = SessionLocal()
    try:
        accounts = db.scalar(select(func.count(MailAccount.id))) or 0
        connected = db.scalar(
            select(func.count(MailAccount.id)).where(MailAccount.last_status == "ok")
        ) or 0
        open_alerts = db.scalar(
            select(func.count(Alert.id)).where(Alert.resolved.is_(False))
        ) or 0
        subscriptions = db.scalar(select(func.count(Subscription.id))) or 0
        return (
            "📊 <b>RESUMEN DE MAIL CONTROL</b>\n\n"
            f"📬 Cuentas: <b>{accounts}</b>\n"
            f"✅ Conectadas: <b>{connected}</b>\n"
            f"🚨 Alertas pendientes: <b>{open_alerts}</b>\n"
            f"📺 Servicios detectados: <b>{subscriptions}</b>"
        )
    finally:
        db.close()


def _alerts() -> str:
    db = SessionLocal()
    try:
        rows = (
            db.query(Alert)
            .options(joinedload(Alert.message).joinedload(Message.account))
            .filter(Alert.resolved.is_(False))
            .order_by(Alert.created_at.desc())
            .limit(10)
            .all()
        )
        if not rows:
            return "✅ <b>Sin alertas pendientes</b>\n\nNo hay incidencias que requieran atención."
        lines = ["🚨 <b>ALERTAS PENDIENTES</b>"]
        for item in rows:
            lines.append(
                "\n"
                f"• <b>{html.escape(item.service or 'Servicio')}</b> · "
                f"{html.escape(item.keyword)}\n"
                f"  <code>{html.escape(item.message.account.email)}</code>\n"
                f"  {html.escape(item.message.subject[:100])}"
            )
        return "\n".join(lines)
    finally:
        db.close()


def _accounts() -> str:
    db = SessionLocal()
    try:
        rows = db.scalars(select(MailAccount).order_by(MailAccount.email)).all()
        if not rows:
            return "📭 No hay cuentas conectadas."
        lines = ["📬 <b>CUENTAS CONECTADAS</b>"]
        for account in rows[:30]:
            icon = "✅" if account.last_status == "ok" else "⚠️"
            lines.append(
                f"\n{icon} <code>{html.escape(account.email)}</code>\n"
                f"   {html.escape(account.provider)} · {html.escape(account.last_status)}"
            )
        if len(rows) > 30:
            lines.append(f"\n… y {len(rows) - 30} cuentas más.")
        return "\n".join(lines)
    finally:
        db.close()


def _find_account(email: str) -> tuple[MailAccount | None, list[Message]]:
    db = SessionLocal()
    try:
        account = db.scalar(
            select(MailAccount).where(func.lower(MailAccount.email) == email.lower())
        )
        if not account:
            return None, []
        messages = db.scalars(
            select(Message)
            .where(Message.account_id == account.id)
            .order_by(Message.received_at.desc())
            .limit(8)
        ).all()
        db.expunge(account)
        for message in messages:
            db.expunge(message)
        return account, list(messages)
    finally:
        db.close()


def _search(email: str) -> str:
    account, messages = _find_account(email)
    if not account:
        return "❌ Esa cuenta no está registrada en Mail Control."
    if not messages:
        return f"📭 No hay correos guardados para <code>{html.escape(email)}</code>."
    lines = [f"🔎 <b>ÚLTIMOS CORREOS</b>\n<code>{html.escape(email)}</code>"]
    for message in messages:
        lines.append(
            f"\n• <b>{html.escape(message.from_name or message.from_addr)[:80]}</b>\n"
            f"  {html.escape(message.subject[:120])}"
        )
    return "\n".join(lines)


def _code(email: str) -> str:
    db = SessionLocal()
    try:
        account = db.scalar(
            select(MailAccount).where(func.lower(MailAccount.email) == email.lower())
        )
        if not account:
            return "❌ Esa cuenta no está registrada en Mail Control."
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=15)
        messages = db.scalars(
            select(Message)
            .where(
                Message.account_id == account.id,
                Message.received_at >= cutoff,
                Message.sender_trusted.is_(True),
            )
            .order_by(Message.received_at.desc())
            .limit(10)
        ).all()
        for message in messages:
            source = f"{message.subject}\n{message.body_text[:4000]}"
            match = _CODE_RE.search(source)
            if match:
                return (
                    "🔐 <b>CÓDIGO RECIENTE</b>\n\n"
                    f"Cuenta: <code>{html.escape(email)}</code>\n"
                    f"Código: <code>{match.group(1)}</code>\n"
                    f"Remitente: {html.escape(message.from_name or message.from_addr)}\n\n"
                    "No compartas este código con personas no autorizadas."
                )
        return "⏳ No encontré un código confiable recibido durante los últimos 15 minutos."
    finally:
        db.close()


def _handle(update: dict) -> None:
    message = update.get("message") or {}
    chat = message.get("chat") or {}
    sender = message.get("from") or {}
    text = (message.get("text") or "").strip()
    chat_id = int(chat.get("id") or 0)
    user_id = int(sender.get("id") or 0)

    if chat.get("type") != "private":
        return
    if user_id != settings.TELEGRAM_ADMIN_CHAT_ID or chat_id != settings.TELEGRAM_ADMIN_CHAT_ID:
        logger.warning("Acceso Telegram rechazado para user_id=%s", user_id)
        return

    normalized = text.lower()
    if normalized in {"/start", "/ayuda", "/help", "❓ ayuda"}:
        send_message(_help(), reply_markup=_menu())
    elif normalized in {"/resumen", "📊 resumen"}:
        send_message(_summary(), reply_markup=_menu())
    elif normalized in {"/alertas", "🚨 alertas"}:
        send_message(_alerts(), reply_markup=_menu())
    elif normalized in {"/cuentas", "📬 cuentas"}:
        send_message(_accounts(), reply_markup=_menu())
    elif normalized.startswith("/buscar "):
        send_message(_search(text.split(maxsplit=1)[1].strip()))
    elif normalized.startswith("/codigo "):
        send_message(_code(text.split(maxsplit=1)[1].strip()))
    else:
        send_message("No reconocí ese comando.\n\n" + _help(), reply_markup=_menu())


def run() -> None:
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_ADMIN_CHAT_ID:
        raise RuntimeError("TELEGRAM_BOT_TOKEN y TELEGRAM_ADMIN_CHAT_ID son obligatorios")
    identity = _api("getMe", timeout=15)
    if not identity.get("ok"):
        raise RuntimeError(f"Telegram rechazó el token: {identity.get('description')}")
    _api("deleteWebhook", {"drop_pending_updates": "false"}, timeout=15)
    logger.info("Bot privado iniciado como @%s", identity["result"]["username"])
    offset = int(_redis.get("mailctl:telegram:update-offset") or 0)
    while True:
        try:
            result = _api(
                "getUpdates",
                {"offset": offset, "timeout": 30, "allowed_updates": json.dumps(["message"])},
                timeout=40,
            )
            for update in result.get("result", []):
                offset = int(update["update_id"]) + 1
                _handle(update)
                _redis.set("mailctl:telegram:update-offset", offset)
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            logger.warning("Error temporal consultando Telegram: %s", exc)
            time.sleep(5)


if __name__ == "__main__":
    run()
