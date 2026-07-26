"""API privada y mínima para el agente de automatización."""

from __future__ import annotations

import hmac
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.db import get_db
from ..services.agent_codes import claim_recent_code

router = APIRouter(prefix="/api/internal/agent", tags=["internal-agent"])


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
        return {"status": "pending"}
    code, message = result
    return {
        "status": "found",
        "code": code,
        "received_at": message.received_at,
    }
