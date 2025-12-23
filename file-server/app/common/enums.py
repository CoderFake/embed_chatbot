"""
Enums for file-server
"""
from enum import Enum


class TaskType(str, Enum):
    """Background task type enumeration"""
    FILE_UPLOAD = "file_upload"
    CRAWL = "crawl"
    DELETE_DOCUMENT = "delete_document"
    RECRAWL = "recrawl"


class DocumentSource(str, Enum):
    """Document source enumeration"""
    FILE = "file"
    WEB = "web"
    API = "api"


class DocumentStatus(str, Enum):
    """Document processing status enumeration"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class JobStatus(str, Enum):
    """Background job processing status"""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    CRAWLING = "CRAWLING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"
