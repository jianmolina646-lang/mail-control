from __future__ import annotations

import hashlib
import re
from contextlib import suppress
from html import escape
from pathlib import Path

import httpx
import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

from mail_control.modules.mail.models import MailAccount
from mail_control.settings import Settings

logger = structlog.get_logger(__name__)
_SPACE = re.compile(r"\s+")


class TelegramAlerts:
    def __init__(self, settings: Settings, redis: Redis) -> None:
        self.redis = redis
        self.token, self.chat_id = self._credentials(settings.telegram_alerts_file)
        self.dedupe_seconds = settings.telegram_account_alert_dedupe_seconds

    @staticmethod
    def _credentials(filename: str | None) -> tuple[str, str]:
        if not filename:
            return "", ""
        try:
            values: dict[str, str] = {}
            for raw_line in Path(filename).read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"').strip("'")
            return values.get("TELEGRAM_BOT_TOKEN", ""), values.get("TELEGRAM_CHAT_ID", "")
        except OSError as error:
            logger.warning(
                "telegram_alert_credentials_unavailable",
                error_type=type(error).__name__,
            )
            return "", ""

    def _active_key(self, account: MailAccount) -> str:
        return f"mail-control:telegram-alert:{account.id}:active"

    def _dedupe_key(self, account: MailAccount, fingerprint: str) -> str:
        return f"mail-control:telegram-alert:{account.id}:error:{fingerprint}"

    @staticmethod
    def _fingerprint(detail: str) -> str:
        normalized = _SPACE.sub(" ", detail.strip().casefold())
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]

    async def account_issue(self, account: MailAccount, detail: str) -> None:
        if not self.token or not self.chat_id:
            return
        fingerprint = self._fingerprint(detail)
        dedupe_key = self._dedupe_key(account, fingerprint)
        try:
            claimed = await self.redis.set(self._active_key(account), fingerprint, nx=True)
            if claimed:
                await self.redis.set(
                    dedupe_key,
                    "1",
                    ex=self.dedupe_seconds,
                    nx=True,
                )
        except RedisError as error:
            logger.warning("telegram_alert_dedupe_failed", error_type=type(error).__name__)
            return
        if not claimed:
            return
        provider = escape(account.provider.value.upper())
        message = (
            "🚨 <b>Mail Control requiere atención</b>\n"
            f"Cuenta: <code>{escape(account.email)}</code>\n"
            f"Proveedor: {provider}\n"
            f"Detalle: {escape(detail[:500])}"
        )
        if not await self._send(message):
            with suppress(RedisError):
                await self.redis.delete(dedupe_key, self._active_key(account))

    async def account_recovered(self, account: MailAccount) -> None:
        if not self.token or not self.chat_id:
            return
        try:
            fingerprint = await self.redis.getdel(self._active_key(account))
        except RedisError as error:
            logger.warning("telegram_recovery_dedupe_failed", error_type=type(error).__name__)
            return
        if not fingerprint:
            return
        with suppress(RedisError):
            await self.redis.delete(self._dedupe_key(account, str(fingerprint)))
        message = (
            "✅ <b>Cuenta de correo recuperada</b>\n"
            f"Cuenta: <code>{escape(account.email)}</code>\n"
            f"Proveedor: {escape(account.provider.value.upper())}"
        )
        await self._send(message)

    async def _send(self, text: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    f"https://api.telegram.org/bot{self.token}/sendMessage",
                    json={"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"},
                )
                response.raise_for_status()
            return True
        except httpx.HTTPError as error:
            logger.warning("telegram_alert_delivery_failed", error_type=type(error).__name__)
            return False
