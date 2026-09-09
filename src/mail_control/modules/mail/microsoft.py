from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import random
import secrets
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any, cast
from urllib.parse import quote, urlencode, urlparse
from uuid import UUID

import httpx
from redis.asyncio import Redis
from redis.exceptions import RedisError

from mail_control.modules.mail.http import bounded_request

MICROSOFT_AUTH_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
MICROSOFT_TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
GRAPH_URL = "https://graph.microsoft.com/v1.0"
MICROSOFT_SCOPES = ("offline_access", "User.Read", "Mail.Read")
OAUTH_STATE_TTL_SECONDS = 3600
GRAPH_TRANSIENT_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
GRAPH_MAX_ATTEMPTS = 4
GRAPH_MAX_RETRY_DELAY_SECONDS = 30.0


class MicrosoftError(Exception):
    pass


class MicrosoftReauthorizationRequired(MicrosoftError):
    """The Microsoft grant was revoked or can no longer be refreshed."""


class MicrosoftDeltaExpired(MicrosoftError):
    pass


class MicrosoftTransientError(MicrosoftError):
    """Microsoft Graph stayed unavailable after bounded automatic retries."""


@dataclass(frozen=True, slots=True)
class MicrosoftOAuthState:
    tenant_id: UUID
    user_id: UUID
    verifier: str
    target_account_id: UUID | None = None
    browser_nonce: str | None = None


@dataclass(frozen=True, slots=True)
class MicrosoftTokens:
    access_token: str
    refresh_token: str | None
    expires_at: datetime
    scopes: list[str]


class MicrosoftOAuth:
    def __init__(
        self,
        redis: Redis,
        *,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
    ) -> None:
        self.redis = redis
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

    async def authorization_url(
        self, tenant_id: UUID, user_id: UUID, *, account_id: UUID | None = None,
        email_hint: str | None = None, browser_nonce: str | None = None,
    ) -> str:
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode("ascii")).digest()
        ).rstrip(b"=").decode("ascii")
        await self.redis.setex(
            f"oauth:microsoft:{state}",
            OAUTH_STATE_TTL_SECONDS,
            json.dumps(
                {
                    "tenant_id": str(tenant_id),
                    "user_id": str(user_id),
                    "verifier": verifier,
                    "target_account_id": str(account_id) if account_id else None,
                    "browser_nonce": browser_nonce,
                }
            ),
        )
        return f"{MICROSOFT_AUTH_URL}?{urlencode({
            'client_id': self.client_id,
            'response_type': 'code',
            'redirect_uri': self.redirect_uri,
            'response_mode': 'query',
            'prompt': 'select_account',
            'scope': ' '.join(MICROSOFT_SCOPES),
            **({'login_hint': email_hint} if email_hint else {}),
            'state': state,
            'code_challenge': challenge,
            'code_challenge_method': 'S256',
        })}"

    async def consume_state(self, state: str) -> MicrosoftOAuthState:
        raw = await self.redis.getdel(f"oauth:microsoft:{state}")
        if not raw:
            raise MicrosoftError("invalid or expired OAuth state")
        data = json.loads(raw)
        return MicrosoftOAuthState(
            tenant_id=UUID(data["tenant_id"]),
            user_id=UUID(data["user_id"]),
            verifier=data["verifier"],
            target_account_id=(
                UUID(data["target_account_id"])
                if data.get("target_account_id")
                else None
            ),
            browser_nonce=data.get("browser_nonce"),
        )

    async def exchange_code(self, code: str, verifier: str) -> MicrosoftTokens:
        return await self._token(
            {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "redirect_uri": self.redirect_uri,
                "grant_type": "authorization_code",
                "code_verifier": verifier,
                "scope": " ".join(MICROSOFT_SCOPES),
            }
        )

    async def refresh_access_token(self, refresh_token: str) -> MicrosoftTokens:
        return await self._token(
            {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
                "scope": " ".join(MICROSOFT_SCOPES),
            }
        )

    async def _token(self, data: dict[str, str]) -> MicrosoftTokens:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(MICROSOFT_TOKEN_URL, data=data)
        if response.is_error:
            try:
                error_payload = response.json()
            except ValueError:
                error_payload = {}
            error_name = str(error_payload.get("error", "oauth_error"))
            error_codes = error_payload.get("error_codes", [])
            aadsts_code = str(error_codes[0]) if error_codes else "unknown"
            error_class = (
                MicrosoftReauthorizationRequired
                if error_name == "invalid_grant"
                else MicrosoftError
            )
            raise error_class(
                "Microsoft rejected the OAuth token request "
                f"({error_name}, AADSTS{aadsts_code})"
            )
        payload = response.json()
        return MicrosoftTokens(
            access_token=payload["access_token"],
            refresh_token=payload.get("refresh_token"),
            expires_at=datetime.now(UTC) + timedelta(seconds=int(payload["expires_in"])),
            scopes=payload.get("scope", " ".join(MICROSOFT_SCOPES)).split(),
        )


class MicrosoftGraphClient:
    def __init__(
        self, access_token: str, *,
        refresh_access_token: Callable[[str], Awaitable[str]] | None = None,
        folder_cache: Redis | None = None,
        folder_cache_key: str | None = None,
    ) -> None:
        self._refresh_access_token = refresh_access_token
        self._folder_cache = folder_cache
        self._folder_cache_key = folder_cache_key
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Prefer": 'IdType="ImmutableId", odata.maxpagesize=100',
        }

    async def profile(self) -> dict[str, Any]:
        return await self.get("/me", params={"$select": "id,mail,userPrincipalName"})

    async def folders(self, next_link: str | None = None) -> dict[str, Any]:
        if next_link:
            return await self.get(next_link)
        return await self.get(
            "/me/mailFolders",
            params={"includeHiddenFolders": "true", "$top": 100},
        )

    async def folder_mailboxes(self) -> dict[str, str]:
        if self._folder_cache is not None and self._folder_cache_key:
            try:
                cached = await self._folder_cache.get(self._folder_cache_key)
                if cached:
                    data = json.loads(cached)
                    if isinstance(data, dict) and all(
                        isinstance(key, str) and isinstance(value, str)
                        for key, value in data.items()
                    ):
                        return cast(dict[str, str], data)
            except (RedisError, ValueError):
                pass
        result: dict[str, str] = {}
        for name, mailbox in (
            ("inbox", "inbox"), ("sentitems", "sent"), ("drafts", "drafts"),
            ("deleteditems", "trash"), ("junkemail", "spam"), ("archive", "archive"),
        ):
            try:
                folder = await self.get(f"/me/mailFolders/{name}", params={"$select": "id"})
            except httpx.HTTPStatusError as error:
                if error.response.status_code == 404:
                    continue
                raise
            result[str(folder["id"])] = mailbox
        if self._folder_cache is not None and self._folder_cache_key:
            with suppress(RedisError):
                await self._folder_cache.setex(self._folder_cache_key, 3600, json.dumps(result))
        return result

    async def get_message(self, message_id: str) -> dict[str, Any]:
        return await self.get(f"/me/messages/{quote(message_id, safe='')}")

    async def attachments(self, message_id: str, page_url: str | None = None) -> dict[str, Any]:
        return await self.get(
            page_url or f"/me/messages/{quote(message_id, safe='')}/attachments",
            params=None if page_url else {
                "$select": (
                    "id,name,contentType,size,isInline,"
                    "microsoft.graph.fileAttachment/contentId"
                ),
                "$top": 100,
            },
        )

    async def attachment(self, message_id: str, attachment_id: str) -> dict[str, Any]:
        return await self.get(
            f"/me/messages/{quote(message_id, safe='')}/attachments/{quote(attachment_id, safe='')}"
        )

    async def delta(self, folder_id: str, cursor: str | None = None) -> dict[str, Any]:
        url = cursor or f"/me/mailFolders/{folder_id}/messages/delta"
        params: dict[str, str | int] | None = None
        if cursor is None:
            params = {
                "$select": (
                    "id,conversationId,internetMessageId,subject,from,toRecipients,"
                    "ccRecipients,bccRecipients,receivedDateTime,bodyPreview,isRead,"
                    "body,parentFolderId,hasAttachments,flag,isDraft"
                )
            }
        try:
            return await self.get(url, params=params)
        except httpx.HTTPStatusError as error:
            if error.response.status_code in {404, 410}:
                raise MicrosoftDeltaExpired from error
            raise

    async def create_subscription(
        self,
        *,
        notification_url: str,
        lifecycle_url: str,
        resource: str,
        expiration_at: datetime,
        client_state: str,
    ) -> dict[str, Any]:
        return await self.post(
            "/subscriptions",
            json_data={
                "changeType": "created,updated,deleted",
                "notificationUrl": notification_url,
                "lifecycleNotificationUrl": lifecycle_url,
                "resource": resource,
                "expirationDateTime": expiration_at.isoformat().replace("+00:00", "Z"),
                "clientState": client_state,
            },
        )

    async def renew_subscription(
        self,
        subscription_id: str,
        *,
        expiration_at: datetime,
    ) -> dict[str, Any]:
        return await self.patch(
            f"/subscriptions/{subscription_id}",
            json_data={
                "expirationDateTime": expiration_at.isoformat().replace("+00:00", "Z")
            },
        )

    async def reauthorize_subscription(self, subscription_id: str) -> None:
        await self.post(f"/subscriptions/{subscription_id}/reauthorize", json_data={})

    async def get(
        self,
        path_or_url: str,
        *,
        params: dict[str, str | int] | None = None,
    ) -> dict[str, Any]:
        return await self.request("GET", path_or_url, params=params)

    async def post(
        self,
        path_or_url: str,
        *,
        json_data: dict[str, Any],
    ) -> dict[str, Any]:
        return await self.request("POST", path_or_url, json_data=json_data)

    async def patch(
        self,
        path_or_url: str,
        *,
        json_data: dict[str, Any],
    ) -> dict[str, Any]:
        return await self.request("PATCH", path_or_url, json_data=json_data)

    async def request(
        self,
        method: str,
        path_or_url: str,
        *,
        params: dict[str, str | int] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        parsed = urlparse(path_or_url)
        if parsed.netloc and (parsed.scheme != "https" or parsed.netloc != "graph.microsoft.com"):
            raise MicrosoftError("Refusing a Graph continuation outside the provider origin")
        last_error: Exception | None = None
        refreshed = False
        async with httpx.AsyncClient(
            base_url=GRAPH_URL,
            headers=self.headers,
            timeout=30,
        ) as client:
            for attempt in range(GRAPH_MAX_ATTEMPTS):
                try:
                    response = await bounded_request(
                        client, method,
                        path_or_url,
                        params=params,
                        json=json_data,
                        headers=self.headers,
                    )
                except httpx.RequestError as error:
                    last_error = error
                else:
                    if response.status_code == 401 and self._refresh_access_token and not refreshed:
                        token = await self._refresh_access_token(
                            self.headers["Authorization"].removeprefix("Bearer ")
                        )
                        self.headers["Authorization"] = f"Bearer {token}"
                        refreshed = True
                        response = await bounded_request(
                            client,
                            method,
                            path_or_url,
                            params=params,
                            json=json_data,
                            headers=self.headers,
                        )
                    if response.status_code not in GRAPH_TRANSIENT_STATUS_CODES:
                        response.raise_for_status()
                        if not response.content:
                            return {}
                        return cast(dict[str, Any], response.json())
                    last_error = httpx.HTTPStatusError(
                        f"Microsoft Graph temporarily returned {response.status_code}",
                        request=response.request,
                        response=response,
                    )

                if attempt + 1 == GRAPH_MAX_ATTEMPTS:
                    break
                retry_after = None
                if isinstance(last_error, httpx.HTTPStatusError):
                    retry_after = last_error.response.headers.get("Retry-After")
                delay = self._retry_delay(retry_after, attempt)
                if delay > GRAPH_MAX_RETRY_DELAY_SECONDS:
                    raise MicrosoftTransientError(
                        "Microsoft Graph requested a longer retry cooldown"
                    ) from last_error
                await asyncio.sleep(delay)

        raise MicrosoftTransientError(
            f"Microsoft Graph remained unavailable after {GRAPH_MAX_ATTEMPTS} attempts"
        ) from last_error

    @staticmethod
    def _retry_delay(retry_after: str | None, attempt: int) -> float:
        delay: float | None = None
        if retry_after:
            try:
                delay = float(retry_after)
            except ValueError:
                try:
                    retry_at = parsedate_to_datetime(retry_after)
                    if retry_at.tzinfo is None:
                        retry_at = retry_at.replace(tzinfo=UTC)
                    delay = (retry_at - datetime.now(UTC)).total_seconds()
                except (TypeError, ValueError, OverflowError):
                    delay = None
            if delay is not None:
                return max(delay, 0.0)
        ceiling = min(2**attempt, GRAPH_MAX_RETRY_DELAY_SECONDS)
        return random.uniform(0.0, ceiling)
