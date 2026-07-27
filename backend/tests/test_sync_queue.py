import unittest
from unittest.mock import Mock, patch

from app.workers import tasks


class SyncQueueTests(unittest.TestCase):
    def test_transient_timeout_is_detected(self):
        self.assertTrue(tasks._is_transient_imap_error(TimeoutError("read timed out")))
        self.assertFalse(
            tasks._is_transient_imap_error(
                RuntimeError("Credenciales inválidas")
            )
        )

    def test_transient_fetch_is_retried_before_failing_account(self):
        account = Mock(email="slow@gmail.com")
        with patch.object(
            tasks.imap_service,
            "fetch_recent",
            side_effect=[TimeoutError("read timed out"), ["message"]],
        ) as fetch, patch.object(
            tasks.settings,
            "IMAP_RETRY_ATTEMPTS",
            2,
        ), patch.object(
            tasks.settings,
            "IMAP_RETRY_DELAY_SECONDS",
            0,
        ), patch.object(tasks.time, "sleep") as sleep:
            result = tasks._fetch_recent_with_retry(account, limit=25)

        self.assertEqual(result, ["message"])
        self.assertEqual(fetch.call_count, 2)
        sleep.assert_not_called()

    def test_permanent_fetch_error_is_not_retried(self):
        account = Mock(email="invalid@gmail.com")
        with patch.object(
            tasks.imap_service,
            "fetch_recent",
            side_effect=RuntimeError("Credenciales inválidas"),
        ) as fetch, patch.object(tasks.settings, "IMAP_RETRY_ATTEMPTS", 2):
            with self.assertRaisesRegex(RuntimeError, "Credenciales"):
                tasks._fetch_recent_with_retry(account)

        fetch.assert_called_once()

    def test_queue_account_sync_deduplicates_pending_account(self):
        redis = Mock()
        redis.set.return_value = False
        with patch.object(tasks, "_redis", redis), patch.object(
            tasks.scan_account_chunk,
            "apply_async",
        ) as apply_async:
            self.assertFalse(tasks.queue_account_sync(42))
            apply_async.assert_not_called()

    def test_queue_account_sync_reserves_before_enqueue(self):
        redis = Mock()
        redis.set.return_value = True
        with patch.object(tasks, "_redis", redis), patch.object(
            tasks.scan_account_chunk,
            "apply_async",
        ) as apply_async:
            self.assertTrue(tasks.queue_account_sync(42))
            apply_async.assert_called_once_with(
                args=[[42]],
                kwargs={"reserved": True},
            )
