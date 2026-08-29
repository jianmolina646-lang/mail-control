from __future__ import annotations

import pytest

from mail_control.modules.mail.crypto import CredentialCipher


def test_credential_cipher_round_trip_and_wrong_key() -> None:
    cipher = CredentialCipher("primary-encryption-key")
    encrypted = cipher.encrypt("refresh-token-secret")

    assert "refresh-token-secret" not in encrypted
    assert cipher.decrypt(encrypted) == "refresh-token-secret"

    with pytest.raises(ValueError):
        CredentialCipher("different-key").decrypt(encrypted)
