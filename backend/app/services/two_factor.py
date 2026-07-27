"""TOTP compatible con Google Authenticator y códigos de recuperación."""

from __future__ import annotations

import base64
import hashlib
import hmac
import io
import json
import secrets

import pyotp
import qrcode

from ..core import crypto
from ..core.config import settings


def new_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(
        name=email,
        issuer_name="Mail Control",
    )


def qr_data_uri(uri: str) -> str:
    image = qrcode.make(uri)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode()


def verify_totp(secret: str, code: str) -> bool:
    normalized = "".join(code.split())
    return bool(normalized) and pyotp.TOTP(secret).verify(
        normalized,
        valid_window=1,
    )


def generate_recovery_codes(count: int = 10) -> list[str]:
    return [
        f"{secrets.token_hex(2).upper()}-{secrets.token_hex(2).upper()}"
        for _ in range(count)
    ]


def _hash_code(code: str) -> str:
    normalized = code.strip().upper().replace(" ", "")
    return hmac.new(
        settings.SECRET_KEY.encode(),
        normalized.encode(),
        hashlib.sha256,
    ).hexdigest()


def hash_recovery_codes(codes: list[str]) -> str:
    return json.dumps([_hash_code(code) for code in codes])


def consume_recovery_code(serialized: str, code: str) -> tuple[bool, str]:
    try:
        hashes = json.loads(serialized or "[]")
    except json.JSONDecodeError:
        hashes = []
    candidate = _hash_code(code)
    for index, stored in enumerate(hashes):
        if hmac.compare_digest(candidate, stored):
            hashes.pop(index)
            return True, json.dumps(hashes)
    return False, serialized or "[]"


def encrypt_secret(secret: str) -> str:
    return crypto.encrypt(secret)


def decrypt_secret(encrypted: str) -> str:
    return crypto.decrypt(encrypted)
