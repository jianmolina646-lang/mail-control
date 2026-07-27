import unittest

from app.core import request_security


class RequestSecurityTests(unittest.TestCase):
    def test_client_ip_uses_first_forwarded_address(self):
        headers = {
            "x-forwarded-for": "203.0.113.20, 10.0.0.2",
            "x-real-ip": "10.0.0.3",
        }
        self.assertEqual(
            request_security.client_ip(headers, "10.0.0.4"),
            "203.0.113.20",
        )

    def test_json_with_charset_is_allowed(self):
        self.assertTrue(
            request_security.content_type_allowed(
                "POST",
                20,
                "application/json; charset=utf-8",
            )
        )

    def test_body_with_unexpected_content_type_is_rejected(self):
        self.assertFalse(
            request_security.content_type_allowed("POST", 20, "text/plain")
        )

    def test_empty_write_does_not_require_content_type(self):
        self.assertTrue(request_security.content_type_allowed("POST", 0, ""))

    def test_csrf_requires_matching_non_empty_values(self):
        self.assertTrue(request_security.csrf_valid("secret", "secret"))
        self.assertFalse(request_security.csrf_valid("secret", "other"))
        self.assertFalse(request_security.csrf_valid("", ""))


if __name__ == "__main__":
    unittest.main()
