import unittest
from datetime import date
from unittest.mock import Mock, patch

from app.core.config import settings
from app.models.models import Message, Subscription, SubscriptionEvent, SyncEvent
from app.services import imap_service
from app.workers import tasks


class ScalabilityTests(unittest.TestCase):
    def test_scalability_indexes_are_part_of_model_metadata(self):
        index_names = {
            index.name
            for table in (Message, Subscription, SubscriptionEvent, SyncEvent)
            for index in table.__table__.indexes
        }
        self.assertIn("ix_message_received_id", index_names)
        self.assertIn("ix_message_account_received_id", index_names)
        self.assertIn("ix_messages_subject_trgm", index_names)
        self.assertIn("ix_sync_events_created_at", index_names)
        self.assertIn("ix_subscriptions_latest_message_id", index_names)
        self.assertIn("ix_subscription_events_message_id", index_names)

    def test_imap_folder_search_is_bounded_by_retention_date(self):
        server = Mock()
        server.search.return_value = []
        cutoff = date(2026, 7, 1)
        result = imap_service._fetch_selected_folder(
            server,
            "INBOX",
            100,
            set(),
            cutoff,
        )
        self.assertEqual(result, [])
        server.search.assert_called_once_with(["SINCE", cutoff])

    def test_sync_event_cleanup_uses_configured_retention(self):
        db = Mock()
        db.execute.return_value.rowcount = 4
        with patch.object(tasks, "SessionLocal", return_value=db):
            deleted = tasks.cleanup_old_sync_events.run()
        self.assertEqual(deleted, 4)
        db.commit.assert_called_once_with()
        db.close.assert_called_once_with()
        self.assertGreaterEqual(settings.SYNC_EVENT_RETENTION_DAYS, 30)


if __name__ == "__main__":
    unittest.main()
