"""
Centralized enumerations used across models, schemas, and services.
All Enums should be defined here for consistency and reusability.
"""
from enum import Enum


# ============================================================================
# User & Authentication Enums
# ============================================================================

class UserRole(str, Enum):
    """User role enumeration for RBAC"""
    ROOT = "root"
    ADMIN = "admin"
    MEMBER = "member"


class TokenType(str, Enum):
    """JWT token type enumeration"""
    ACCESS = "access"
    REFRESH = "refresh"
    WIDGET = "widget"
    INVITE = "invite"
    PASSWORD_RESET = "password_reset"


class InviteStatus(str, Enum):
    """Invite status enumeration"""
    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    REVOKED = "revoked"


# ============================================================================
# Bot & Configuration Enums
# ============================================================================

class BotStatus(str, Enum):
    """Bot status enumeration"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DRAFT = "draft"


# ============================================================================
# Document & Knowledge Base Enums
# ============================================================================

class DocumentStatus(str, Enum):
    """Document processing status enumeration"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentSource(str, Enum):
    """Document source type enumeration"""
    FILE = "file"
    WEB = "web"
    API = "api"


class TaskType(str, Enum):
    """Background task type enumeration"""
    FILE_UPLOAD = "file_upload"
    CRAWL = "crawl"
    DELETE_DOCUMENT = "delete_document"
    RECRAWL = "recrawl"

class TaskStatus(str, Enum):
    """Task status enum."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


# ============================================================================
# Visitor & Chat Session Enums
# ============================================================================

class SessionStatus(str, Enum):
    """Chat session status enumeration"""
    ACTIVE = "active"
    CLOSED = "closed"
    TIMEOUT = "timeout"


# ============================================================================
# Notification Enums
# ============================================================================

class AssessmentTaskType(str, Enum):
    """Task types for visitor grading/assessment."""
    GRADING = "grading"
    ASSESSMENT = "assessment"


class LeadCategory(str, Enum):
    """Lead quality categories."""
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"


class NotificationType(str, Enum):
    """Notification type enumeration"""
    INVITE = "invite"
    INVITE_ACCEPTED = "invite_accepted"
    BOT_ALERT = "bot_alert"
    SYSTEM = "system"
    LEAD_SCORED = "lead_scored"
    VISITOR_REVIEW = "visitor_review"
    TASK_PROCESSING = "task_processing"
    CONTACT_REQUEST = "contact_request"


# ============================================================================
# Provider & Model Enums
# ============================================================================

class AuthType(str, Enum):
    """Provider authentication type enumeration"""
    API_KEY = "api_key"
    BEARER = "bearer"
    OTP = "otp"


class ProviderStatus(str, Enum):
    """Provider status enumeration"""
    ACTIVE = "active"
    INACTIVE = "inactive"


class ModelType(str, Enum):
    """Model type enumeration"""
    CHAT = "chat"
    EMBEDDING = "embedding"


class JobStatus(str, Enum):
    """Background job processing status"""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    CRAWLING = "CRAWLING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"


# ============================================================================
#  Environment Enums
# ============================================================================

class Environment(str, Enum):
    """Deployment environment enumeration"""
    DEVELOPMENT = "dev"
    STAGING = "stg"
    PRODUCTION = "prod"

# ============================================================================
# Statistics Enums
# ============================================================================

class TimePeriod(str, Enum):
    """Time period for statistics grouping."""
    DAY = "day"
    MONTH = "month"
    YEAR = "year"


# ============================================================================
# Bot Worker Enums
# ============================================================================

class ScheduleType(str, Enum):
    """Bot worker schedule enumeration."""
    CRAWL = "crawl"
    VISITOR_EMAIL = "visitor_email"
    GRADING = "grading"


class Frequency(str, Enum):
    """Scheduling frequency options"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
