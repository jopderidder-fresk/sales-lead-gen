"""Tests for Fernet encryption utilities."""

from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet


@pytest.fixture()
def fernet_key() -> str:
    return Fernet.generate_key().decode()


class TestEncryptDecrypt:
    def test_round_trip(self, fernet_key: str) -> None:
        with patch("app.core.encryption.settings") as mock_settings:
            mock_settings.fernet_key = fernet_key
            from app.core.encryption import decrypt, encrypt

            plaintext = "sk-live-abc123"
            ciphertext = encrypt(plaintext)
            assert ciphertext != plaintext
            assert decrypt(ciphertext) == plaintext

    def test_different_plaintexts_produce_different_ciphertexts(self, fernet_key: str) -> None:
        with patch("app.core.encryption.settings") as mock_settings:
            mock_settings.fernet_key = fernet_key
            from app.core.encryption import encrypt

            c1 = encrypt("secret-a")
            c2 = encrypt("secret-b")
            assert c1 != c2

    def test_decrypt_with_wrong_key_raises(self, fernet_key: str) -> None:
        from app.core.encryption import EncryptionError, encrypt

        with patch("app.core.encryption.settings") as mock_settings:
            mock_settings.fernet_key = fernet_key
            ciphertext = encrypt("secret")

        other_key = Fernet.generate_key().decode()
        with patch("app.core.encryption.settings") as mock_settings:
            mock_settings.fernet_key = other_key
            from app.core.encryption import decrypt

            with pytest.raises(EncryptionError, match="invalid token or wrong key"):
                decrypt(ciphertext)

    def test_empty_fernet_key_raises(self) -> None:
        with patch("app.core.encryption.settings") as mock_settings:
            mock_settings.fernet_key = ""
            from app.core.encryption import EncryptionError, encrypt

            with pytest.raises(EncryptionError, match="FERNET_KEY is not configured"):
                encrypt("anything")

    def test_invalid_fernet_key_raises(self) -> None:
        with patch("app.core.encryption.settings") as mock_settings:
            mock_settings.fernet_key = "not-a-valid-key"
            from app.core.encryption import EncryptionError, encrypt

            with pytest.raises(EncryptionError, match="Invalid FERNET_KEY"):
                encrypt("anything")
