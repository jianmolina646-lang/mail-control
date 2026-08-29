from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from mail_control.api.dependencies import Principal
from mail_control.api.saas import validate_managed_role, validate_managed_user
from mail_control.modules.identity.models import RoleName, User


def principal(role: RoleName) -> Principal:
    user = User(
        tenant_id=uuid4(),
        email="actor@example.com",
        email_normalized="actor@example.com",
        display_name="Actor",
        password_hash="unused",
        role=role,
        is_active=True,
    )
    return Principal(claims=SimpleNamespace(), user=user)  # type: ignore[arg-type]


def target(role: RoleName) -> User:
    return User(
        tenant_id=uuid4(),
        email="target@example.com",
        email_normalized="target@example.com",
        display_name="Target",
        password_hash="unused",
        role=role,
        is_active=True,
    )


@pytest.mark.parametrize("role", [RoleName.OWNER, RoleName.ADMIN])
def test_admin_cannot_assign_privileged_roles(role: RoleName) -> None:
    with pytest.raises(HTTPException) as error:
        validate_managed_role(principal(RoleName.ADMIN), role)
    assert error.value.status_code == 403


@pytest.mark.parametrize("role", [RoleName.OWNER, RoleName.ADMIN])
def test_admin_cannot_modify_privileged_users(role: RoleName) -> None:
    with pytest.raises(HTTPException) as error:
        validate_managed_user(principal(RoleName.ADMIN), target(role))
    assert error.value.status_code == 403


def test_owner_can_manage_admin_but_cannot_create_another_owner() -> None:
    validate_managed_user(principal(RoleName.OWNER), target(RoleName.ADMIN))
    with pytest.raises(HTTPException):
        validate_managed_role(principal(RoleName.OWNER), RoleName.OWNER)
