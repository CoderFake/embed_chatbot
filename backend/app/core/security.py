from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import uuid
from jose import JWTError, jwt
from fastapi import HTTPException, status
from cryptography.fernet import Fernet
import secrets

from app.config.settings import settings

# Initialize Fernet encryption for API keys
_encryption_key = settings.ENCRYPTION_KEY
if not _encryption_key:
    # Generate a key if not provided (for development only)
    _encryption_key = Fernet.generate_key().decode()

_fernet = Fernet(_encryption_key.encode() if isinstance(_encryption_key, str) else _encryption_key)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT access token.
    
    Args:
        data: Payload data to encode (should include: sub, email, role)
        expires_delta: Optional custom expiration time
        
    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # Add standard JWT claims
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "jti": str(uuid.uuid4()),  # Unique JWT ID for blacklisting
        "token_type": "access"
    })
    
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.JWT_SECRET_KEY, 
        algorithm=settings.JWT_ALGORITHM
    )
    
    return encoded_jwt


def create_refresh_token(data: Dict[str, Any]) -> str:
    """
    Create JWT refresh token with longer expiration.
    
    Args:
        data: Payload data to encode (should include: sub)
        
    Returns:
        Encoded JWT refresh token string
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "jti": str(uuid.uuid4()),
        "token_type": "refresh"
    })
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    
    return encoded_jwt


def create_widget_token(
    bot_id: str,
    visitor_id: str,
    session_id: str,
    origin: str
) -> str:
    """
    Create short-lived JWT for widget chat sessions.
    
    Args:
        bot_id: Bot UUID
        visitor_id: Visitor UUID
        session_id: Chat session UUID
        origin: Request origin for validation
        
    Returns:
        Encoded JWT token for widget authentication
    """
    expire = datetime.utcnow() + timedelta(hours=settings.WIDGET_TOKEN_EXPIRE_HOURS)
    
    payload = {
        "sub": visitor_id,
        "bot_id": bot_id,
        "session_id": session_id,
        "origin": origin,
        "exp": expire,
        "iat": datetime.utcnow(),
        "jti": str(uuid.uuid4()),
        "token_type": "widget"
    }
    
    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )


def create_invite_token(email: str, role: str) -> str:
    """
    Create invite token for user registration.
    
    Args:
        email: Invited user email
        role: User role to assign
        
    Returns:
        Encoded JWT invite token
    """
    expire = datetime.utcnow() + timedelta(days=settings.INVITE_TOKEN_EXPIRE_DAYS)
    
    payload = {
        "sub": email,
        "role": role,
        "exp": expire,
        "iat": datetime.utcnow(),
        "jti": str(uuid.uuid4()),
        "token_type": "invite"
    }
    
    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decode and verify JWT token.
    
    Args:
        token: JWT token string
        
    Returns:
        Decoded token payload
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


def verify_token_type(payload: Dict[str, Any], expected_type: str) -> bool:
    """
    Verify token type matches expected type.
    
    Args:
        payload: Decoded token payload
        expected_type: Expected token type (access, refresh, widget, invite)
        
    Returns:
        True if token type matches
        
    Raises:
        HTTPException: If token type doesn't match
    """
    token_type = payload.get("token_type")
    
    if token_type != expected_type:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token type. Expected {expected_type}, got {token_type}"
        )
    
    return True


def get_jti_from_token(token: str) -> str:
    """
    Extract JTI (JWT ID) from token without full validation.
    Used for blacklist checking.
    
    Args:
        token: JWT token string
        
    Returns:
        JTI string
    """
    try:
        # Decode without verification to get jti
        unverified = jwt.get_unverified_claims(token)
        return unverified.get("jti", "")
    except Exception:
        return ""


def encrypt_api_key(api_key: str) -> str:
    """
    Encrypt API key for secure storage.
    
    Args:
        api_key: Plain text API key
        
    Returns:
        Encrypted API key (base64 encoded)
    """
    return _fernet.encrypt(api_key.encode()).decode()


def decrypt_api_key(encrypted_key: str) -> str:
    """
    Decrypt stored API key.
    
    Args:
        encrypted_key: Encrypted API key
        
    Returns:
        Plain text API key
        
    Raises:
        Exception: If decryption fails
    """
    try:
        return _fernet.decrypt(encrypted_key.encode()).decode()
    except Exception as e:
        raise ValueError(f"Failed to decrypt API key: {str(e)}")


def generate_secure_token(length: int = 32) -> str:
    """
    Generate cryptographically secure random token.
    
    Args:
        length: Token length in bytes
        
    Returns:
        Hex-encoded random token
    """
    return secrets.token_urlsafe(length)


def get_encryption_key() -> str:
    """
    Get the encryption key used for API key encryption.
    Should be stored securely and never exposed.
    
    Returns:
        Encryption key string
    """
    return _encryption_key if isinstance(_encryption_key, str) else _encryption_key.decode()
