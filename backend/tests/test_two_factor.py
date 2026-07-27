import pyotp

from app.services import two_factor


def test_totp_accepts_current_google_authenticator_code():
    secret = two_factor.new_secret()
    assert two_factor.verify_totp(secret, pyotp.TOTP(secret).now())


def test_recovery_code_can_only_be_used_once():
    code = two_factor.generate_recovery_codes(1)[0]
    serialized = two_factor.hash_recovery_codes([code])
    accepted, remaining = two_factor.consume_recovery_code(serialized, code)
    accepted_again, _ = two_factor.consume_recovery_code(remaining, code)
    assert accepted is True
    assert accepted_again is False


def test_qr_is_embedded_png_and_uri_names_product():
    secret = two_factor.new_secret()
    uri = two_factor.provisioning_uri(secret, "admin@example.com")
    assert "issuer=Mail%20Control" in uri
    assert two_factor.qr_data_uri(uri).startswith("data:image/png;base64,")
