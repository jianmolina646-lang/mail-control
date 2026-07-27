"""Celery configurado para un VPS de 1 vCPU / 2 GB RAM.

Claves anti-OOM:
- worker_concurrency=2 (procesos), prefetch=1: nunca hay más de 2 chunks en RAM.
- Cada chunk procesa IMAP_CHUNK_SIZE cuentas en serie, abriendo y cerrando
  cada conexión IMAP. Un semáforo distribuido en Redis limita las conexiones
  IMAP concurrentes de TODO el sistema a IMAP_MAX_CONCURRENCY (50).
- worker_max_tasks_per_child recicla el proceso cada 50 tareas (libera RAM).
"""

from celery import Celery
from celery.schedules import crontab

from ..core.config import settings

celery_app = Celery(
    "mail_control",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    timezone="UTC",
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    worker_concurrency=2,
    worker_max_tasks_per_child=50,
    worker_max_memory_per_child=300_000,  # KB: recicla el proceso si pasa ~300 MB
    task_time_limit=60 * 10,
    task_soft_time_limit=60 * 8,
    broker_connection_retry_on_startup=True,
    result_expires=3600,
)

celery_app.conf.beat_schedule = {
    "scan-all-accounts": {
        "task": "app.workers.tasks.scan_all_accounts",
        "schedule": settings.SCAN_INTERVAL_MINUTES * 60.0,
    },
    "cleanup-old-messages": {
        "task": "app.workers.tasks.cleanup_old_messages",
        "schedule": crontab(hour=4, minute=30),
    },
    # 13:00 UTC equivale a las 08:00 en America/Lima.
    "telegram-daily-summary": {
        "task": "app.workers.tasks.send_telegram_daily_summary",
        "schedule": crontab(hour=13, minute=0),
    },
    "monitor-system-health": {
        "task": "app.workers.tasks.monitor_system_health",
        "schedule": 5 * 60.0,
    },
}
