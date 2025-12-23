"""
Encryption and decryption utilities for sensitive data (API keys, secrets).
Uses Fernet symmetric encryption from cryptography library.
"""
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from app.config.settings import settings


class EncryptionService:
    """
    Service for encrypting and decrypting sensitive data using Fernet.
    Encryption key is derived from SECRET_KEY in settings.
    """
    
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
    
    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt plaintext string.
        
        Args:
            plaintext: String to encrypt (e.g., API key)
            
        Returns:
            Base64-encoded encrypted string
        """
        if not plaintext:
            raise ValueError("Cannot encrypt empty string")
        
        encrypted_bytes = self.cipher.encrypt(plaintext.encode())
        return encrypted_bytes.decode()
    
    def decrypt(self, encrypted: str) -> str:
        """
        Decrypt encrypted string.
        
        Args:
            encrypted: Base64-encoded encrypted string
            
        Returns:
            Decrypted plaintext string
            
        Raises:
            ValueError: If decryption fails
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


def encrypt_api_key(api_key: str) -> str:
    """
    Convenience function to encrypt API key.
    
    Args:
        api_key: Plain API key
        
    Returns:
        Encrypted API key
    """
    return encryption_service.encrypt(api_key)


def decrypt_api_key(encrypted_key: str) -> str:
    """
    Convenience function to decrypt API key.

    Args:
        encrypted_key: Encrypted API key

    Returns:
        Plain API key
    """
    return encryption_service.decrypt(encrypted_key)


def is_encrypted(value: str) -> bool:
    """
    Check if a string is already encrypted by Fernet.

    Args:
        value: String to check

    Returns:
        True if string appears to be Fernet-encrypted, False otherwise
    """
    if not value:
        return False

    try:
        encryption_service.cipher.decrypt(value.encode())
        return True
    except Exception:
        return False
