import unittest
from unittest.mock import Mock, patch

from app.workers import tasks


class SyncQueueTests(unittest.TestCase):
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
