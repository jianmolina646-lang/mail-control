import unittest
from unittest.mock import Mock, patch

from cryptography.fernet import Fernet

from app.core import crypto
from app.services.imap_service import (
    _login_server,
    _received_folders,
    normalize_app_password,
)


class ImapPasswordTests(unittest.TestCase):
    def test_fernet_round_trip_preserves_spaces(self):
        password = "abcd efgh ijkl mnop"

        with patch.object(
            crypto.settings,
            "CREDENTIALS_ENCRYPTION_KEY",
            Fernet.generate_key().decode(),
        ):
            self.assertEqual(crypto.decrypt(crypto.encrypt(password)), password)

    def test_microsoft_app_password_removes_visual_whitespace(self):
        self.assertEqual(
            normalize_app_password(
                "abcd efgh\tijkl\nmnop",
                "user@outlook.com",
                "outlook.office365.com",
            ),
            "abcdefghijklmnop",
        )

    def test_custom_imap_password_keeps_spaces(self):
        password = "a real password with spaces"

        self.assertEqual(
            normalize_app_password(
                password,
                "user@example.com",
                "imap.example.com",
            ),
            password,
        )

    def test_microsoft_login_requires_oauth(self):
        server = Mock()

        with self.assertRaisesRegex(RuntimeError, "OAuth2"):
            _login_server(
                server,
                "user@hotmail.com",
                "abcd efgh ijkl mnop",
                host="outlook.office365.com",
            )
        server.login.assert_not_called()

    def test_microsoft_login_uses_xoauth2_token(self):
        server = Mock()
        account = Mock(oauth_token="short-lived-access-token")

        _login_server(
            server,
            "user@hotmail.com",
            "",
            account=account,
            host="outlook.office365.com",
        )

        server.oauth2_login.assert_called_once_with(
            "user@hotmail.com",
            "short-lived-access-token",
        )

    def test_received_folders_exclude_outgoing_and_deleted_mail(self):
        server = Mock()
        server.list_folders.return_value = [
            ((b"\\Inbox",), b"/", "Inbox"),
            ((b"\\Junk",), b"/", "Junk"),
            ((b"\\Archive",), b"/", "Archive"),
            ((), b"/", "Netflix"),
            ((b"\\Sent",), b"/", "Sent"),
            ((b"\\Drafts",), b"/", "Drafts"),
            ((b"\\Trash",), b"/", "Deleted"),
        ]

        self.assertEqual(
            _received_folders(server),
            ["Junk", "Archive", "Netflix"],
        )


if __name__ == "__main__":
    unittest.main()
