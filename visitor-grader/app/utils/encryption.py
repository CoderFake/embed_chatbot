"""Encryption and decryption utilities for API keys."""
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.config.settings import settings


class EncryptionService:
    """Service for encrypting and decrypting API keys using Fernet."""

    def __init__(self):
        """Initialize encryption service with key derivation."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=settings.ENCRYPTION_SALT.encode(),
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(
            kdf.derive(settings.SECRET_KEY.encode())
        )
        self.cipher = Fernet(key)

    def decrypt(self, encrypted: str) -> str:
        """
        Decrypt encrypted string.

        Args:
            encrypted: Base64-encoded encrypted string

        Returns:
            Decrypted plaintext string
        """
        if not encrypted:
            raise ValueError("Cannot decrypt empty string")

        try:
            decrypted_bytes = self.cipher.decrypt(encrypted.encode())
            return decrypted_bytes.decode()
        except Exception as e:
            raise ValueError(f"Decryption failed: {str(e)}")


# Singleton instance
encryption_service = EncryptionService()


def decrypt_api_key(encrypted_key: str) -> str:
    """Decrypt API key."""
    return encryption_service.decrypt(encrypted_key)
