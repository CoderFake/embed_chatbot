"""Datetime utilities with timezone support."""
from datetime import datetime, timezone
import pytz
from typing import Optional

from app.config.settings import settings


def get_timezone():
    """
    Get application timezone from settings.
    
    Returns:
        pytz timezone object
    """
    return pytz.timezone(settings.TIMEZONE)


def now() -> datetime:
    """
    Get current datetime in application timezone.
    
    Returns:
        Current datetime with timezone
    """
    tz = get_timezone()
    return datetime.now(tz)


def utcnow() -> datetime:
    """
    Get current UTC datetime.
    
    Returns:
        Current UTC datetime
    """
    return datetime.now(timezone.utc)


def to_timezone(dt: datetime, tz: Optional[str] = None) -> datetime:
    """
    Convert datetime to specific timezone.
    
    Args:
        dt: Datetime to convert
        tz: Target timezone (default: application timezone from settings)
        
    Returns:
        Datetime in target timezone
    """
    target_tz = pytz.timezone(tz) if tz else get_timezone()
    
    if dt.tzinfo is None:
        # Assume UTC if naive datetime
        dt = pytz.utc.localize(dt)
    
    return dt.astimezone(target_tz)
