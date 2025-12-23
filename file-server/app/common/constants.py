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


# ============================================================================
# Pagination Defaults
# ============================================================================

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


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
# Crawl4AI Configurations
# ============================================================================

# Config for origin page - full config with stream for detailed extraction
ORIGIN_CRAWLER_CONFIG = {
    "type": "CrawlerRunConfig",
    "params": {
        "scraping_strategy": {
            "type": "LXMLWebScrapingStrategy",
            "params": {}
        },
        "table_extraction": {
            "type": "DefaultTableExtraction",
            "params": {}
        },
        "exclude_social_media_domains": [
            "facebook.com",
            "twitter.com",
            "x.com",
            "linkedin.com",
            "instagram.com",
            "pinterest.com",
            "tiktok.com",
            "snapchat.com",
            "reddit.com"
        ],
        "stream": True
    }
}

# Config for batch crawling - simpler with browser config for performance
BATCH_BROWSER_CONFIG = {
    "type": "BrowserConfig",
    "params": {
        "headers": {
            "type": "dict",
            "value": {
                "sec-ch-ua": "\"Chromium\";v=\"116\", \"Not_A Brand\";v=\"8\", \"Google Chrome\";v=\"116\""
            }
        },
        "extra_args": [
            "--no-sandbox",
            "--disable-gpu"
        ]
    }
}

