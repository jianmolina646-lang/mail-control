import unittest

from app.services.imap_service import _fetch_selected_folder, _received_folders


class FakeServer:
    def list_folders(self):
        return [
            ((b"\\HasNoChildren",), b"/", "INBOX"),
            ((b"\\All", b"\\HasNoChildren"), b"/", "[Gmail]/All Mail"),
            ((b"\\Important",), b"/", "[Gmail]/Important"),
            ((b"\\Spam",), b"/", "[Gmail]/Spam"),
            ((b"\\Flagged",), b"/", "[Gmail]/Starred"),
            ((b"\\Sent",), b"/", "[Gmail]/Sent Mail"),
            ((b"\\HasNoChildren",), b"/", "Streaming"),
        ]


class ReceivedFoldersTests(unittest.TestCase):
    def test_excludes_duplicate_and_system_mailboxes(self):
        self.assertEqual(
            _received_folders(FakeServer()),
            ["[Gmail]/Spam", "Streaming"],
        )

    def test_incremental_fetch_skips_uids_already_stored(self):
        class IncrementalServer:
            def select_folder(self, *_args, **_kwargs):
                return None

            def search(self, *_args, **_kwargs):
                return [10, 11]

            def fetch(self, *_args, **_kwargs):
                raise AssertionError("No debe descargar mensajes ya almacenados")

        self.assertEqual(
            _fetch_selected_folder(
                IncrementalServer(),
                "INBOX",
                100,
                {"10", "11"},
            ),
            [],
        )
