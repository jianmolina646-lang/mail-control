"""Tareas Celery: escaneo de casillas en chunks con concurrencia estricta."""

from __future__ import annotations

import logging
import shutil
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import redis as redis_lib
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ..core.config import settings
from ..core.crypto import decrypt
from ..core.db import SessionLocal
from ..models.models import Alert, MailAccount, Message, Subscription, SyncEvent
from ..services import imap_service, radar, subscription_tracker, telegram_notifier
from .celery_app import celery_app

logger = logging.getLogger(__name__)

_redis = redis_lib.Redis.from_url(settings.REDIS_URL)

# --- Semáforo distribuido: máximo IMAP_MAX_CONCURRENCY conexiones en total ---
_SEM_KEY = "mailctl:imap_semaphore"
_SEM_TTL = 60 * 5  # si un worker muere, el slot se libera solo a los 5 min
_ACCOUNT_LOCK_TTL = 60 * 12
_PENDING_TTL = 60 * 30
_RELEASE_LOCK_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
end
return 0
"""


@contextmanager
def imap_slot(account_id: int):
    """Reserva un slot global y un bloqueo exclusivo por cuenta."""
    token = uuid.uuid4().hex
    account_key = f"mailctl:imap_account_lock:{account_id}"
    member = f"acct:{account_id}:{token}"
    account_locked = False
    acquired = False
    try:
        account_locked = bool(
            _redis.set(account_key, token, nx=True, ex=_ACCOUNT_LOCK_TTL)
        )
        if not account_locked:
            yield False
            return

        # Limpia slots viejos (crash de workers) y trata de reservar.
        now = datetime.now(timezone.utc).timestamp()
        _redis.zremrangebyscore(_SEM_KEY, 0, now - _SEM_TTL)
        if _redis.zcard(_SEM_KEY) < settings.IMAP_MAX_CONCURRENCY:
            _redis.zadd(_SEM_KEY, {member: now})
            acquired = True
        yield acquired
    finally:
        if acquired:
            _redis.zrem(_SEM_KEY, member)
        if account_locked:
            _redis.eval(_RELEASE_LOCK_SCRIPT, 1, account_key, token)


class _AccountProxy:
    """Adaptador con la contraseña ya desencriptada para imap_service."""

    def __init__(self, acct: MailAccount):
        self.email = acct.email
        self.imap_host = acct.imap_host
        self.imap_port = acct.imap_port
        self.imap_user = acct.imap_user
        self.password = decrypt(acct.encrypted_password) if acct.encrypted_password else ""
        self.oauth_token = getattr(acct, "oauth_token", None)


def _pending_key(account_id: int) -> str:
    return f"mailctl:imap_pending:{account_id}"


def _is_transient_imap_error(exc: Exception) -> bool:
    if isinstance(exc, (TimeoutError, ConnectionError, OSError)):
        return True
    detail = str(exc).lower()
    return any(
        marker in detail
        for marker in (
            "timed out",
            "timeout",
            "connection reset",
            "connection aborted",
            "connection closed",
            "temporary",
            "temporarily",
            "try again",
            "eof",
        )
    )


def _fetch_recent_with_retry(account, **kwargs):
    attempts = max(1, settings.IMAP_RETRY_ATTEMPTS)
    for attempt in range(1, attempts + 1):
        try:
            return imap_service.fetch_recent(account, **kwargs)
        except Exception as exc:
            if not _is_transient_imap_error(exc) or attempt >= attempts:
                raise
            delay = max(0, settings.IMAP_RETRY_DELAY_SECONDS * attempt)
            logger.warning(
                "Fallo IMAP transitorio para %s; reintento %s/%s en %ss: %s",
                getattr(account, "email", "?"),
                attempt + 1,
                attempts,
                delay,
                exc,
            )
            if delay:
                time.sleep(delay)
    raise RuntimeError("No se pudo completar la sincronización IMAP")


def _consecutive_failures(db, account_id: int) -> int:
    statuses = db.scalars(
        select(SyncEvent.status)
        .where(SyncEvent.account_id == account_id)
        .order_by(SyncEvent.created_at.desc())
        .limit(max(1, settings.IMAP_FAILURES_BEFORE_ALERT))
    ).all()
    count = 0
    for status in statuses:
        if status != "error":
            break
        count += 1
    return count


def queue_account_sync(account_id: int) -> bool:
    """Encola una cuenta solo si no está pendiente o en ejecución."""
    key = _pending_key(account_id)
    if not _redis.set(key, "1", nx=True, ex=_PENDING_TTL):
        return False
    try:
        scan_account_chunk.apply_async(
            args=[[account_id]],
            kwargs={"reserved": True},
        )
    except Exception:
        _redis.delete(key)
        raise
    return True


@celery_app.task(name="app.workers.tasks.scan_all_accounts")
def scan_all_accounts() -> int:
    """Dispara el escaneo de todas las cuentas habilitadas, en chunks chicos."""
    db = SessionLocal()
    try:
        ids = [
            row[0]
            for row in db.execute(
                select(MailAccount.id)
                .where(MailAccount.is_enabled.is_(True))
                .order_by(MailAccount.last_synced_at.asc().nulls_first())
            ).all()
        ]
    finally:
        db.close()

    reserved_ids = [
        account_id
        for account_id in ids
        if _redis.set(_pending_key(account_id), "1", nx=True, ex=_PENDING_TTL)
    ]
    chunk = max(1, settings.IMAP_CHUNK_SIZE)
    for i in range(0, len(reserved_ids), chunk):
        batch = reserved_ids[i : i + chunk]
        try:
            scan_account_chunk.apply_async(
                args=[batch],
                kwargs={"reserved": True},
            )
        except Exception:
            for account_id in batch:
                _redis.delete(_pending_key(account_id))
            raise
    logger.info(
        "Programados %s chunks para %s cuentas; %s ya estaban pendientes",
        -(-len(reserved_ids) // chunk) if reserved_ids else 0,
        len(reserved_ids),
        len(ids) - len(reserved_ids),
    )
    return len(reserved_ids)


@celery_app.task(name="app.workers.tasks.scan_account_chunk", bind=True, max_retries=3)
def scan_account_chunk(
    self,
    account_ids: list[int],
    reserved: bool = False,
) -> int:
    """Procesa un lote chico de cuentas EN SERIE (una conexión a la vez).
    
    Reintentos automáticos hasta 3 veces si hay errores transitorios (timeout, conexión perdida).
    """
    try:
        processed = 0
        for account_id in account_ids:
            pending_key = _pending_key(account_id)
            owns_pending = reserved or bool(
                _redis.set(pending_key, "1", nx=True, ex=_PENDING_TTL)
            )
            if not owns_pending:
                logger.info("Tarea duplicada descartada para cuenta %s", account_id)
                continue
            try:
                with imap_slot(account_id) as ok:
                    if not ok:
                        logger.info("Sincronización duplicada omitida para cuenta %s", account_id)
                        continue
                    _sync_one_account(account_id)
                    processed += 1
            finally:
                _redis.delete(pending_key)
        return processed
    except Exception as exc:
        # Reintentar con delay exponencial si hay errores transitorios
        err_str = str(exc).lower()
        if any(x in err_str for x in ["timeout", "connection", "temporary", "temporarily", "try again"]):
            logger.warning("Error transitorio en scan_account_chunk, reintentando... (intento %d/3)", 
                          self.request.retries + 1)
            raise self.retry(exc=exc, countdown=30 * (self.request.retries + 1))
        else:
            # Errores permanentes no se reintentan
            logger.error("Error permanente en scan_account_chunk, no se reintenta: %s", exc)
            raise


@celery_app.task(name="app.workers.tasks.scan_account_for_codes")
def scan_account_for_codes(account_id: int) -> int:
    """Sincronización prioritaria: solo 10 mensajes recientes de INBOX."""
    with imap_slot(account_id) as ok:
        if not ok:
            logger.info("Sincronización urgente duplicada omitida para cuenta %s", account_id)
            return 0
        _sync_one_account(account_id, urgent=True)
        return 1


def _sync_one_account(account_id: int, *, urgent: bool = False) -> None:
    started_at = time.monotonic()
    db = SessionLocal()
    try:
        acct = db.get(MailAccount, account_id)
        if not acct or not acct.is_enabled:
            logger.debug("Cuenta %s no encontrada o deshabilitada", account_id)
            return

        previous_failures = _consecutive_failures(db, acct.id)
        message_cutoff = datetime.now(timezone.utc) - timedelta(
            days=settings.MESSAGE_RETENTION_DAYS
        )
        existing_rows = db.execute(
            select(Message.folder_name, Message.uid)
            .where(
                Message.account_id == acct.id,
                Message.received_at >= message_cutoff,
            )
        ).all()
        existing = {(row[0], row[1]) for row in existing_rows}
        known_uids_by_folder: dict[str, set[str]] = {}
        for folder_name, uid in existing_rows:
            known_uids_by_folder.setdefault(folder_name, set()).add(uid)

        logger.info("Sincronizando cuenta: %s (%s:%d)", acct.email, acct.imap_host, acct.imap_port)
        try:
            if imap_service.is_microsoft_account(acct.imap_user, acct.imap_host):
                if not imap_service.prepare_microsoft_oauth(acct):
                    raise RuntimeError("Cuenta Microsoft pendiente de autorización OAuth2")
                db.commit()
            parsed = _fetch_recent_with_retry(
                _AccountProxy(acct),
                limit=10 if urgent else None,
                include_other_folders=not urgent,
                known_uids_by_folder=known_uids_by_folder,
            )
            logger.info("IMAP fetch_recent: %d correos traídos de %s", len(parsed), acct.email)
        except Exception as exc:
            acct.last_status = "error"
            acct.last_error = str(exc)[:500]
            acct.last_synced_at = datetime.now(timezone.utc)
            db.add(SyncEvent(
                account_id=acct.id,
                status="error",
                duration_ms=round((time.monotonic() - started_at) * 1000),
                error=str(exc)[:500],
            ))
            db.commit()
            if previous_failures + 1 >= settings.IMAP_FAILURES_BEFORE_ALERT:
                telegram_notifier.notify_account_error(
                    account_id=acct.id,
                    email=acct.email,
                    error=str(exc),
                )
            else:
                logger.warning(
                    "Primer fallo IMAP de %s; se reintentará sin alertar al usuario",
                    acct.email,
                )
            logger.error("IMAP error en %s: %s (tipo: %s)", acct.email, exc, type(exc).__name__, exc_info=True)
            return

        existing_message_ids = {
            row[0]
            for row in db.execute(
                select(Message.message_id).where(
                    Message.account_id == acct.id,
                    Message.message_id != "",
                    Message.received_at >= message_cutoff,
                )
            ).all()
        }
        logger.debug("%s: %d correos previos en BD", acct.email, len(existing))
        
        new_messages = 0
        new_alerts = 0
        telegram_alerts: list[dict[str, object]] = []
        for pm in parsed:
            message_key = (pm.folder_name, pm.uid)
            if message_key in existing:
                logger.debug(
                    "Mensaje %s/%s ya existe, saltando",
                    pm.folder_name,
                    pm.uid,
                )
                continue
            if pm.message_id and pm.message_id in existing_message_ids:
                logger.debug(
                    "Message-ID %s ya existe en otra carpeta, saltando",
                    pm.message_id,
                )
                continue
            
            classification = radar.classify(
                pm.from_addr, pm.subject, pm.body_text
            )
            is_alert = classification.is_alert
            insert_result = db.execute(
                pg_insert(Message)
                .values(
                    account_id=acct.id,
                    uid=pm.uid,
                    folder_name=pm.folder_name,
                    message_id=pm.message_id,
                    from_addr=pm.from_addr,
                    from_name=pm.from_name,
                    to_addr=pm.to_addr,
                    subject=pm.subject,
                    snippet=pm.snippet,
                    body_text=pm.body_text,
                    body_html=pm.body_html,
                    received_at=pm.received_at,
                    is_alert=is_alert,
                    sender_trusted=classification.sender_trusted,
                    security_warning=classification.security_warning,
                )
                .on_conflict_do_nothing()
                .returning(Message.id)
            )
            inserted_id = insert_result.scalar_one_or_none()
            if inserted_id is None:
                logger.debug(
                    "Mensaje %s/%s insertado por otra sincronización, saltando",
                    pm.folder_name,
                    pm.uid,
                )
                existing.add(message_key)
                if pm.message_id:
                    existing_message_ids.add(pm.message_id)
                continue
            msg = db.get(Message, inserted_id)
            if msg is None:
                raise RuntimeError("No se pudo recuperar el mensaje recién insertado")
            existing.add(message_key)
            if pm.message_id:
                existing_message_ids.add(pm.message_id)
            new_messages += 1
            
            if is_alert:
                logger.info("🚨 ALERTA DETECTADA en %s: servicio=%s, keyword=%s, asunto=%s", 
                           acct.email, classification.service, classification.reason, pm.subject[:100])
                alert = Alert(
                    message_id=msg.id,
                    service=classification.service,
                    keyword=classification.reason,
                    severity=classification.severity,
                )
                db.add(alert)
                db.flush()
                telegram_alerts.append({
                    "alert_id": alert.id,
                    "account_email": acct.email,
                    "service": classification.service,
                    "severity": classification.severity,
                    "reason": classification.reason,
                    "subject": pm.subject,
                })
                new_alerts += 1
            subscription_tracker.apply_classification(
                db,
                account_id=acct.id,
                message=msg,
                result=classification,
            )

        acct.last_status = "ok"
        acct.last_error = ""
        acct.last_synced_at = datetime.now(timezone.utc)
        db.add(SyncEvent(
            account_id=acct.id,
            status="ok",
            messages_found=len(parsed),
            new_messages=new_messages,
            duration_ms=round((time.monotonic() - started_at) * 1000),
        ))
        db.commit()
        if previous_failures >= settings.IMAP_FAILURES_BEFORE_ALERT:
            telegram_notifier.notify_account_recovered(
                account_id=acct.id,
                email=acct.email,
            )
        
        logger.info("✓ Sincronización exitosa de %s: %d nuevos correos, %d alertas", 
                   acct.email, new_messages, new_alerts)
    except Exception as exc:
        logger.critical("Error crítico en _sync_one_account: %s", exc, exc_info=True)
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.cleanup_old_messages")
def cleanup_old_messages(days: int | None = None) -> int:
    """Borra correos de más de `days` días SIN alerta, para cuidar el disco."""
    retention_days = days or settings.MESSAGE_RETENTION_DAYS
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    db = SessionLocal()
    try:
        result = db.execute(
            delete(Message).where(
                Message.received_at < cutoff,
                Message.is_alert.is_(False),
            )
        )
        db.commit()
        return result.rowcount or 0
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.cleanup_old_sync_events")
def cleanup_old_sync_events(days: int | None = None) -> int:
    """Conserva un historial operativo acotado para evitar crecimiento ilimitado."""
    retention_days = days or settings.SYNC_EVENT_RETENTION_DAYS
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    db = SessionLocal()
    try:
        result = db.execute(delete(SyncEvent).where(SyncEvent.created_at < cutoff))
        db.commit()
        return result.rowcount or 0
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.rebuild_subscription_states")
def rebuild_subscription_states() -> int:
    """Reclasifica el historial completo usando las reglas actuales."""
    db = SessionLocal()
    try:
        db.execute(delete(Alert))
        db.execute(delete(Subscription))
        messages = db.scalars(
            select(Message).order_by(Message.received_at.asc(), Message.id.asc())
        ).all()
        detected = 0
        for message in messages:
            result = radar.classify(
                message.from_addr,
                message.subject,
                message.body_text,
            )
            message.is_alert = result.is_alert
            message.sender_trusted = result.sender_trusted
            message.security_warning = result.security_warning
            if result.is_alert:
                db.add(
                    Alert(
                        message_id=message.id,
                        service=result.service,
                        keyword=result.reason,
                        severity=result.severity,
                    )
                )
            if result.status != "unknown":
                subscription_tracker.apply_classification(
                    db,
                    account_id=message.account_id,
                    message=message,
                    result=result,
                )
                detected += 1
        db.commit()

        for telegram_alert in telegram_alerts:
            telegram_notifier.notify_critical_alert(**telegram_alert)
        logger.info("Radar reconstruido: %s mensajes con estado", detected)
        return detected
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.send_telegram_daily_summary")
def send_telegram_daily_summary() -> int:
    """Envía a las 08:00 de Lima un resumen operativo sin datos sensibles."""
    if not settings.TELEGRAM_DAILY_SUMMARY:
        return 0
    db = SessionLocal()
    try:
        accounts = db.scalar(select(func.count(MailAccount.id))) or 0
        connected = db.scalar(
            select(func.count(MailAccount.id)).where(MailAccount.last_status == "ok")
        ) or 0
        errors = db.scalar(
            select(func.count(MailAccount.id)).where(MailAccount.last_status == "error")
        ) or 0
        alerts = db.scalar(
            select(func.count(Alert.id)).where(Alert.resolved.is_(False))
        ) or 0
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        messages = db.scalar(
            select(func.count(Message.id)).where(Message.received_at >= since)
        ) or 0
    finally:
        db.close()
    sent = telegram_notifier.send_message(
        "☀️ <b>RESUMEN DIARIO · MAIL CONTROL</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📬 Cuentas: <b>{accounts}</b>\n"
        f"✅ Conectadas: <b>{connected}</b>\n"
        f"⚠️ Con error: <b>{errors}</b>\n"
        f"🚨 Alertas pendientes: <b>{alerts}</b>\n"
        f"✉️ Correos recibidos en 24 h: <b>{messages}</b>",
        reply_markup={
            "inline_keyboard": [[
                {"text": "Ver alertas", "callback_data": "alerts:0:all", "style": "danger"},
                {"text": "Ver cuentas", "callback_data": "accounts:0", "style": "primary"},
            ]]
        },
    )
    return int(sent)


def _memory_percent() -> int:
    try:
        with open("/sys/fs/cgroup/memory.current", encoding="utf-8") as handle:
            current = int(handle.read())
        with open("/sys/fs/cgroup/memory.max", encoding="utf-8") as handle:
            maximum_text = handle.read().strip()
        if maximum_text == "max":
            return 0
        maximum = int(maximum_text)
        return round(current * 100 / maximum) if maximum else 0
    except (OSError, ValueError):
        return 0


@celery_app.task(name="app.workers.tasks.monitor_system_health")
def monitor_system_health() -> int:
    issues: list[str] = []
    disk = shutil.disk_usage("/")
    disk_percent = round(disk.used * 100 / disk.total)
    memory_percent = _memory_percent()
    queue_size = _redis.llen("celery")
    if disk_percent >= settings.SYSTEM_DISK_ALERT_PERCENT:
        issues.append(f"Disco en {disk_percent}%")
    if memory_percent >= settings.SYSTEM_MEMORY_ALERT_PERCENT:
        issues.append(f"Memoria del contenedor en {memory_percent}%")
    if queue_size >= settings.SYSTEM_QUEUE_ALERT_SIZE:
        issues.append(f"Cola de tareas con {queue_size} pendientes")
    telegram_notifier.notify_system_health(issues=issues)
    return len(issues)
