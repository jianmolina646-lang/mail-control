from __future__ import annotations

from typing import Annotated, Any

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from mail_control.api.dependencies import system_database_session
from mail_control.modules.mail.microsoft_push import enqueue_from_graph_notification
from mail_control.settings import get_settings

router = APIRouter(prefix="/v1/webhooks/microsoft", tags=["microsoft-graph-webhooks"])
logger = structlog.get_logger(__name__)


@router.post("/graph")
async def graph_webhook(
    request: Request,
    session: Annotated[AsyncSession, Depends(system_database_session)],
    validation_token: Annotated[str | None, Query(alias="validationToken")] = None,
) -> Response:
    if validation_token is not None:
        return PlainTextResponse(validation_token)

    settings = get_settings()
    if not settings.microsoft_graph_webhook_enabled:
        return Response(status_code=status.HTTP_202_ACCEPTED)

    try:
        envelope: dict[str, Any] = await request.json()
        notifications = envelope.get("value")
        if not isinstance(notifications, list):
            raise ValueError("Microsoft Graph webhook omitted value list")
        for notification in notifications:
            if not isinstance(notification, dict):
                raise ValueError("Microsoft Graph notification must be an object")
            await enqueue_from_graph_notification(
                session,
                request.app.state.resources,
                settings,
                notification,
            )
    except (ValueError, httpx.HTTPError) as error:
        logger.warning("microsoft_graph_webhook_rejected", detail=str(error))
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error
    return Response(status_code=status.HTTP_202_ACCEPTED)
