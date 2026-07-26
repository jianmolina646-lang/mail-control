"""Notificaciones privadas de Mail Control mediante Telegram."""

from __future__ import annotations

import html
import json
import logging
from urllib import parse, request

import redis as redis_lib

from ..core.config import settings

logger = logging.getLogger(__name__)
_redis = redis_lib.Redis.from_url(settings.REDIS_URL)
_API_BASE = "https://api.telegram.org/bot"


def enabled() -> bool:
    return bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_ADMIN_CHAT_ID)


def _call(method: str, payload: dict[str, object], *, timeout: int = 15) -> dict:
    if not enabled():
        return {"ok": False, "description": "Telegram no configurado"}
    body = parse.urlencode(payload).encode()
    req = request.Request(
        f"{_API_BASE}{settings.TELEGRAM_BOT_TOKEN}/{method}",
        data=body,
        method="POST",
    )
    with request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode())


def send_message(text: str, *, reply_markup: dict | None = None) -> bool:
    """Envía al único administrador autorizado; nunca propaga fallos al escaneo."""
    if not enabled():
        return False
    payload: dict[str, object] = {
        "chat_id": settings.TELEGRAM_ADMIN_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    try:
        result = _call("sendMessage", payload)
        if not result.get("ok"):
            logger.warning("Telegram rechazó una notificación: %s", result.get("description"))
        return bool(result.get("ok"))
    except Exception as exc:
        logger.warning("No se pudo enviar una notificación por Telegram: %s", exc)
        return False


def notify_critical_alert(
    *,
    alert_id: int,
    account_email: str,
    service: str,
    severity: str,
    reason: str,
    subject: str,
) -> None:
    if not settings.TELEGRAM_NOTIFY_ALERTS:
        return
    severity_icon = "🔴" if severity == "critical" else "🟠"
    text = (
        f"{severity_icon} <b>ALERTA DE SUSCRIPCIÓN</b>\n\n"
        f"<b>Servicio:</b> {html.escape(service or 'No identificado')}\n"
        f"<b>Cuenta:</b> <code>{html.escape(account_email)}</code>\n"
        f"<b>Motivo:</b> {html.escape(reason)}\n"
        f"<b>Correo:</b> {html.escape(subject[:180])}\n\n"
        "Revisa Mail Control antes de realizar cambios."
    )
    send_message(
        text,
        reply_markup={
            "inline_keyboard": [[
                {
                    "text": "Revisar alerta",
                    "callback_data": f"alert:{alert_id}",
                },
                {
                    "text": "Abrir panel",
                    "url": f"{settings.FRONTEND_URL.rstrip('/')}/alertas",
                },
            ]]
        },
    )


def notify_account_error(*, account_id: int, email: str, error: str) -> None:
    if not settings.TELEGRAM_NOTIFY_ACCOUNT_ERRORS or not enabled():
        return
    # Como máximo un aviso por cuenta y hora para evitar inundar el chat.
    key = f"mailctl:telegram:account-error:{account_id}"
    try:
        if not _redis.set(key, "1", nx=True, ex=3600):
            return
    except Exception:
        # Si Redis no está disponible, se omite el aviso para evitar duplicados.
        return
    oauth_required = any(
        marker in error.lower()
        for marker in ("oauth", "autorización", "authorization", "token", "revincular")
    )
    title = "🔐 <b>CUENTA REQUIERE REVINCULACIÓN</b>" if oauth_required else (
        "⚠️ <b>ERROR DE SINCRONIZACIÓN</b>"
    )
    action = (
        "\n\nAbre <b>Cuentas conectadas</b> y pulsa <b>Revincular</b>."
        if oauth_required
        else "\n\nMail Control volverá a intentarlo automáticamente."
    )
    send_message(
        f"{title}\n\n"
        f"<b>Cuenta:</b> <code>{html.escape(email)}</code>\n"
        f"<b>Detalle:</b> {html.escape(error[:350])}"
        f"{action}",
        reply_markup={
            "inline_keyboard": [[{
                "text": "Abrir cuentas",
                "url": f"{settings.FRONTEND_URL.rstrip('/')}/cuentas",
            }]]
        },
    )
