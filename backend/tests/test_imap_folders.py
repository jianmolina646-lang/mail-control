from app.services.imap_service import _received_folders


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


def test_received_folders_excludes_duplicate_and_system_mailboxes():
    assert _received_folders(FakeServer()) == ["Streaming"]
