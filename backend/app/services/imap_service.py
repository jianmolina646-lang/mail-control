from __future__ import annotations
import email
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime
from datetime import datetime, timezone
import json
import ssl
import time
import urllib.parse
import urllib.request
from bs4 import BeautifulSoup
from imapclient import IMAPClient
from imapclient.exceptions import LoginError
from ..core.config import settings
# Servidor oficial recomendado por Microsoft para IMAP
MICROSOFT_IMAP_HOST = "outlook.office365.com"
MICROSOFT_DOMAINS = ("@outlook.", "@hotmail.", "@live.", "@msn.")
def normalize_imap_host(host: str) -> str:
    """Normaliza el host IMAP. Reemplaza servidores obsoletos de Microsoft por outlook.office365.com."""
    if not host:
        return MICROSOFT_IMAP_HOST
    h = host.lower().strip()
    if h in ("imap-mail.outlook.com", "imap.live.com", "outlook.com", "hotmail.com"):
        return MICROSOFT_IMAP_HOST
    return host
def is_microsoft_account(username: str, host: str) -> bool:
    """Detecta si la cuenta pertenece al ecosistema Microsoft (Outlook/Hotmail/Office365)."""
    user_lower = (username or "").lower()
    host_lower = (host or "").lower()
    if MICROSOFT_IMAP_HOST in host_lower or "outlook" in host_lower or "office365" in host_lower:
        return True
    return any(domain in user_lower for domain in MICROSOFT_DOMAINS)
def refresh_ms_oauth2_token(
    client_id: str,
    refresh_token: str,
    client_secret: str | None = None,
    tenant: str = "common",
) -> str:
    """Obtiene un nuevo Access Token de Microsoft mediante OAuth 2.0 (Refresh Token).
    Requerido para cuentas @outlook.com / @hotmail.com / Office365 tras la desactivación
    definitiva de Basic Auth y Contraseñas de Aplicación por parte de Microsoft en sep 2024.
    """
    token_url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
    payload = {
        "client_id": client_id,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "scope": "https://outlook.office.com/IMAP.AccessAsUser.All offline_access",
    }
    if client_secret:
        payload["client_secret"] = client_secret
    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(
        token_url,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        res_json = json.loads(resp.read().decode("utf-8"))
        return res_json["access_token"]
def obtain_ms_device_code_token(client_id: str, tenant: str = "common") -> dict[str, str]:
    """Inicia el flujo de código de dispositivo (Device Code Flow) para autenticar una cuenta
    de Hotmail / Outlook personal o empresarial de forma interactiva en la terminal.
    Retorna un diccionario con {"access_token": ..., "refresh_token": ...}.
    """
    device_code_url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/devicecode"
    token_url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
    payload = {
        "client_id": client_id,
        "scope": "https://outlook.office.com/IMAP.AccessAsUser.All offline_access",
    }
    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(device_code_url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        code_res = json.loads(resp.read().decode("utf-8"))
    user_code = code_res["user_code"]
    verification_uri = code_res.get("verification_uri", "https://microsoft.com/devicelogin")
    device_code = code_res["device_code"]
    interval = code_res.get("interval", 5)
    print(f"\n=======================================================")
    print(f" AUTENTICACIÓN OAUTH2 MICROSOFT REQUERIDA ")
    print(f"=======================================================")
    print(f"1. Abre en tu navegador: {verification_uri}")
    print(f"2. Ingresa el código:    {user_code}")
    print(f"=======================================================\n")
    poll_payload = {
        "client_id": client_id,
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        "device_code": device_code,
    }
    while True:
        time.sleep(interval)
        poll_data = urllib.parse.urlencode(poll_payload).encode("utf-8")
        poll_req = urllib.request.Request(token_url, data=poll_data, headers={"Content-Type": "application/x-www-form-urlencoded"})
        try:
            with urllib.request.urlopen(poll_req, timeout=15) as token_resp:
                res_json = json.loads(token_resp.read().decode("utf-8"))
                print("¡Autenticación OAuth2 completada exitosamente!")
                return res_json
        except urllib.error.HTTPError as err:
            err_json = json.loads(err.read().decode("utf-8"))
            error_code = err_json.get("error")
            if error_code == "authorization_pending":
                continue
            elif error_code == "slow_down":
                interval += 5
                continue
            else:
                raise RuntimeError(f"Error durante autenticación OAuth2: {err_json.get('error_description')}") from err
def _decode(value) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return str(value)
def _html_to_text(html: str) -> str:
    if not html:
        return ""
    try:
        return BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    except Exception:
        try:
            return BeautifulSoup(html, "lxml").get_text(" ", strip=True)
        except Exception:
            return ""
def _payload(part) -> str:
    try:
        raw = part.get_payload(decode=True)
        if raw is None:
            return ""
        charset = part.get_content_charset() or "utf-8"
        return raw.decode(charset, errors="replace")
    except Exception:
        return ""
def _extract_bodies(msg: email.message.Message) -> tuple[str, str]:
    """Devuelve (texto_plano, html). Acota el tamaño para no reventar RAM."""
    text_parts: list[str] = []
    html_parts: list[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            if part.is_multipart():
                continue
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition") or "")
            if "attachment" in disp:
                continue
            if ctype == "text/plain":
                text_parts.append(_payload(part))
            elif ctype == "text/html":
                html_parts.append(_payload(part))
    else:
        if msg.get_content_type() == "text/html":
            html_parts.append(_payload(msg))
        else:
            text_parts.append(_payload(msg))
    html = "\n".join(p for p in html_parts if p)[:200_000]
    text = "\n".join(p for p in text_parts if p)
    if not text and html:
        text = _html_to_text(html)
    return text[:100_000], html
class ParsedMessage:
    __slots__ = (
        "uid", "message_id", "from_addr", "from_name", "to_addr",
        "subject", "snippet", "body_text", "body_html", "received_at",
    )
    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))
def get_imap_username(account) -> str:
    """Asegura devolver el correo completo requerido por servidores como Outlook.com."""
    user = getattr(account, "imap_user", None) or getattr(account, "email", "")
    if "@" not in user and hasattr(account, "email") and "@" in account.email:
        return account.email
    return user
def _login_server(server: IMAPClient, username: str, password: str, account=None, host: str = ""):
    """Realiza el inicio de sesión IMAP soportando OAuth2 y Basic Auth, con diagnóstico de errores de Microsoft."""
    # 1. Token OAuth2 directo en el objeto cuenta
    oauth_token = getattr(account, "oauth_token", None) if account else None
    # 2. Si la cuenta tiene un método dinámico para refrescar/obtener el token
    if not oauth_token and account and hasattr(account, "get_oauth_token") and callable(account.get_oauth_token):
        try:
            oauth_token = account.get_oauth_token()
        except Exception:
            pass
    # 3. Intentar refrescar token si hay refresh token disponible
    if not oauth_token and account:
        rf_token = getattr(account, "oauth_refresh_token", None)
        client_id = getattr(account, "oauth_client_id", None)
        if rf_token and client_id:
            try:
                client_secret = getattr(account, "oauth_client_secret", None)
                tenant = getattr(account, "oauth_tenant", "common")
                oauth_token = refresh_ms_oauth2_token(client_id, rf_token, client_secret=client_secret, tenant=tenant)
            except Exception:
                pass
    if oauth_token:
        server.oauth2_login(username, oauth_token)
        return
    # 4. Intentar login básico
    try:
        server.login(username, password)
    except (LoginError, Exception) as exc:
        err_msg = str(exc)
        if "AUTHENTICATE failed" in err_msg or "Logon failure" in err_msg:
            if is_microsoft_account(username, host):
                raise RuntimeError(
                    f"Error de autenticación IMAP en Microsoft para '{username}': {err_msg}\n"
                    "Causa: Desde septiembre de 2024, Microsoft desactivó definitivamente la autenticación básica "
                    "(usuario/contraseña y contraseñas de aplicación) para cuentas personales (@hotmail.com, @outlook.com, @live.com).\n"
                    "Solución: Debe utilizarse autenticación OAuth 2.0 (XOAUTH2).\n"
                    "Puedes usar la función 'obtain_ms_device_code_token(client_id)' de imap.py para obtener los tokens de tu cuenta fácilmente."
                ) from exc
        raise
def fetch_recent(account, limit: int | None = None) -> list[ParsedMessage]:
    """Trae los últimos limit correos de la casilla. Abre y cierra la conexión.
    account debe exponer imap_host, imap_port, imap_user, email y una property
    password ya desencriptada. También puede exponer oauth_token u oauth_refresh_token.
    """
    limit = limit or getattr(settings, "IMAP_FETCH_LIMIT", 10)
    timeout = getattr(settings, "IMAP_TIMEOUT", 30)
    results: list[ParsedMessage] = []
    username = get_imap_username(account)
    raw_host = getattr(account, "imap_host", MICROSOFT_IMAP_HOST)
    host = normalize_imap_host(raw_host)
    port = getattr(account, "imap_port", None) or 993
    ssl_context = ssl.create_default_context()
    with IMAPClient(
        host=host,
        port=port,
        use_uid=True,
        ssl=True,
        ssl_context=ssl_context,
        timeout=timeout,
    ) as server:
        _login_server(server, username, getattr(account, "password", ""), account=account, host=host)
        server.select_folder("INBOX", readonly=True)
        uids = server.search(["ALL"])
        if not uids:
            return results
        uids = sorted(uids)[-limit:]
        response = server.fetch(uids, ["BODY.PEEK[]", "INTERNALDATE"])
        for uid, data in response.items():
            raw = (
                data.get(b"BODY.PEEK[]")
                or data.get("BODY.PEEK[]")
                or data.get(b"RFC822")
                or data.get("RFC822")
            )
            if not raw:
                continue
            msg = email.message_from_bytes(raw)
            name, addr = parseaddr(msg.get("From", ""))
            _, to_addr = parseaddr(msg.get("To", ""))
            subject = _decode(msg.get("Subject", ""))
            body_text, body_html = _extract_bodies(msg)
            received = data.get(b"INTERNALDATE") or data.get("INTERNALDATE")
            if received is None:
                try:
                    received = parsedate_to_datetime(msg.get("Date"))
                except Exception:
                    received = datetime.now(timezone.utc)
            elif isinstance(received, str):
                try:
                    received = parsedate_to_datetime(received)
                except Exception:
                    received = datetime.now(timezone.utc)
            if received.tzinfo is None:
                received = received.replace(tzinfo=timezone.utc)
            results.append(
                ParsedMessage(
                    uid=str(uid),
                    message_id=(msg.get("Message-ID") or "")[:512],
                    from_addr=addr[:512],
                    from_name=_decode(name)[:255],
                    to_addr=to_addr[:512],
                    subject=subject[:1000],
                    snippet=(body_text or "").strip().replace("\n", " ")[:300],
                    body_text=body_text,
                    body_html=body_html,
                    received_at=received,
                )
            )
    return results
def test_connection(host_or_account, port: int | None = None, user: str | None = None, password: str | None = None) -> None:
    """Valida credenciales IMAP. Acepta (host, port, user, password) o un objeto account."""
    if isinstance(host_or_account, str):
        host = normalize_imap_host(host_or_account)
        port = port or 993
        username = user or ""
        pwd = password or ""
        account = None
    else:
        account = host_or_account
        raw_host = getattr(account, "imap_host", MICROSOFT_IMAP_HOST)
        host = normalize_imap_host(raw_host)
        port = getattr(account, "imap_port", None) or 993
        username = get_imap_username(account)
        pwd = getattr(account, "password", "")
    timeout = getattr(settings, "IMAP_TIMEOUT", 30)
    ssl_context = ssl.create_default_context()
    with IMAPClient(
        host=host,
        port=port,
        use_uid=True,
        ssl=True,
        ssl_context=ssl_context,
        timeout=timeout,
    ) as server:
        _login_server(server, username, pwd, account=account, host=host)
        server.select_folder("INBOX", readonly=True)
