import unittest

import pyotp

from app.services import two_factor


class TwoFactorTests(unittest.TestCase):
    def test_totp_accepts_current_google_authenticator_code(self):
        secret = two_factor.new_secret()
        self.assertTrue(two_factor.verify_totp(secret, pyotp.TOTP(secret).now()))

    def test_recovery_code_can_only_be_used_once(self):
        code = two_factor.generate_recovery_codes(1)[0]
        serialized = two_factor.hash_recovery_codes([code])
        accepted, remaining = two_factor.consume_recovery_code(serialized, code)
        accepted_again, _ = two_factor.consume_recovery_code(remaining, code)
        self.assertTrue(accepted)
        self.assertFalse(accepted_again)

    def test_qr_is_embedded_png_and_uri_names_product(self):
        secret = two_factor.new_secret()
        uri = two_factor.provisioning_uri(secret, "admin@example.com")
        self.assertIn("issuer=Mail%20Control", uri)
        self.assertTrue(two_factor.qr_data_uri(uri).startswith("data:image/png;base64,"))


if __name__ == "__main__":
    unittest.main()
