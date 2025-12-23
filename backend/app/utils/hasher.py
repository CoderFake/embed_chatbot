from passlib.context import CryptContext
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import base64

from app.config.settings import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    """
    Hash a password using bcrypt.
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password string
    """

    if len(password) > 72:
        password = password[:72]
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.
    
    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password to compare against
        
    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


class Hasher:
    """
    Password hashing utility wrapper.
    """
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt."""
        return get_password_hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return verify_password(plain_password, hashed_password)


class APIKeyEncryption:
    """
    Encryption utility for API keys using Fernet symmetric encryption.
    """
    
    def __init__(self):
        """
        Initialize Fernet cipher with key derived from JWT secret.
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=settings.ENCRYPTION_SALT.encode(),
            iterations=100000,
            backend=default_backend()
        )
        key = base64.urlsafe_b64encode(kdf.derive(settings.JWT_SECRET_KEY.encode()))
        self.cipher = Fernet(key)
    
    def encrypt_api_key(self, api_key: str) -> str:
        """
        Encrypt an API key for secure storage.
        
        Args:
            api_key: Plain text API key
            
        Returns:
            Encrypted API key as base64 string
        """
        encrypted = self.cipher.encrypt(api_key.encode())
        return encrypted.decode()
    
    def decrypt_api_key(self, encrypted_key: str) -> str:
        """
        Decrypt an API key for use.
        
        Args:
            encrypted_key: Encrypted API key string
            
        Returns:
            Decrypted plain text API key
        """
        decrypted = self.cipher.decrypt(encrypted_key.encode())
        return decrypted.decode()

api_key_encryption = APIKeyEncryption()