from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from mail_control.api.auth_flows import router as auth_flows_router
from mail_control.api.dashboard import router as dashboard_router
from mail_control.api.gmail import router as gmail_router
from mail_control.api.gmail_push import router as gmail_push_router
from mail_control.api.health import router as health_router
from mail_control.api.identity import router as identity_router
from mail_control.api.microsoft import router as microsoft_router
from mail_control.api.microsoft_graph import router as microsoft_graph_router
from mail_control.api.platform import router as platform_router
from mail_control.api.saas import router as saas_router
from mail_control.infrastructure.resources import Resources
from mail_control.logging import configure_logging
from mail_control.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.resources = await Resources.connect(settings)
    try:
        yield
    finally:
        await app.state.resources.close()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "X-Request-ID"],
    )
    app.include_router(health_router)
    app.include_router(identity_router)
    app.include_router(auth_flows_router)
    app.include_router(gmail_router)
    app.include_router(gmail_push_router)
    app.include_router(microsoft_router)
    app.include_router(microsoft_graph_router)
    app.include_router(dashboard_router)
    app.include_router(saas_router)
    app.include_router(platform_router)
    return app
