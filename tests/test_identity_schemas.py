from __future__ import annotations

import pytest
from pydantic import ValidationError

from mail_control.modules.identity.schemas import RegisterTenantRequest


def test_registration_normalizes_email() -> None:
    request = RegisterTenantRequest(
        tenant_name="Jheliz",
        tenant_slug="jheliz-control",
        owner_name="Owner",
        email="  OWNER@Example.COM ",
        password="a-strong-password",
    )
    assert request.email == "owner@example.com"


@pytest.mark.parametrize("slug", ["UPPERCASE", "-invalid", "invalid_", "x"])
def test_registration_rejects_invalid_tenant_slug(slug: str) -> None:
    with pytest.raises(ValidationError):
        RegisterTenantRequest(
            tenant_name="Jheliz",
            tenant_slug=slug,
            owner_name="Owner",
            email="owner@example.com",
            password="a-strong-password",
        )
