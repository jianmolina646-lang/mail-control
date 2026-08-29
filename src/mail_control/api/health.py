from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from mail_control.modules.system.health import check_dependencies

router = APIRouter(prefix="/health", tags=["system"])


@router.get("/live")
async def liveness() -> dict[str, str]:
    return {"status": "alive"}


@router.get("/")
@router.get("/ready")
async def readiness(request: Request) -> JSONResponse:
    status = await check_dependencies(request.app.state.resources)
    payload = {
        "status": "ready" if status.ready else "not_ready",
        "dependencies": {
            "database": status.database,
            "redis": status.redis,
            "rabbitmq": status.rabbitmq,
        },
    }
    return JSONResponse(payload, status_code=200 if status.ready else 503)
