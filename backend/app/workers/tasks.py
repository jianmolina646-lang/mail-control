"""Tareas Celery: escaneo de casillas en chunks con concurrencia estricta."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import redis as redis_lib
from sqlalchemy import delete, select

from ..core.config import settings
from ..core.crypto import decrypt
from ..core.db import SessionLocal
from ..models.models import Alert, MailAccount, Message, Subscription
from ..services import imap_service, radar, subscription_tracker
from .celery_app import celery_app

logger = logging.getLogger(__name__)

_redis = redis_lib.Redis.from_url(settings.REDIS_URL)

# --- Semáforo distribuido: máximo IMAP_MAX_CONCURRENCY conexiones en total ---
_SEM_KEY = "mailctl:imap_semaphore"
_SEM_TTL = 60 * 5  # si un worker muere, el slot se libera solo a los 5 min


@contextmanager
def imap_slot(account_id: int):
    """Reserva un slot del semáforo global de conexiones IMAP."""
    member = f"acct:{account_id}"
    acquired = False
    try:
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


class _AccountProxy:
    """Adaptador con la contraseña ya desencriptada para imap_service."""

    def __init__(self, acct: MailAccount):
        self.email = acct.email
        self.imap_host = acct.imap_host
        self.imap_port = acct.imap_port
        self.imap_user = acct.imap_user
        self.password = decrypt(acct.encrypted_password) if acct.encrypted_password else ""
        self.oauth_token = getattr(acct, "oauth_token", None)


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

    chunk = max(1, settings.IMAP_CHUNK_SIZE)
    for i in range(0, len(ids), chunk):
        scan_account_chunk.delay(ids[i : i + chunk])
    logger.info("Programados %s chunks para %s cuentas", -(-len(ids) // chunk) if ids else 0, len(ids))
    return len(ids)


@celery_app.task(name="app.workers.tasks.scan_account_chunk", bind=True, max_retries=3)
def scan_account_chunk(self, account_ids: list[int]) -> int:
    """Procesa un lote chico de cuentas EN SERIE (una conexión a la vez).
    
    Reintentos automáticos hasta 3 veces si hay errores transitorios (timeout, conexión perdida).
    """
    try:
        processed = 0
        for account_id in account_ids:
            with imap_slot(account_id) as ok:
                if not ok:
                    # Semáforo lleno: reintentar este resto más tarde.
                    logger.warning("Semáforo IMAP lleno; re-encolando cuenta %s", account_id)
                    scan_account_chunk.apply_async(args=[[account_id]], countdown=60)
                    continue
                _sync_one_account(account_id)
                processed += 1
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


def _sync_one_account(account_id: int) -> None:
    db = SessionLocal()
    try:
        acct = db.get(MailAccount, account_id)
        if not acct or not acct.is_enabled:
            logger.debug("Cuenta %s no encontrada o deshabilitada", account_id)
            return
        
        logger.info("Sincronizando cuenta: %s (%s:%d)", acct.email, acct.imap_host, acct.imap_port)
        try:
            if imap_service.is_microsoft_account(acct.imap_user, acct.imap_host):
                if not imap_service.prepare_microsoft_oauth(acct):
                    raise RuntimeError("Cuenta Microsoft pendiente de autorización OAuth2")
                db.commit()
            parsed = imap_service.fetch_recent(_AccountProxy(acct))
            logger.info("IMAP fetch_recent: %d correos traídos de %s", len(parsed), acct.email)
        except Exception as exc:
            acct.last_status = "error"
            acct.last_error = str(exc)[:500]
            acct.last_synced_at = datetime.now(timezone.utc)
            db.commit()
            logger.error("IMAP error en %s: %s (tipo: %s)", acct.email, exc, type(exc).__name__, exc_info=True)
            return

        existing = {
            (row[0], row[1])
            for row in db.execute(
                select(Message.folder_name, Message.uid)
                .where(Message.account_id == acct.id)
            ).all()
        }
        existing_message_ids = {
            row[0]
            for row in db.execute(
                select(Message.message_id).where(
                    Message.account_id == acct.id,
                    Message.message_id != "",
                )
            ).all()
        }
        logger.debug("%s: %d correos previos en BD", acct.email, len(existing))
        
        new_messages = 0
        new_alerts = 0
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
            msg = Message(
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
            db.add(msg)
            db.flush()
            existing.add(message_key)
            if pm.message_id:
                existing_message_ids.add(pm.message_id)
            new_messages += 1
            
            if is_alert:
                logger.info("🚨 ALERTA DETECTADA en %s: servicio=%s, keyword=%s, asunto=%s", 
                           acct.email, classification.service, classification.reason, pm.subject[:100])
                db.add(Alert(
                    message_id=msg.id,
                    service=classification.service,
                    keyword=classification.reason,
                    severity=classification.severity,
                ))
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
        db.commit()
        
        logger.info("✓ Sincronización exitosa de %s: %d nuevos correos, %d alertas", 
                   acct.email, new_messages, new_alerts)
    except Exception as exc:
        logger.critical("Error crítico en _sync_one_account: %s", exc, exc_info=True)
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.cleanup_old_messages")
def cleanup_old_messages(days: int = 30) -> int:
    """Borra correos de más de `days` días SIN alerta, para cuidar el disco."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
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
        logger.info("Radar reconstruido: %s mensajes con estado", detected)
        return detected
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
