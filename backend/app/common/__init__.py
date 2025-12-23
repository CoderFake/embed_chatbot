"""
Common utilities, constants, and shared code
"""
# Enums (centralized)
from app.common.enums import (
    UserRole,
    TokenType,
    InviteStatus,
    BotStatus,
    DocumentStatus,
    SessionStatus,
    NotificationType,
    AuthType,
    ProviderStatus,
    ModelType,
)

# Constants (static values)
from app.common.constants import (
    # File Processing
    DOCLING_FORMATS,
    LANGCHAIN_FORMATS,
    SUPPORTED_FILE_EXTENSIONS,
    MAX_FILE_SIZE_MB,
    MAX_FILE_SIZE_BYTES,
    
    # Cache
    CachePrefix,
    
    # Messages
    ErrorMessage,
    SuccessMessage,
    
    # Pagination
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    
    # Regex
    EMAIL_REGEX,
    URL_REGEX,
    BOT_KEY_REGEX,
)

# Types (data classes)
from app.common.types import CurrentUser

__all__ = [
    # Enums
    "UserRole",
    "TokenType",
    "InviteStatus",
    "BotStatus",
    "DocumentStatus",
    "SessionStatus",
    "NotificationType",
    "AuthType",
    "ProviderStatus",
    "ModelType",
    
    # File Processing Constants
    "DOCLING_FORMATS",
    "LANGCHAIN_FORMATS",
    "SUPPORTED_FILE_EXTENSIONS",
    "MAX_FILE_SIZE_MB",
    "MAX_FILE_SIZE_BYTES",
    
    # Cache
    "CachePrefix",
    
    # Messages
    "ErrorMessage",
    "SuccessMessage",
    
    # Pagination
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    
    # Regex
    "EMAIL_REGEX",
    "URL_REGEX",
    "BOT_KEY_REGEX",
    
    # Types
    "CurrentUser",
]
