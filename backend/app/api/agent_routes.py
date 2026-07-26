"""API privada y mínima para el agente de automatización."""

from __future__ import annotations

import hmac
from datetime import datetime

import redis
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.db import get_db
from ..models.models import MailAccount
from ..services.agent_codes import claim_recent_code

router = APIRouter(prefix="/api/internal/agent", tags=["internal-agent"])
_redis = redis.Redis.from_url(settings.REDIS_URL)


class CodeRequest(BaseModel):
    job_id: str = Field(min_length=36, max_length=36)
    account_email: str = Field(min_length=3, max_length=255)
    service: str = Field(min_length=2, max_length=32)
    not_before: datetime


def _authorize(authorization: str = Header(default="")) -> None:
    expected = settings.MAIL_AGENT_API_TOKEN
    supplied = authorization.removeprefix("Bearer ").strip()
    if not expected or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Agente no autorizado")


@router.post("/codes/claim", dependencies=[Depends(_authorize)])
def claim_code(data: CodeRequest, db: Session = Depends(get_db)):
    try:
        result = claim_recent_code(
            db,
            job_id=data.job_id,
            account_email=data.account_email,
            service=data.service,
            not_before=data.not_before,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not result:
        # El escaneo periódico puede tardar más que la ventana de un código.
        # Solicita una sincronización prioritaria, limitada a una cada 15 s
        # por cuenta para que el polling del agente no sature Gmail/IMAP.
        account_id = db.scalar(
            select(MailAccount.id).where(
                MailAccount.email.ilike(data.account_email.strip()),
                MailAccount.is_enabled.is_(True),
            )
        )
        sync_queued = False
        if account_id:
            try:
                key = f"mailctl:agent-sync:{account_id}"
                if _redis.set(key, "1", ex=15, nx=True):
                    from ..workers.tasks import scan_account_chunk

                    scan_account_chunk.delay([account_id])
                    sync_queued = True
            except Exception:
                # La consulta sigue siendo segura aunque Redis esté reiniciando;
                # el siguiente polling o el beat periódico volverán a intentar.
                sync_queued = False
        return {"status": "pending", "sync_queued": sync_queued}
    code, message = result
    return {
        "status": "found",
        "code": code,
        "received_at": message.received_at,
    }
