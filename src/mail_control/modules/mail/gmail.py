from __future__ import annotations

import base64
import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from urllib.parse import urlencode
from uuid import UUID

import httpx
from redis.asyncio import Redis

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


@dataclass(frozen=True, slots=True)
class OAuthState:
    tenant_id: UUID
    user_id: UUID
    verifier: str


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

    async def authorization_url(self, tenant_id: UUID, user_id: UUID) -> str:
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode("ascii")).digest()
        ).rstrip(b"=").decode("ascii")
        payload = json.dumps(
            {"tenant_id": str(tenant_id), "user_id": str(user_id), "verifier": verifier}
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
                "prompt": "consent",
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
    def __init__(self, access_token: str) -> None:
        self._headers = {"Authorization": f"Bearer {access_token}"}

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
        params: dict[str, str | int] = {"maxResults": max_results}
        if page_token:
            params["pageToken"] = page_token
        return await self._get("/users/me/messages", params=params)

    async def get_message(self, message_id: str, *, full: bool = True) -> dict[str, Any]:
        try:
            return await self._get(
                f"/users/me/messages/{message_id}",
                params={"format": "full" if full else "minimal"},
            )
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 404:
                raise GmailMessageNotFound from error
            raise

    async def history(
        self,
        start_history_id: str,
        *,
        page_token: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, str | int] = {
            "startHistoryId": start_history_id,
            "maxResults": 500,
            "historyTypes": "messageAdded",
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
        async with httpx.AsyncClient(
            base_url=GMAIL_API_URL,
            headers=self._headers,
            timeout=30,
        ) as client:
            response = await client.get(path, params=params)
            response.raise_for_status()
            return cast(dict[str, Any], response.json())

    async def _post(
        self,
        path: str,
        *,
        json: dict[str, Any],
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(
            base_url=GMAIL_API_URL,
            headers=self._headers,
            timeout=30,
        ) as client:
            response = await client.post(path, json=json)
            response.raise_for_status()
            return cast(dict[str, Any], response.json())
