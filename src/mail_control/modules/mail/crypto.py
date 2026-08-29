from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken


class CredentialCipher:
    def __init__(self, key_material: str) -> None:
        key = base64.urlsafe_b64encode(hashlib.sha256(key_material.encode("utf-8")).digest())
        self._fernet = Fernet(key)

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")
        except InvalidToken as error:
            raise ValueError("credential cannot be decrypted") from error
