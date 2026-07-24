"""Microsoft OAuth2 token acquisition and renewal using MSAL."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import msal
from jose import JWTError, jwt

from ..core.config import settings

IMAP_SCOPES = ["https://outlook.office.com/IMAP.AccessAsUser.All"]
_STATE_ALGORITHM = "HS256"


def _validate_config() -> None:
    missing = [
        name
        for name in (
            "MICROSOFT_CLIENT_ID",
            "MICROSOFT_CLIENT_SECRET",
            "MICROSOFT_REDIRECT_URI",
        )
        if not getattr(settings, name)
    ]
    if missing:
        raise RuntimeError(
            "Falta configurar Microsoft OAuth2: " + ", ".join(missing)
        )


def _client(cache: msal.SerializableTokenCache | None = None):
    _validate_config()
    authority = (
        "https://login.microsoftonline.com/"
        f"{settings.MICROSOFT_TENANT_ID}"
    )
    return msal.ConfidentialClientApplication(
        settings.MICROSOFT_CLIENT_ID,
        authority=authority,
        client_credential=settings.MICROSOFT_CLIENT_SECRET,
        token_cache=cache,
    )


def create_authorization_url(account_id: int, login_hint: str) -> str:
    now = datetime.now(timezone.utc)
    state = jwt.encode(
        {
            "purpose": "microsoft_oauth",
            "account_id": account_id,
            "iat": now,
            "exp": now + timedelta(minutes=10),
        },
        settings.SECRET_KEY,
        algorithm=_STATE_ALGORITHM,
    )
    return _client().get_authorization_request_url(
        scopes=IMAP_SCOPES,
        redirect_uri=settings.MICROSOFT_REDIRECT_URI,
        state=state,
        login_hint=login_hint,
        prompt="select_account",
    )


def account_id_from_state(state: str) -> int:
    try:
        payload = jwt.decode(
            state,
            settings.SECRET_KEY,
            algorithms=[_STATE_ALGORITHM],
        )
        if payload.get("purpose") != "microsoft_oauth":
            raise ValueError
        return int(payload["account_id"])
    except (JWTError, KeyError, TypeError, ValueError) as exc:
        raise ValueError("Estado OAuth inválido o expirado") from exc


def redeem_authorization_code(code: str) -> tuple[str, str]:
    cache = msal.SerializableTokenCache()
    result = _client(cache).acquire_token_by_authorization_code(
        code,
        scopes=IMAP_SCOPES,
        redirect_uri=settings.MICROSOFT_REDIRECT_URI,
    )
    if "access_token" not in result:
        detail = result.get("error_description") or result.get("error") or "Error OAuth"
        raise RuntimeError(f"Microsoft rechazó la autorización: {detail}")
    username = (
        result.get("id_token_claims", {}).get("preferred_username")
        or result.get("id_token_claims", {}).get("email")
        or ""
    )
    return cache.serialize(), username


def acquire_access_token(serialized_cache: str, username: str) -> tuple[str, str]:
    cache = msal.SerializableTokenCache()
    cache.deserialize(serialized_cache)
    app = _client(cache)
    accounts = app.get_accounts(username=username) or app.get_accounts()
    if not accounts:
        raise RuntimeError("La sesión Microsoft no está vinculada; vuelve a autorizarla")
    result = app.acquire_token_silent(IMAP_SCOPES, account=accounts[0])
    if not result or "access_token" not in result:
        detail = (result or {}).get("error_description", "se requiere autorización")
        raise RuntimeError(f"No se pudo renovar el token Microsoft: {detail}")
    return result["access_token"], cache.serialize()
