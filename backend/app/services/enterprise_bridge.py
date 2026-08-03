"""Read-only Telegram bridge plus durable sync publishing for Mail Control Enterprise."""

from __future__ import annotations

import json
import os
from contextlib import closing
from datetime import datetime
from uuid import UUID

import pika
import psycopg2
from psycopg2.extras import RealDictCursor


DATABASE_URL = os.getenv(
    "ENTERPRISE_DATABASE_URL",
    "postgresql://mail_control:mail_control@mail-control-enterprise-postgres-1:5432/mail_control",
)
RABBITMQ_URL = os.getenv(
    "ENTERPRISE_RABBITMQ_URL",
    "amqp://mail_control:mail_control@mail-control-enterprise-rabbitmq-1:5672/",
)


def _rows(sql: str, params: tuple[object, ...] = ()) -> list[dict]:
    with closing(psycopg2.connect(DATABASE_URL, connect_timeout=8)) as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]


def accounts() -> list[dict]:
    return _rows(
        """
        SELECT a.id, a.tenant_id, a.email, a.provider::text AS provider,
               a.status::text AS status, a.last_synced_at, a.last_error,
               count(m.id)::int AS message_count
        FROM mail_accounts a
        LEFT JOIN email_messages m ON m.mail_account_id = a.id
        GROUP BY a.id
        ORDER BY lower(a.email)
        """
    )


def recent_messages(email: str, limit: int = 8) -> list[dict]:
    return _rows(
        """
        SELECT m.sender, m.subject, m.snippet, m.received_at
        FROM email_messages m
        JOIN mail_accounts a ON a.id = m.mail_account_id
        WHERE lower(a.email) = lower(%s) AND m.deleted_at IS NULL
        ORDER BY coalesce(m.received_at, m.created_at) DESC
        LIMIT %s
        """,
        (email, limit),
    )


def queue_sync(account_id: str) -> str:
    selected = _rows(
        "SELECT id, tenant_id, provider::text AS provider, email FROM mail_accounts WHERE id=%s",
        (str(UUID(account_id)),),
    )
    if not selected:
        raise ValueError("La cuenta Enterprise no existe.")
    account = selected[0]
    provider = str(account["provider"]).lower()
    queue = "mail.sync.microsoft" if provider == "microsoft" else "mail.sync.gmail"
    parameters = pika.URLParameters(RABBITMQ_URL)
    parameters.socket_timeout = 8
    connection = pika.BlockingConnection(parameters)
    try:
        channel = connection.channel()
        channel.queue_declare(queue=queue, durable=True)
        channel.basic_publish(
            exchange="",
            routing_key=queue,
            body=json.dumps(
                {
                    "tenant_id": str(account["tenant_id"]),
                    "mail_account_id": str(account["id"]),
                }
            ).encode(),
            properties=pika.BasicProperties(delivery_mode=2),
        )
    finally:
        connection.close()
    return str(account["email"])


def queue_all() -> int:
    rows = accounts()
    for account in rows:
        queue_sync(str(account["id"]))
    return len(rows)


def format_time(value: datetime | None) -> str:
    return value.strftime("%d/%m %H:%M UTC") if value else "Pendiente"
