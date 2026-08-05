import pytest
from fastapi import HTTPException

from app.core.security import get_current_admin
from app.models.models import User


def user(*, is_admin: bool) -> User:
    return User(
        email="operator@example.com",
        hashed_password="unused",
        is_active=True,
        is_admin=is_admin,
    )


def test_regular_user_cannot_access_global_mail_data():
    with pytest.raises(HTTPException) as error:
        get_current_admin(user(is_admin=False))

    assert error.value.status_code == 403


def test_admin_can_access_global_mail_data():
    admin = user(is_admin=True)
    assert get_current_admin(admin) is admin


def test_new_users_are_not_administrators_by_default():
    created = User(email="new@example.com", hashed_password="unused")
    assert created.is_admin is None  # SQLAlchemy applies the false default on INSERT.
    assert User.__table__.c.is_admin.default.arg is False
