from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import secrets
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from urllib.parse import quote, urlencode
from uuid import UUID

import httpx
from redis.asyncio import Redis

from mail_control.modules.mail.http import bounded_request

GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_API_URL = "https://gmail.googleapis.com/gmail/v1"


class GmailError(Exception):
    def __init__(
        self,
        message: str = "Gmail provider error",
        *,
        code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code


class GmailReauthRequired(GmailError):
    """Google rejected a refresh token and the user must authorize again."""


GmailReauthorizationRequired = GmailReauthRequired


class GmailHistoryExpired(GmailError):
    pass


class GmailMessageNotFound(GmailError):
    """A message disappeared after Gmail returned it in a list/history page."""


class GmailTransientError(GmailError):
    """Gmail stayed unavailable after bounded retries."""


@dataclass(frozen=True, slots=True)
class OAuthState:
    tenant_id: UUID
    user_id: UUID
    verifier: str
    target_account_id: UUID | None = None
    browser_nonce: str | None = None


@dataclass(frozen=True, slots=True)
class GoogleTokens:
    access_token: str
    refresh_token: str | None
    expires_at: datetime
    scopes: list[str]


class GmailOAuth:
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
        payload = json.dumps(
            {"tenant_id": str(tenant_id), "user_id": str(user_id), "verifier": verifier,
             "target_account_id": str(account_id) if account_id else None,
             "browser_nonce": browser_nonce}
        )
        await self.redis.setex(f"oauth:gmail:{state}", 600, payload)
        query = urlencode(
            {
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "response_type": "code",
                "scope": GMAIL_SCOPE,
                "access_type": "offline",
                "include_granted_scopes": "true",
                "prompt": "select_account consent",
                **({"login_hint": email_hint} if email_hint else {}),
                "state": state,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )
        return f"{GOOGLE_AUTH_URL}?{query}"

    async def consume_state(self, state: str) -> OAuthState:
        key = f"oauth:gmail:{state}"
        raw = await self.redis.getdel(key)
        if not raw:
            raise GmailError("invalid or expired OAuth state")
        data = json.loads(raw)
        return OAuthState(
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

    async def exchange_code(self, code: str, verifier: str) -> GoogleTokens:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": self.redirect_uri,
                    "grant_type": "authorization_code",
                    "code_verifier": verifier,
                },
            )
        if response.is_error:
            raise self._token_error(response, "authorization code")
        data = response.json()
        return GoogleTokens(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            expires_at=datetime.now(UTC) + timedelta(seconds=int(data["expires_in"])),
            scopes=data.get("scope", GMAIL_SCOPE).split(),
        )

    async def refresh_access_token(self, refresh_token: str) -> GoogleTokens:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "refresh_token": refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "refresh_token",
                },
            )
        if response.is_error:
            raise self._token_error(response, "refresh token")
        data = response.json()
        return GoogleTokens(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            expires_at=datetime.now(UTC) + timedelta(seconds=int(data["expires_in"])),
            scopes=data.get("scope", GMAIL_SCOPE).split(),
        )

    @staticmethod
    def _token_error(response: httpx.Response, operation: str) -> GmailError:
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        code = str(payload.get("error") or "oauth_error")
        description = str(payload.get("error_description") or "")
        message = f"Google rejected the {operation} ({code})"
        if description:
            message = f"{message}: {description[:240]}"
        if code == "invalid_grant":
            return GmailReauthRequired(message, code=code)
        return GmailError(message, code=code)


class GmailClient:
    def __init__(
        self, access_token: str, *,
        refresh_access_token: Callable[[str], Awaitable[str]] | None = None,
    ) -> None:
        self._headers = {"Authorization": f"Bearer {access_token}"}
        self._refresh_access_token = refresh_access_token

    async def profile(self) -> dict[str, Any]:
        return await self._get("/users/me/profile")

    async def watch(
        self,
        *,
        topic_name: str,
        label_ids: tuple[str, ...] = ("INBOX",),
        label_filter_behavior: str = "INCLUDE",
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "topicName": topic_name,
            "labelFilterBehavior": label_filter_behavior,
        }
        if label_ids:
            payload["labelIds"] = list(label_ids)
        return await self._post("/users/me/watch", json=payload)

    async def list_messages(
        self,
        *,
        page_token: str | None = None,
        max_results: int = 500,
    ) -> dict[str, Any]:
        params: dict[str, str | int] = {
            "maxResults": max_results, "includeSpamTrash": "true"
        }
        if page_token:
            params["pageToken"] = page_token
        return await self._get("/users/me/messages", params=params)

    async def get_message(self, message_id: str, *, full: bool = True) -> dict[str, Any]:
        try:
            return await self._get(
                f"/users/me/messages/{quote(message_id, safe='')}",
                params={"format": "full" if full else "minimal"},
            )
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 404:
                raise GmailMessageNotFound from error
            raise

    async def get_attachment(self, message_id: str, attachment_id: str) -> dict[str, Any]:
        return await self._get(
            f"/users/me/messages/{quote(message_id, safe='')}/attachments/"
            f"{quote(attachment_id, safe='')}"
        )

    async def attachment(self, message_id: str, attachment_id: str) -> dict[str, Any]:
        return await self.get_attachment(message_id, attachment_id)

    async def history(
        self,
        start_history_id: str,
        *,
        page_token: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, str | int] = {
            "startHistoryId": start_history_id,
            "maxResults": 500,
        }
        if page_token:
            params["pageToken"] = page_token
        try:
            return await self._get("/users/me/history", params=params)
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 404:
                raise GmailHistoryExpired from error
            raise

    async def _get(
        self,
        path: str,
        *,
        params: dict[str, str | int] | None = None,
    ) -> dict[str, Any]:
        return await self._request("GET", path, params=params)

    async def _post(
        self,
        path: str,
        *,
        json: dict[str, Any],
    ) -> dict[str, Any]:
        return await self._request("POST", path, json=json)

    async def _request(
        self, method: str, path: str, *,
        params: dict[str, str | int] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        # Share Graph's bounded Retry-After/jitter policy without retrying permanent 403s.
        from mail_control.modules.mail.microsoft import MicrosoftGraphClient

        last_error: Exception | None = None
        refreshed = False
        async with httpx.AsyncClient(base_url=GMAIL_API_URL, timeout=30) as client:
            attempt = 0
            while attempt < 4:
                try:
                    response = await bounded_request(
                        client, method, path, params=params, json=json, headers=self._headers
                    )
                except httpx.RequestError as error:
                    last_error = error
                else:
                    if response.status_code == 401 and self._refresh_access_token and not refreshed:
                        token = await self._refresh_access_token(
                            self._headers["Authorization"].removeprefix("Bearer ")
                        )
                        self._headers["Authorization"] = f"Bearer {token}"
                        refreshed = True
                        continue
                    limited = False
                    if response.status_code == 403:
                        try:
                            reasons = response.json().get("error", {}).get("errors", [])
                            limited = any(item.get("reason") in {
                                "rateLimitExceeded", "userRateLimitExceeded"
                            } for item in reasons)
                        except (ValueError, AttributeError):
                            pass
                    if response.status_code not in {429, 500, 502, 503, 504} and not limited:
                        response.raise_for_status()
                        return cast(dict[str, Any], response.json()) if response.content else {}
                    last_error = httpx.HTTPStatusError(
                        f"Gmail temporarily returned {response.status_code}",
                        request=response.request, response=response,
                    )
                attempt += 1
                if attempt >= 4:
                    break
                retry_after = (
                    last_error.response.headers.get("Retry-After")
                    if isinstance(last_error, httpx.HTTPStatusError) else None
                )
                delay = MicrosoftGraphClient._retry_delay(retry_after, attempt - 1)
                if delay > 30:
                    # Preserve a long provider cooldown without tying up a worker.
                    raise GmailTransientError(
                        "Gmail requested a longer retry cooldown"
                    ) from last_error
                await asyncio.sleep(delay)
        raise GmailTransientError("Gmail remained unavailable after 4 attempts") from last_error
