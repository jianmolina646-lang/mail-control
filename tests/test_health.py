from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mail_control.api.health import router
from mail_control.modules.system.health import DependencyStatus


def test_liveness() -> None:
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_dependency_status_requires_every_dependency() -> None:
    assert DependencyStatus(True, True, True).ready is True
    assert DependencyStatus(True, False, True).ready is False
