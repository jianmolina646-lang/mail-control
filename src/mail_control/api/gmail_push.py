from __future__ import annotations

from typing import Annotated, Any

import httpx
import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from mail_control.api.dependencies import system_database_session
from mail_control.modules.mail.gmail_push import (
    decode_pubsub_payload,
    enqueue_from_push,
    verify_pubsub_push_request,
)
from mail_control.settings import get_settings

router = APIRouter(prefix="/v1/webhooks/gmail", tags=["gmail-push"])
logger = structlog.get_logger(__name__)


@router.post("/pubsub", status_code=status.HTTP_204_NO_CONTENT)
async def pubsub_push(
    request: Request,
    session: Annotated[AsyncSession, Depends(system_database_session)],
    token: Annotated[str | None, Query(max_length=256)] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> Response:
    settings = get_settings()
    if not settings.gmail_push_enabled:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    try:
        await verify_pubsub_push_request(
            authorization=authorization,
            verification_token=settings.gmail_pubsub_verification_token,
            provided_token=token,
            expected_service_account=settings.gmail_pubsub_service_account,
            expected_audience=settings.gmail_pubsub_audience,
            redis=request.app.state.resources.redis,
        )
        envelope: dict[str, Any] = await request.json()
        payload = decode_pubsub_payload(envelope)
        await enqueue_from_push(
            session,
            request.app.state.resources,
            settings,
            email=payload["emailAddress"],
            history_id=payload["historyId"],
        )
    except (ValueError, httpx.HTTPError) as error:
        logger.warning("gmail_pubsub_webhook_rejected", detail=str(error))
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
