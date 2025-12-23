"""
Common constants and configurations used across the application.
Note: Enums are in enums.py, not here. This file only contains static values.
"""
from typing import Set


# ============================================================================
# File Processing Constants
# ============================================================================

# Docling-supported formats (advanced processing with structure preservation)
DOCLING_FORMATS: Set[str] = {
    '.pdf', '.docx', '.pptx', '.xlsx', 
    '.html', '.htm', '.csv',
    '.png', '.jpeg', '.jpg', '.tiff', '.tif', '.bmp',
    '.md', '.txt'
}

# LangChain-supported formats (basic text extraction)
LANGCHAIN_FORMATS: Set[str] = {
    '.pdf', '.docx', '.doc', 
    '.txt', '.md', 
    '.html', '.htm', 
    '.pptx', '.ppt', 
    '.xlsx', '.xls', 
    '.csv'
}

# All supported file extensions for document upload
SUPPORTED_FILE_EXTENSIONS: Set[str] = DOCLING_FORMATS.union(LANGCHAIN_FORMATS)

# Max file size for uploads (in bytes)
MAX_FILE_SIZE_MB = 50
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024  # 50MB


# ============================================================================
# Cache Key Prefixes
# ============================================================================

class CachePrefix:
    """Redis cache key prefixes for consistent key naming"""
    USER = "user"
    BOT = "bot"
    DOCUMENT = "document"
    VISITOR = "visitor"
    PROVIDER = "provider"
    MODEL = "model"
    BOT_CONFIG = "bot_config"
    ALLOWED_ORIGINS = "allowed_origins"
    ANALYTICS_OVERVIEW = "analytics_overview"
    ANALYTICS_BOT = "analytics_bot"
    BLACKLIST = "blacklist"
    RATE_LIMIT = "rate_limit"
    INVITE = "invite"


# ============================================================================
# HTTP Status Messages
# ============================================================================

class ErrorMessage:
    """Common error messages"""
    # Authentication
    INVALID_CREDENTIALS = "Invalid email or password"
    UNAUTHORIZED = "Unauthorized access"
    TOKEN_EXPIRED = "Token has expired"
    TOKEN_INVALID = "Invalid token"
    TOKEN_BLACKLISTED = "Token has been revoked"
    
    # Authorization
    INSUFFICIENT_PERMISSIONS = "Insufficient permissions"
    FORBIDDEN = "Access forbidden"
    
    # Resource Not Found
    USER_NOT_FOUND = "User not found"
    BOT_NOT_FOUND = "Bot not found"
    DOCUMENT_NOT_FOUND = "Document not found"
    VISITOR_NOT_FOUND = "Visitor not found"
    
    # Validation
    INVALID_FILE_TYPE = "Invalid file type. Supported formats: {formats}"
    FILE_TOO_LARGE = "File too large. Maximum size: {size}MB"
    INVALID_INPUT = "Invalid input data"
    
    # Conflicts
    EMAIL_ALREADY_EXISTS = "Email already exists"
    BOT_KEY_ALREADY_EXISTS = "Bot key already exists"
    
    # Server Errors
    INTERNAL_ERROR = "Internal server error"
    SERVICE_UNAVAILABLE = "Service temporarily unavailable"


class SuccessMessage:
    """Common success messages"""
    # Authentication
    LOGIN_SUCCESS = "Login successful"
    LOGOUT_SUCCESS = "Logout successful"
    TOKEN_REFRESHED = "Token refreshed successfully"
    
    # User Management
    USER_CREATED = "User created successfully"
    USER_UPDATED = "User updated successfully"
    USER_DELETED = "User deleted successfully"
    PASSWORD_CHANGED = "Password changed successfully"
    
    # Bot Management
    BOT_CREATED = "Bot created successfully"
    BOT_UPDATED = "Bot updated successfully"
    BOT_DELETED = "Bot deleted successfully"
    
    # Document Management
    DOCUMENT_UPLOADED = "Document uploaded successfully"
    DOCUMENT_DELETED = "Document deleted successfully"
    DOCUMENT_PROCESSING = "Document processing started"
    
    # Invite Management
    INVITE_SENT = "Invite sent successfully"
    INVITE_ACCEPTED = "Invite accepted successfully"
    INVITE_REVOKED = "Invite revoked successfully"


# ============================================================================
# Pagination Defaults
# ============================================================================

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


# ============================================================================
# Regex Patterns
# ============================================================================

EMAIL_REGEX = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
URL_REGEX = r'^https?://[^\s<>"{}|\\^`\[\]]+$'
BOT_KEY_REGEX = r'^bot_[a-zA-Z0-9_]+$'


# ============================================================================
# Email Subjects
# ============================================================================
class EmailSubject:
    """Email subject lines"""
    PASSWORD_RESET = "Reset Your Password - Chatbot Platform"
    PASSWORD_CHANGED = "Your Password Has Been Changed"
    INVITE_USER = "You're Invited to Join Chatbot Platform"
    WELCOME = "Welcome to Chatbot Platform"
    HOT_LEAD_DETECTED = "Hot Lead Detected - Score: {score}/100 | {bot_name}"


# ============================================================================
# API Response Messages
# ============================================================================
class ResponseMessage:
    """Standard API response messages"""
    RESET_EMAIL_SENT = "reset_email_sent"
    INVITE_ACCEPTED = "Invite confirmed. Please login with credentials from email."
    ACCOUNT_CREATED = "Account created successfully"
    PASSWORD_CHANGED = "Password changed successfully"
    PASSWORD_RESET = "Password reset successfully"


# ============================================================================
# Redis Key Prefixes
# ============================================================================
class RedisKeyPrefix:
    """Redis key prefixes for consistent key naming"""
    PASSWORD_RESET = "password_reset"
    USER_TOKENS = "user_tokens"


# ============================================================================
# Frontend Routes (for email links)
# ============================================================================
class FrontendRoute:
    """Frontend route paths for email links"""
    RESET_PASSWORD = "/reset-password"
    ACCEPT_INVITE = "/accept-invite"
    LOGIN = "/login"


# ============================================================================
# Default Values
# ============================================================================
class DefaultValue:
    """Default values used across the application"""
    UNKNOWN_IP = "Unknown"


# ============================================================================
# Progress Milestones (percentage)
# ============================================================================
class ProgressMilestone:
    """Progress percentage milestones for different processing stages"""
    # Document processing stages
    DOWNLOAD_COMPLETE = 20
    EXTRACTION_COMPLETE = 40
    CHUNKING_COMPLETE = 60
    EMBEDDING_COMPLETE = 90
    
    # Crawl processing stages
    SITEMAP_FETCHED = 5
    CRAWL_IN_PROGRESS_MAX = 95
    
    # Common
    STARTED = 0
    COMPLETED = 100
    FAILED = 0


# ============================================================================
# File Path Patterns
# ============================================================================
class FilePathPattern:
    """File path patterns for document storage"""
    DOCUMENT_PATH_TEMPLATE = "{bot_key}/{doc_id}_{filename}"
    PATH_SEPARATOR = "/"
    FILENAME_SEPARATOR = "_"


# ============================================================================
# URL Crawling Constants
# ============================================================================

# Extensions to exclude when crawling URLs
EXCLUDED_URL_EXTENSIONS: Set[str] = {
    '.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp', '.ico', '.bmp',  # Images
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',  # Documents
    '.zip', '.rar', '.tar', '.gz',  # Archives
    '.mp4', '.avi', '.mov', '.mp3', '.wav',  # Media
    '.css', '.js', '.json', '.xml', '.woff', '.woff2', '.ttf', '.eot'  # Assets
}


# ============================================================================
# Widget File Constants
# ============================================================================

class WidgetFile:
    """Widget file management constants"""
    # Allowed file extensions
    ALLOWED_EXTENSIONS: Set[str] = {'.js'}
    
    # File size limits
    MAX_FILE_SIZE_MB = 10
    MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024  # 10MB
    
    # Storage paths in MinIO
    STORAGE_PREFIX = "widget"
    LATEST_FILENAME = "widget.js"
    VERSIONED_FILENAME_TEMPLATE = "widget.v{version}.js"
    
    # Cache headers
    VERSIONED_CACHE_CONTROL = "public, max-age=31536000, immutable"  # 1 year
    LATEST_CACHE_CONTROL = "public, max-age=3600"  # 1 hour
    
    # Error messages
    ERROR_INVALID_EXTENSION = "Only JavaScript files (.js) are allowed"
    ERROR_FILE_TOO_LARGE = f"File size exceeds {MAX_FILE_SIZE_MB}MB limit"
    ERROR_CANNOT_DELETE_LATEST = "Cannot delete the latest widget version. Upload a new version first."
    ERROR_FILE_NOT_FOUND = "Widget file not found"
    
    # Success messages
    SUCCESS_UPLOADED = "Widget uploaded successfully"
    SUCCESS_DELETED = "Widget file deleted"

