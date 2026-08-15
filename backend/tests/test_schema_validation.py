import unittest

from pydantic import ValidationError

from app.api.agent_routes import CodeRequest
from app.schemas.schemas import LoginIn, MailAccountIn, MailAccountUpdate, TwoFactorConfirmIn


class SchemaValidationTests(unittest.TestCase):
    def test_login_rejects_empty_or_oversized_password(self):
        with self.assertRaises(ValidationError):
            LoginIn(email="admin@example.com", password="")
        with self.assertRaises(ValidationError):
            LoginIn(email="admin@example.com", password="x" * 129)

    def test_mail_account_validates_provider_host_and_port(self):
        with self.assertRaises(ValidationError):
            MailAccountIn(
                email="user@example.com",
                provider="unknown",
                imap_host="imap.example.com",
            )
        with self.assertRaises(ValidationError):
            MailAccountUpdate(imap_port=70000)
        with self.assertRaises(ValidationError):
            MailAccountUpdate(imap_host="invalid host")

    def test_totp_requires_six_digits(self):
        with self.assertRaises(ValidationError):
            TwoFactorConfirmIn(code="12ab56")

    def test_agent_request_validates_uuid_email_and_service(self):
        with self.assertRaises(ValidationError):
            CodeRequest(
                job_id="not-a-uuid",
                account_email="invalid",
                service="bad service",
                not_before="2026-08-15T00:00:00Z",
            )


if __name__ == "__main__":
    unittest.main()
