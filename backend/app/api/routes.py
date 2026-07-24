"""Rutas de la API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from ..core import crypto
from ..core.db import get_db
from ..core.security import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from ..models.models import Alert, MailAccount, Message, User
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
    Token,
    UserOut,
)
from ..services import imap_service

router = APIRouter(prefix="/api")

IMAP_PRESETS = {
    "outlook": ("outlook.office365.com", 993),
    "hotmail": ("outlook.office365.com", 993),
    "gmail": ("imap.gmail.com", 993),
}


# --- Auth ---
@router.post("/auth/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form.username, User.is_active.is_(True)).first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    return Token(access_token=create_access_token(user.email))


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

    acct = MailAccount(
        email=data.email,
        provider=data.provider.lower(),
        imap_host=host,
        imap_port=port,
        imap_user=data.imap_user or data.email,
        encrypted_password=crypto.encrypt(
            imap_service.normalize_app_password(
                data.password, data.imap_user or data.email, host
            )
        ),
    )
    db.add(acct)
    db.commit()
    db.refresh(acct)
    
    # Dispara sincronización automática inmediatamente
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
    if data.password:
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
