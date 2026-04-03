"""Fernet symmetric encryption for API keys and sensitive values.

Usage:
    from app.core.encryption import encrypt, decrypt

    ciphertext = encrypt("sk-live-abc123")
    plaintext  = decrypt(ciphertext)

The Fernet key is read once from ``settings.fernet_key``.  In development
(when the key is empty) the functions raise ``EncryptionError`` so that
callers never silently fall back to plaintext storage.
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


class EncryptionError(Exception):
    """Raised when encryption or decryption fails."""


def _get_fernet() -> Fernet:
    key = settings.fernet_key
    if not key:
        raise EncryptionError(
            "FERNET_KEY is not configured. "
            "Generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
        )
    try:
        return Fernet(key.encode())
    except (ValueError, Exception) as exc:
        raise EncryptionError(f"Invalid FERNET_KEY: {exc}") from exc


def encrypt(plaintext: str) -> str:
    """Encrypt a string and return a URL-safe base64 ciphertext."""
    f = _get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt a Fernet token back to the original string.

    Raises ``EncryptionError`` if the token is invalid or the key is wrong.
    """
    f = _get_fernet()
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise EncryptionError("Decryption failed — invalid token or wrong key") from exc
