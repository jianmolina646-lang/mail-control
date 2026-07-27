"""Bot privado de operación para el administrador de Mail Control."""

from __future__ import annotations

import html
import hashlib
import json
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from urllib import parse, request

import redis as redis_lib
from bs4 import BeautifulSoup
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from .core.config import settings
from .core.db import SessionLocal
from .models.models import AgentCodeReceipt, Alert, MailAccount, Message, Subscription
from .services.telegram_notifier import send_message

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mail_control.telegram")
_redis = redis_lib.Redis.from_url(settings.REDIS_URL)
_PAGE_SIZE = 5
_CODE_PATTERNS = (
    re.compile(
        r"(?i)(?:código|codigo|code|verification|verificación|inicio de sesión)"
        r"[^0-9]{0,40}([0-9]{4,8})"
    ),
    re.compile(r"(?<!\d)(\d{6})(?!\d)"),
)
_NETFLIX_URL_PATTERN = re.compile(r"https://[^\s<>\"']+", re.IGNORECASE)
_NETFLIX_LOGIN_TERMS = (
    "inicio de sesión",
    "inicio de sesion",
    "iniciar sesión",
    "iniciar sesion",
    "sin contraseña",
    "sin contrasena",
    "sign in",
    "signin",
    "log in",
    "login",
    "acceso temporal",
)
_NETFLIX_LINK_TERMS = (
    "tv2",
    "login",
    "signin",
    "sign-in",
    "password",
    "auth",
    "access",
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
            [
                {"text": "📊 Resumen", "style": "primary"},
                {"text": "🚨 Alertas", "style": "danger"},
            ],
            [
                {"text": "📬 Cuentas", "style": "primary"},
                {"text": "🧾 Auditoría", "style": "success"},
            ],
            [{"text": "❓ Ayuda", "style": "primary"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def _mask_email(email: str) -> str:
    local, separator, domain = email.partition("@")
    if not separator:
        return email
    visible = local[:2]
    return f"{visible}{'•' * max(3, min(8, len(local) - len(visible)))}@{domain}"


def _audit(action: str, detail: str = "") -> None:
    event = json.dumps(
        {
            "at": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "detail": detail[:180],
        }
    )
    try:
        pipe = _redis.pipeline()
        pipe.lpush("mailctl:telegram:audit", event)
        pipe.ltrim("mailctl:telegram:audit", 0, 199)
        pipe.execute()
    except Exception as exc:
        logger.warning("No se pudo registrar auditoría Telegram: %s", exc)


def _help() -> str:
    return (
        "💠 <b>MAIL CONTROL · CENTRO OPERATIVO</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>Comandos disponibles</b>\n\n"
        "/resumen — estado general\n"
        "/alertas — incidencias con filtros y resolución\n"
        "/cuentas — estado y sincronización inmediata\n"
        "/buscar correo@dominio.com — últimos mensajes\n"
        "/codigo correo@dominio.com — código reciente confiable\n"
        "/netflix correo@dominio.com — enlace reciente de Netflix\n"
        "/auditoria — últimas operaciones del bot\n\n"
        "🛡 <i>Acceso privado · acciones protegidas con confirmación</i>"
    )


def _summary() -> tuple[str, dict]:
    db = SessionLocal()
    try:
        accounts = db.scalar(select(func.count(MailAccount.id))) or 0
        connected = db.scalar(
            select(func.count(MailAccount.id)).where(MailAccount.last_status == "ok")
        ) or 0
        errors = db.scalar(
            select(func.count(MailAccount.id)).where(MailAccount.last_status == "error")
        ) or 0
        open_alerts = db.scalar(
            select(func.count(Alert.id)).where(Alert.resolved.is_(False))
        ) or 0
        subscriptions = db.scalar(select(func.count(Subscription.id))) or 0
        text = (
            "💠 <b>MAIL CONTROL</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📊 <b>RESUMEN OPERATIVO</b>\n\n"
            f"📬 <b>{accounts}</b>  cuentas supervisadas\n"
            f"🟢 <b>{connected}</b>  conectadas\n"
            f"🟠 <b>{errors}</b>  requieren revisión\n"
            f"🔴 <b>{open_alerts}</b>  alertas pendientes\n"
            f"📺 <b>{subscriptions}</b>  servicios detectados\n\n"
            "🛡 <i>Supervisión automática activa</i>"
        )
        markup = {
            "inline_keyboard": [
                [
                    {"text": "🚨 Ver alertas", "callback_data": "alerts:0:all", "style": "danger"},
                    {"text": "📬 Ver cuentas", "callback_data": "accounts:0", "style": "primary"},
                ],
                [{"text": "🔄 Sincronizar todas", "callback_data": "syncall:ask", "style": "success"}],
            ]
        }
        return text, markup
    finally:
        db.close()


def _alerts(page: int = 0, service: str = "all") -> tuple[str, dict]:
    page = max(0, page)
    db = SessionLocal()
    try:
        query = (
            db.query(Alert)
            .options(joinedload(Alert.message).joinedload(Message.account))
            .filter(Alert.resolved.is_(False))
        )
        if service != "all":
            query = query.filter(func.lower(Alert.service) == service.lower())
        total = query.count()
        rows = (
            query.order_by(Alert.created_at.desc())
            .offset(page * _PAGE_SIZE)
            .limit(_PAGE_SIZE)
            .all()
        )
        title = "🔴 <b>CENTRO DE ALERTAS</b>\n━━━━━━━━━━━━━━━━━━━━"
        if service != "all":
            title += f"\nFiltro: <b>{html.escape(service)}</b>"
        lines = [title, f"\nResultados: <b>{total}</b>"]
        buttons: list[list[dict[str, str]]] = []
        for item in rows:
            lines.append(
                "\n"
                f"• <b>#{item.id} · {html.escape(item.service or 'Servicio')}</b>\n"
                f"  {html.escape(item.keyword)} · "
                f"<code>{html.escape(_mask_email(item.message.account.email))}</code>\n"
                f"  {html.escape(item.message.subject[:90])}"
            )
            buttons.append([{
                "text": f"Revisar #{item.id} · {item.service or 'Servicio'}",
                "callback_data": f"alert:{item.id}",
                "style": "danger" if item.severity == "critical" else "primary",
            }])
        if not rows:
            lines.append("\n✅ No hay alertas en esta selección.")

        navigation: list[dict[str, str]] = []
        if page > 0:
            navigation.append({
                "text": "◀️ Anterior",
                "callback_data": f"alerts:{page - 1}:{service}",
                "style": "primary",
            })
        if (page + 1) * _PAGE_SIZE < total:
            navigation.append({
                "text": "Siguiente ▶️",
                "callback_data": f"alerts:{page + 1}:{service}",
                "style": "primary",
            })
        if navigation:
            buttons.append(navigation)

        services = [
            row[0]
            for row in db.execute(
                select(Alert.service)
                .where(Alert.resolved.is_(False), Alert.service != "")
                .distinct()
                .order_by(Alert.service)
                .limit(8)
            ).all()
        ]
        filter_buttons = [{
            "text": "Todas",
            "callback_data": "alerts:0:all",
            "style": "success" if service == "all" else "primary",
        }]
        filter_buttons.extend(
            {
                "text": item[:16],
                "callback_data": f"alerts:0:{item}"[:64],
                "style": "success" if item.lower() == service.lower() else "primary",
            }
            for item in services
        )
        for index in range(0, len(filter_buttons), 3):
            buttons.append(filter_buttons[index:index + 3])
        return "\n".join(lines), {"inline_keyboard": buttons}
    finally:
        db.close()


def _alert_detail(alert_id: int) -> tuple[str, dict]:
    db = SessionLocal()
    try:
        item = (
            db.query(Alert)
            .options(joinedload(Alert.message).joinedload(Message.account))
            .filter(Alert.id == alert_id)
            .first()
        )
        if not item:
            return "❌ La alerta ya no existe.", {"inline_keyboard": []}
        state = "Resuelta" if item.resolved else "Pendiente"
        text = (
            f"🔴 <b>ALERTA #{item.id}</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<b>Estado:</b> {state}\n"
            f"<b>Severidad:</b> {html.escape(item.severity)}\n"
            f"<b>Servicio:</b> {html.escape(item.service or 'No identificado')}\n"
            f"<b>Cuenta:</b> <code>{html.escape(_mask_email(item.message.account.email))}</code>\n"
            f"<b>Motivo:</b> {html.escape(item.keyword)}\n"
            f"<b>Remitente:</b> {html.escape(item.message.from_name or item.message.from_addr)}\n"
            f"<b>Asunto:</b> {html.escape(item.message.subject[:220])}\n"
            f"<b>Fecha:</b> {item.created_at:%d/%m/%Y %H:%M} UTC"
        )
        buttons = [[
            {"text": "📨 Ver en panel", "url": f"{settings.FRONTEND_URL.rstrip('/')}/alertas"},
        ]]
        if not item.resolved:
            buttons.insert(0, [{
                "text": "✅ Marcar resuelta",
                "callback_data": f"resolve:ask:{item.id}",
                "style": "success",
            }])
        buttons.append([{"text": "◀️ Volver", "callback_data": "alerts:0:all", "style": "primary"}])
        return text, {"inline_keyboard": buttons}
    finally:
        db.close()


def _resolve_alert(alert_id: int) -> str:
    db = SessionLocal()
    try:
        item = db.get(Alert, alert_id)
        if not item:
            return "❌ La alerta ya no existe."
        if item.resolved:
            return f"ℹ️ La alerta #{alert_id} ya estaba resuelta."
        item.resolved = True
        db.commit()
        _audit("resolve_alert", str(alert_id))
        return f"✅ Alerta #{alert_id} marcada como resuelta."
    finally:
        db.close()


def _accounts(page: int = 0) -> tuple[str, dict]:
    page = max(0, page)
    db = SessionLocal()
    try:
        total = db.scalar(select(func.count(MailAccount.id))) or 0
        rows = db.scalars(
            select(MailAccount)
            .order_by(MailAccount.email)
            .offset(page * _PAGE_SIZE)
            .limit(_PAGE_SIZE)
        ).all()
        lines = ["📬 <b>CUENTAS CONECTADAS</b>\n━━━━━━━━━━━━━━━━━━━━", f"\nTotal supervisado: <b>{total}</b>"]
        buttons: list[list[dict[str, str]]] = []
        for account in rows:
            icon = "✅" if account.last_status == "ok" else "⚠️"
            oauth = " · OAuth2" if account.auth_method == "oauth2" else ""
            lines.append(
                f"\n{icon} <code>{html.escape(_mask_email(account.email))}</code>\n"
                f"   {html.escape(account.provider)}{oauth} · {html.escape(account.last_status)}"
            )
            buttons.append([{
                "text": f"🔄 Sincronizar {_mask_email(account.email)}",
                "callback_data": f"sync:{account.id}",
                "style": "success",
            }])
        navigation: list[dict[str, str]] = []
        if page > 0:
            navigation.append({"text": "◀️ Anterior", "callback_data": f"accounts:{page - 1}", "style": "primary"})
        if (page + 1) * _PAGE_SIZE < total:
            navigation.append({"text": "Siguiente ▶️", "callback_data": f"accounts:{page + 1}", "style": "primary"})
        if navigation:
            buttons.append(navigation)
        buttons.append([{"text": "🔄 Sincronizar todas", "callback_data": "syncall:ask", "style": "success"}])
        return "\n".join(lines), {"inline_keyboard": buttons}
    finally:
        db.close()


def _queue_sync(account_id: int) -> str:
    db = SessionLocal()
    try:
        account = db.get(MailAccount, account_id)
        if not account or not account.is_enabled:
            return "❌ La cuenta no existe o está deshabilitada."
        email = account.email
    finally:
        db.close()
    from .workers.tasks import queue_account_sync

    queue_account_sync(account_id)
    _audit("sync_account", str(account_id))
    return f"🔄 Sincronización programada para <code>{html.escape(_mask_email(email))}</code>."


def _queue_sync_all() -> str:
    from .workers.tasks import scan_all_accounts

    scan_all_accounts.delay()
    _audit("sync_all")
    return "🔄 Sincronización de todas las cuentas programada."


def _find_account(email: str) -> tuple[MailAccount | None, list[Message]]:
    db = SessionLocal()
    try:
        account = db.scalar(
            select(MailAccount).where(func.lower(MailAccount.email) == email.lower())
        )
        if not account:
            return None, []
        messages = list(db.scalars(
            select(Message)
            .where(Message.account_id == account.id)
            .order_by(Message.received_at.desc())
            .limit(8)
        ).all())
        db.expunge(account)
        for message in messages:
            db.expunge(message)
        return account, messages
    finally:
        db.close()


def _search(email: str) -> str:
    account, messages = _find_account(email)
    if not account:
        return "❌ Esa cuenta no está registrada en Mail Control."
    if not messages:
        return f"📭 No hay correos guardados para <code>{html.escape(_mask_email(email))}</code>."
    lines = [f"🔎 <b>ÚLTIMOS CORREOS</b>\n━━━━━━━━━━━━━━━━━━━━\n<code>{html.escape(_mask_email(email))}</code>"]
    for message in messages:
        lines.append(
            f"\n• <b>{html.escape(message.from_name or message.from_addr)[:80]}</b>\n"
            f"  {html.escape(message.subject[:120])}"
        )
    _audit("search_mail", _mask_email(email))
    return "\n".join(lines)


def _extract_code(message: Message) -> str | None:
    source = f"{message.subject}\n{message.snippet}\n{message.body_text[:4000]}"
    for pattern in _CODE_PATTERNS:
        match = pattern.search(source)
        if match:
            return match.group(1)
    return None


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
            code = _extract_code(message)
            if code:
                _audit("read_code", _mask_email(email))
                return (
                    "🔐 <b>CÓDIGO SEGURO</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"Cuenta: <code>{html.escape(_mask_email(email))}</code>\n"
                    f"Código: <code>{code}</code>\n"
                    f"Remitente: {html.escape(message.from_name or message.from_addr)}\n\n"
                    "Este mensaje se entrega únicamente al administrador autorizado."
                )
        return "⏳ No encontré un código confiable recibido durante los últimos 15 minutos."
    finally:
        db.close()


def _is_netflix_domain(value: str) -> bool:
    domain = value.strip().lower().rstrip(".")
    return domain == "netflix.com" or domain.endswith(".netflix.com")


def _extract_netflix_link(message: Message) -> str | None:
    candidates: list[str] = []
    if message.body_html:
        soup = BeautifulSoup(message.body_html, "html.parser")
        candidates.extend(
            str(anchor.get("href") or "")
            for anchor in soup.find_all("a", href=True)
        )
    candidates.extend(
        _NETFLIX_URL_PATTERN.findall(
            f"{message.subject}\n{message.snippet}\n{message.body_text[:20_000]}"
        )
    )
    valid: list[tuple[int, str]] = []
    for candidate in candidates:
        url = html.unescape(candidate).strip().rstrip(".,);")
        parsed = parse.urlsplit(url)
        if parsed.scheme == "https" and parsed.hostname and _is_netflix_domain(
            parsed.hostname
        ):
            target = f"{parsed.path}?{parsed.query}".lower()
            score = sum(term in target for term in _NETFLIX_LINK_TERMS)
            valid.append((score, url))
    if not valid:
        return None
    valid.sort(key=lambda item: item[0], reverse=True)
    return valid[0][1]


def _netflix_link(
    *,
    email: str | None = None,
    account_id: int | None = None,
) -> tuple[str, dict]:
    db = SessionLocal()
    try:
        account = db.scalar(
            select(MailAccount).where(
                MailAccount.id == account_id
                if account_id is not None
                else func.lower(MailAccount.email) == (email or "").lower(),
                MailAccount.is_enabled.is_(True),
            )
        )
        if not account:
            return "❌ Esa cuenta no está registrada o está deshabilitada.", {
                "inline_keyboard": []
            }

        cutoff = datetime.now(timezone.utc) - timedelta(minutes=15)
        messages = db.scalars(
            select(Message)
            .where(
                Message.account_id == account.id,
                Message.received_at >= cutoff,
                Message.sender_trusted.is_(True),
            )
            .order_by(Message.received_at.desc(), Message.id.desc())
            .limit(25)
        ).all()
        for message in messages:
            sender_domain = message.from_addr.strip().lower().rsplit("@", 1)[-1]
            if not _is_netflix_domain(sender_domain):
                continue
            login_context = f"{message.subject}\n{message.snippet}".lower()
            if not any(term in login_context for term in _NETFLIX_LOGIN_TERMS):
                continue
            link = _extract_netflix_link(message)
            if not link:
                continue
            link_hash = hashlib.sha256(link.encode()).hexdigest()
            used = db.scalar(
                select(AgentCodeReceipt.id).where(
                    AgentCodeReceipt.message_id == message.id,
                    AgentCodeReceipt.code_hash == link_hash,
                )
            )
            if used:
                continue
            db.add(
                AgentCodeReceipt(
                    job_id="telegram-netflix-link",
                    message_id=message.id,
                    code_hash=link_hash,
                )
            )
            db.commit()
            _audit("read_netflix_link", f"{_mask_email(account.email)} · msg {message.id}")
            return (
                "🎬 <b>ENLACE SEGURO DE NETFLIX</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                f"Cuenta: <code>{html.escape(_mask_email(account.email))}</code>\n"
                "Recibido durante los últimos 15 minutos.\n\n"
                "⚠️ Úsalo únicamente en el dispositivo que solicitó el acceso.",
                {"inline_keyboard": [[{
                    "text": "Abrir enlace de Netflix",
                    "url": link,
                    "style": "success",
                }]]},
            )

        from .workers.tasks import queue_account_sync

        queue_account_sync(account.id)
        _audit("queue_netflix_link", _mask_email(account.email))
        return (
            "⏳ Todavía no encontré un enlace nuevo y confiable de Netflix.\n\n"
            "Programé una sincronización inmediata. Espera unos segundos y pulsa "
            "<b>Buscar nuevamente</b>.",
            {"inline_keyboard": [[{
                "text": "🔄 Buscar nuevamente",
                "callback_data": f"netflix:{account.id}",
                "style": "primary",
            }]]},
        )
    finally:
        db.close()


def _audit_report() -> str:
    try:
        records = _redis.lrange("mailctl:telegram:audit", 0, 9)
    except Exception:
        return "⚠️ No se pudo consultar la auditoría."
    if not records:
        return "🧾 Todavía no hay operaciones administrativas registradas."
    lines = ["🧾 <b>REGISTRO DE AUDITORÍA</b>\n━━━━━━━━━━━━━━━━━━━━"]
    for raw in records:
        event = json.loads(raw)
        timestamp = datetime.fromisoformat(event["at"]).strftime("%d/%m %H:%M")
        lines.append(
            f"\n• <b>{html.escape(event['action'])}</b> · {timestamp} UTC"
            + (f"\n  {html.escape(event['detail'])}" if event.get("detail") else "")
        )
    return "\n".join(lines)


def _authorized(chat: dict, sender: dict) -> bool:
    return (
        chat.get("type") == "private"
        and int(chat.get("id") or 0) == settings.TELEGRAM_ADMIN_CHAT_ID
        and int(sender.get("id") or 0) == settings.TELEGRAM_ADMIN_CHAT_ID
    )


def _edit(callback: dict, text: str, markup: dict | None = None) -> None:
    message = callback.get("message") or {}
    payload: dict[str, object] = {
        "chat_id": settings.TELEGRAM_ADMIN_CHAT_ID,
        "message_id": message.get("message_id"),
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }
    if markup is not None:
        payload["reply_markup"] = json.dumps(markup)
    try:
        _api("editMessageText", payload, timeout=15)
    except Exception:
        send_message(text, reply_markup=markup)


def _handle_callback(update: dict) -> None:
    callback = update.get("callback_query") or {}
    sender = callback.get("from") or {}
    message = callback.get("message") or {}
    if not _authorized(message.get("chat") or {}, sender):
        return
    data = callback.get("data") or ""
    try:
        _api("answerCallbackQuery", {"callback_query_id": callback.get("id")}, timeout=10)
    except Exception:
        pass

    if data.startswith("alerts:"):
        _, page, service = data.split(":", 2)
        text, markup = _alerts(int(page), service)
        _edit(callback, text, markup)
    elif data.startswith("alert:"):
        text, markup = _alert_detail(int(data.split(":")[1]))
        _edit(callback, text, markup)
    elif data.startswith("resolve:ask:"):
        alert_id = int(data.rsplit(":", 1)[1])
        _edit(
            callback,
            f"⚠️ <b>CONFIRMAR ACCIÓN</b>\n\n¿Marcar la alerta #{alert_id} como resuelta?",
            {"inline_keyboard": [[
                {"text": "✅ Sí, resolver", "callback_data": f"resolve:yes:{alert_id}", "style": "success"},
                {"text": "Cancelar", "callback_data": f"alert:{alert_id}", "style": "danger"},
            ]]},
        )
    elif data.startswith("resolve:yes:"):
        alert_id = int(data.rsplit(":", 1)[1])
        _edit(callback, _resolve_alert(alert_id), {
            "inline_keyboard": [[{"text": "Volver a alertas", "callback_data": "alerts:0:all", "style": "primary"}]]
        })
    elif data.startswith("accounts:"):
        text, markup = _accounts(int(data.split(":")[1]))
        _edit(callback, text, markup)
    elif data.startswith("sync:"):
        _edit(callback, _queue_sync(int(data.split(":")[1])))
    elif data == "syncall:ask":
        _edit(
            callback,
            "⚠️ <b>CONFIRMAR SINCRONIZACIÓN</b>\n\n"
            "Se conectará a todas las cuentas habilitadas.",
            {"inline_keyboard": [[
                {"text": "✅ Confirmar", "callback_data": "syncall:yes", "style": "success"},
                {"text": "Cancelar", "callback_data": "accounts:0", "style": "danger"},
            ]]},
        )
    elif data == "syncall:yes":
        _edit(callback, _queue_sync_all())
    elif data.startswith("netflix:"):
        text, markup = _netflix_link(account_id=int(data.split(":", 1)[1]))
        _edit(callback, text, markup)


def _handle_message(update: dict) -> None:
    message = update.get("message") or {}
    chat = message.get("chat") or {}
    sender = message.get("from") or {}
    if not _authorized(chat, sender):
        logger.warning("Acceso Telegram rechazado para user_id=%s", sender.get("id"))
        return
    text = (message.get("text") or "").strip()
    normalized = text.lower()
    _audit("command", normalized.split(maxsplit=1)[0][:40])

    if normalized in {"/start", "/ayuda", "/help", "❓ ayuda"}:
        send_message(_help(), reply_markup=_menu())
    elif normalized in {"/resumen", "📊 resumen"}:
        body, markup = _summary()
        send_message(body, reply_markup=markup)
    elif normalized in {"/alertas", "🚨 alertas"}:
        body, markup = _alerts()
        send_message(body, reply_markup=markup)
    elif normalized in {"/cuentas", "📬 cuentas"}:
        body, markup = _accounts()
        send_message(body, reply_markup=markup)
    elif normalized in {"/auditoria", "🧾 auditoría", "🧾 auditoria"}:
        send_message(_audit_report(), reply_markup=_menu())
    elif normalized.startswith("/buscar "):
        send_message(_search(text.split(maxsplit=1)[1].strip()))
    elif normalized.startswith("/codigo "):
        send_message(_code(text.split(maxsplit=1)[1].strip()))
    elif normalized.startswith("/netflix "):
        body, markup = _netflix_link(email=text.split(maxsplit=1)[1].strip())
        send_message(body, reply_markup=markup)
    else:
        send_message("No reconocí ese comando.\n\n" + _help(), reply_markup=_menu())


def _handle(update: dict) -> None:
    if update.get("callback_query"):
        _handle_callback(update)
    elif update.get("message"):
        _handle_message(update)


def run() -> None:
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_ADMIN_CHAT_ID:
        raise RuntimeError("TELEGRAM_BOT_TOKEN y TELEGRAM_ADMIN_CHAT_ID son obligatorios")
    identity = _api("getMe", timeout=15)
    if not identity.get("ok"):
        raise RuntimeError(f"Telegram rechazó el token: {identity.get('description')}")
    _api("deleteWebhook", {"drop_pending_updates": "false"}, timeout=15)
    _api(
        "setMyCommands",
        {
            "commands": json.dumps([
                {"command": "resumen", "description": "Estado general"},
                {"command": "alertas", "description": "Alertas pendientes"},
                {"command": "cuentas", "description": "Cuentas conectadas"},
                {"command": "buscar", "description": "Últimos correos de una cuenta"},
                {"command": "codigo", "description": "Código reciente confiable"},
                {"command": "netflix", "description": "Enlace reciente de Netflix"},
                {"command": "auditoria", "description": "Operaciones del bot"},
                {"command": "ayuda", "description": "Comandos disponibles"},
            ]),
        },
        timeout=15,
    )
    logger.info("Bot privado iniciado como @%s", identity["result"]["username"])
    offset = int(_redis.get("mailctl:telegram:update-offset") or 0)
    while True:
        try:
            result = _api(
                "getUpdates",
                {
                    "offset": offset,
                    "timeout": 30,
                    "allowed_updates": json.dumps(["message", "callback_query"]),
                },
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
