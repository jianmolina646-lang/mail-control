from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from mail_control.modules.mail.models import AccountStatus
from mail_control.modules.system.mail_freshness import FreshnessAlerts, sync_issue
from mail_control.modules.system.telegram_alerts import TelegramAlerts
from tests.test_telegram_alerts import account

NOW = datetime(2026, 9, 8, tzinfo=UTC)


def mailbox(*, minutes=1, status=AccountStatus.CONNECTED, synced=True):
    return SimpleNamespace(
        status=status,
        last_synced_at=NOW - timedelta(minutes=minutes) if synced else None,
        created_at=NOW - timedelta(minutes=minutes),
    )


def test_healthy_container_does_not_imply_fresh_mailbox():
    assert sync_issue(mailbox(minutes=16), NOW, 900) == "stale"
    assert sync_issue(mailbox(minutes=1), NOW, 900) is None


def test_initial_sync_has_grace_and_disconnected_accounts_are_not_alerted():
    assert sync_issue(mailbox(minutes=5, synced=False), NOW, 900) is None
    assert sync_issue(mailbox(minutes=16, synced=False), NOW, 900) == "never_synced"
    assert sync_issue(mailbox(minutes=20, status=AccountStatus.DISCONNECTED), NOW, 900) is None


@pytest.mark.parametrize(
    "state,issue",
    [(AccountStatus.REAUTH_REQUIRED, "reauth_required"), (AccountStatus.ERROR, "sync_error")],
)
def test_permanent_errors_remain_visible_even_with_recent_sync(state, issue):
    assert sync_issue(mailbox(status=state), NOW, 900) == issue


def test_expired_push_alert_is_distinct_from_polling_freshness():
    assert (
        sync_issue(
            mailbox(), NOW, 900, push_enabled=True, push_expires_at=NOW - timedelta(seconds=1)
        )
        == "push_expired"
    )
    assert (
        sync_issue(
            mailbox(), NOW, 900, push_enabled=False, push_expires_at=NOW - timedelta(seconds=1)
        )
        is None
    )


def test_freshness_incident_is_not_cleared_by_normal_worker_recovery():
    item = account()
    assert FreshnessAlerts._active_key(None, item) != TelegramAlerts._active_key(None, item)
