"""Encriptación simétrica (Fernet) para las App Passwords IMAP.

Las credenciales NUNCA se guardan en texto plano: se cifran con la clave
CREDENTIALS_ENCRYPTION_KEY antes de tocar la base de datos.
"""

from cryptography.fernet import Fernet, InvalidToken

from .config import settings


def _fernet() -> Fernet:
    key = settings.CREDENTIALS_ENCRYPTION_KEY
    if not key:
        raise RuntimeError(
            "CREDENTIALS_ENCRYPTION_KEY no configurada. "
            "Generá una con: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(key.encode())


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("No se pudo desencriptar: clave incorrecta o dato corrupto") from exc
