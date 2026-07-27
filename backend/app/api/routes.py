"""Rutas de la API."""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from ..core import crypto
from ..core.config import settings
from ..core.db import get_db
from ..core.login_limiter import clear_failures, is_blocked, register_failure
from ..core.security import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from ..models.models import Alert, MailAccount, Message, Subscription, User
from ..schemas.schemas import (
    AlertOut,
    ChangePasswordIn,
    MailAccountIn,
    MailAccountOut,
    MailAccountUpdate,
    MessageDetail,
    PaginatedAlerts,
    PaginatedMessages,
    StatsOut,
    SubscriptionDetail,
    SubscriptionOut,
    SubscriptionStatsOut,
    UserOut,
)
from ..services import imap_service, microsoft_auth

router = APIRouter(prefix="/api")

IMAP_PRESETS = {
    "outlook": ("outlook.office365.com", 993),
    "hotmail": ("outlook.office365.com", 993),
    "gmail": ("imap.gmail.com", 993),
}


# --- Auth ---
@router.post("/auth/login")
def login(
    request: Request,
    response: Response,
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    # El primer valor de X-Forwarded-For es la IP real del cliente
    # (los proxies intermedios pisan X-Real-IP con su propia IP).
    fwd = request.headers.get("x-forwarded-for", "")
    ip = (
        (fwd.split(",")[0].strip() if fwd else None)
        or request.headers.get("x-real-ip")
        or (request.client.host if request.client else None)
        or "unknown"
    )
    if is_blocked(ip, form.username):
        raise HTTPException(
            status_code=429,
            detail="Demasiados intentos. Intenta nuevamente en 15 minutos.",
        )
    user = db.query(User).filter(User.email == form.username, User.is_active.is_(True)).first()
    if not user or not verify_password(form.password, user.hashed_password):
        attempts = register_failure(ip, form.username)
        if attempts >= settings.LOGIN_MAX_FAILURES:
            raise HTTPException(
                status_code=429,
                detail="IP bloqueada durante 15 minutos.",
            )
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    clear_failures(ip, form.username)
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=create_access_token(user.email),
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite="strict",
        path="/",
    )
    return {"ok": True}


@router.post("/auth/logout")
def logout(response: Response):
    response.delete_cookie(
        settings.SESSION_COOKIE_NAME,
        path="/",
        secure=settings.SESSION_COOKIE_SECURE,
        httponly=True,
        samesite="strict",
    )
    return {"ok": True}


@router.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/change-password")
def change_password(
    data: ChangePasswordIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(data.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="La contraseña actual es incorrecta")
    if data.current_password == data.new_password:
        raise HTTPException(
            status_code=400, detail="La nueva contraseña debe ser distinta a la actual"
        )
    user.hashed_password = hash_password(data.new_password)
    db.commit()
    return {"ok": True}


# --- Cuentas de correo ---
@router.get("/accounts", response_model=list[MailAccountOut])
def list_accounts(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return db.query(MailAccount).order_by(MailAccount.email).all()


@router.post("/accounts", response_model=MailAccountOut, status_code=201)
def create_account(
    data: MailAccountIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if db.query(MailAccount).filter(MailAccount.email == data.email).first():
        raise HTTPException(status_code=409, detail="Esa casilla ya existe")

    host, port = data.imap_host, data.imap_port
    preset = IMAP_PRESETS.get(data.provider.lower())
    if preset and not host:
        host, port = preset

    is_microsoft = imap_service.is_microsoft_account(
        data.imap_user or data.email, host
    )
    if not is_microsoft and not data.password:
        raise HTTPException(
            status_code=422,
            detail="La contraseña es obligatoria para proveedores personalizados",
        )
    encrypted_password = crypto.encrypt(data.password) if data.password and not is_microsoft else ""

    acct = MailAccount(
        email=data.email,
        provider=data.provider.lower(),
        imap_host=host,
        imap_port=port,
        imap_user=data.imap_user or data.email,
        encrypted_password=encrypted_password,
        auth_method="oauth2" if is_microsoft else "password",
    )
    db.add(acct)
    db.commit()
    db.refresh(acct)
    
    # Dispara sincronización automática inmediatamente
    if not is_microsoft:
        from ..workers.tasks import scan_account_chunk
        scan_account_chunk.delay([acct.id])
    
    return acct


@router.patch("/accounts/{account_id}", response_model=MailAccountOut)
def update_account(
    account_id: int,
    data: MailAccountUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    acct = db.get(MailAccount, account_id)
    if not acct:
        raise HTTPException(status_code=404, detail="Casilla no encontrada")
    if data.imap_host is not None:
        acct.imap_host = data.imap_host
    if data.imap_port is not None:
        acct.imap_port = data.imap_port
    if data.imap_user is not None:
        acct.imap_user = data.imap_user
    if data.password and acct.auth_method != "oauth2":
        acct.encrypted_password = crypto.encrypt(
            imap_service.normalize_app_password(
                data.password, acct.imap_user or acct.email, acct.imap_host
            )
        )
    if data.is_enabled is not None:
        acct.is_enabled = data.is_enabled
    db.commit()
    db.refresh(acct)
    return acct


@router.post("/accounts/{account_id}/microsoft/authorize")
def authorize_microsoft_account(
    account_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    acct = db.get(MailAccount, account_id)
    if not acct:
        raise HTTPException(status_code=404, detail="Casilla no encontrada")
    if not imap_service.is_microsoft_account(acct.imap_user, acct.imap_host):
        raise HTTPException(status_code=400, detail="La casilla no es de Microsoft")
    try:
        return {
            "authorization_url": microsoft_auth.create_authorization_url(
                acct.id, acct.imap_user or acct.email
            )
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/microsoft/callback")
def microsoft_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    db: Session = Depends(get_db),
):
    redirect_base = settings.FRONTEND_URL.rstrip("/") + "/cuentas"
    if error:
        detail = error_description or error
        return RedirectResponse(f"{redirect_base}?oauth=error&detail={quote(detail)}")
    try:
        if not code or not state:
            raise ValueError("Microsoft no devolvió code/state")
        account_id = microsoft_auth.account_id_from_state(state)
        acct = db.get(MailAccount, account_id)
        if not acct:
            raise ValueError("La casilla ya no existe")
        serialized_cache, authorized_username = (
            microsoft_auth.redeem_authorization_code(code)
        )
        if (
            authorized_username
            and authorized_username.casefold() != acct.email.casefold()
        ):
            raise ValueError(
                f"Autorizaste {authorized_username}, pero la casilla es {acct.email}"
            )
        acct.encrypted_oauth_cache = crypto.encrypt(serialized_cache)
        acct.encrypted_password = ""
        acct.auth_method = "oauth2"
        acct.last_status = "pending"
        acct.last_error = ""
        db.commit()
        from ..workers.tasks import scan_account_chunk
        scan_account_chunk.delay([acct.id])
        return RedirectResponse(f"{redirect_base}?oauth=connected")
    except Exception as exc:
        db.rollback()
        return RedirectResponse(
            f"{redirect_base}?oauth=error&detail={quote(str(exc))}"
        )


@router.delete("/accounts/{account_id}", status_code=204)
def delete_account(
    account_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    acct = db.get(MailAccount, account_id)
    if not acct:
        raise HTTPException(status_code=404, detail="Casilla no encontrada")
    db.delete(acct)
    db.commit()


@router.post("/accounts/{account_id}/test")
def test_account(
    account_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    acct = db.get(MailAccount, account_id)
    if not acct:
        raise HTTPException(status_code=404, detail="Casilla no encontrada")
    try:
        if imap_service.is_microsoft_account(acct.imap_user, acct.imap_host):
            if not imap_service.prepare_microsoft_oauth(acct):
                raise RuntimeError("Primero debes autorizar la cuenta con Microsoft")
            db.commit()
            imap_service.test_connection(acct)
            return {"ok": True}
        imap_service.test_connection(
            acct.imap_host,
            acct.imap_port,
            acct.imap_user or acct.email,
            crypto.decrypt(acct.encrypted_password),
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Conexión falló: {exc}")
    return {"ok": True}


@router.post("/accounts/{account_id}/sync")
def sync_account_now(
    account_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not db.get(MailAccount, account_id):
        raise HTTPException(status_code=404, detail="Casilla no encontrada")
    from ..workers.tasks import scan_account_chunk

    scan_account_chunk.delay([account_id])
    return {"queued": True}


# --- Mensajes (visor masivo) ---
@router.get("/messages", response_model=PaginatedMessages)
def list_messages(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    account_id: int | None = None,
    q: str | None = None,
    only_alerts: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Message)
    if account_id:
        query = query.filter(Message.account_id == account_id)
    if only_alerts:
        query = query.filter(Message.is_alert.is_(True))
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                Message.subject.ilike(like),
                Message.from_addr.ilike(like),
                Message.from_name.ilike(like),
            )
        )
    total = query.count()
    items = (
        query.order_by(Message.received_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PaginatedMessages(total=total, page=page, page_size=page_size, items=items)


@router.get("/messages/{message_id}", response_model=MessageDetail)
def get_message(
    message_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    msg = db.get(Message, message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Correo no encontrado")
    return msg


# --- Alertas críticas ---
@router.get("/alerts", response_model=PaginatedAlerts)
def list_alerts(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    include_resolved: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Alert).options(joinedload(Alert.message))
    if not include_resolved:
        query = query.filter(Alert.resolved.is_(False))
    total = query.count()
    items = (
        query.order_by(Alert.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PaginatedAlerts(total=total, page=page, page_size=page_size, items=items)


@router.post("/alerts/{alert_id}/resolve")
def resolve_alert(
    alert_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
    alert.resolved = True
    db.commit()
    return {"ok": True}


# --- Estado consolidado de suscripciones ---
def _subscription_out(item: Subscription) -> dict:
    return {
        "id": item.id,
        "account_id": item.account_id,
        "account_email": item.account.email,
        "service": item.service,
        "status": item.status,
        "severity": item.severity,
        "reason": item.reason,
        "score": item.score,
        "latest_message_id": item.latest_message_id,
        "detected_at": item.detected_at,
        "updated_at": item.updated_at,
    }


@router.get("/subscriptions", response_model=list[SubscriptionOut])
def list_subscriptions(
    account_id: int | None = None,
    status: str | None = None,
    service: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Subscription).options(joinedload(Subscription.account))
    if account_id:
        query = query.filter(Subscription.account_id == account_id)
    if status:
        query = query.filter(Subscription.status == status)
    if service:
        query = query.filter(Subscription.service == service)
    return [
        _subscription_out(item)
        for item in query.order_by(Subscription.updated_at.desc()).all()
    ]


@router.get("/subscriptions/stats", response_model=SubscriptionStatsOut)
def subscription_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    counts = dict(
        db.query(Subscription.status, func.count(Subscription.id))
        .group_by(Subscription.status)
        .all()
    )
    return SubscriptionStatsOut(
        total=sum(counts.values()),
        active=counts.get("active", 0),
        warning=counts.get("warning", 0),
        payment_failed=counts.get("payment_failed", 0),
        suspended=counts.get("suspended", 0),
        cancelled=counts.get("cancelled", 0),
    )


@router.get("/subscriptions/{subscription_id}", response_model=SubscriptionDetail)
def get_subscription(
    subscription_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = (
        db.query(Subscription)
        .options(joinedload(Subscription.account), joinedload(Subscription.events))
        .filter(Subscription.id == subscription_id)
        .one_or_none()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Suscripción no encontrada")
    return {**_subscription_out(item), "events": item.events}


@router.post("/subscriptions/rebuild")
def rebuild_subscriptions(
    user: User = Depends(get_current_user),
):
    from ..workers.tasks import rebuild_subscription_states

    task = rebuild_subscription_states.delay()
    return {"queued": True, "task_id": task.id}


# --- Stats del dashboard ---
@router.get("/stats", response_model=StatsOut)
def stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    accounts_total = db.scalar(select(func.count(MailAccount.id))) or 0
    accounts_ok = db.scalar(
        select(func.count(MailAccount.id)).where(MailAccount.last_status == "ok")
    ) or 0
    accounts_error = db.scalar(
        select(func.count(MailAccount.id)).where(MailAccount.last_status == "error")
    ) or 0
    messages_total = db.scalar(select(func.count(Message.id))) or 0
    alerts_open = db.scalar(
        select(func.count(Alert.id)).where(Alert.resolved.is_(False))
    ) or 0
    return StatsOut(
        accounts_total=accounts_total,
        accounts_ok=accounts_ok,
        accounts_error=accounts_error,
        messages_total=messages_total,
        alerts_open=alerts_open,
    )
