"""
Retry logic for handling transient failures
"""
import asyncio
from typing import TypeVar, Callable, Any
from functools import wraps

from app.config.settings import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


def retry_on_error(
    max_retries: int = None,
    retry_delays: list[int] = None,
    exceptions: tuple = (Exception,)
):
    """
    Decorator for retrying function on error with exponential backoff
    
    Args:
        max_retries: Maximum number of retries (default from settings)
        retry_delays: List of delays in seconds (default from settings)
        exceptions: Tuple of exceptions to catch
    """
    if max_retries is None:
        max_retries = settings.MAX_RETRIES
    if retry_delays is None:
        retry_delays = settings.RETRY_DELAYS
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                    
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_retries - 1:
                        delay = retry_delays[min(attempt, len(retry_delays) - 1)]
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries} failed: {e}. "
                            f"Retrying in {delay}s...",
                            extra={
                                "function": func.__name__,
                                "attempt": attempt + 1,
                                "max_retries": max_retries,
                                "delay": delay
                            }
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"All {max_retries} attempts failed for {func.__name__}",
                            extra={
                                "function": func.__name__,
                                "error": str(e)
                            },
                            exc_info=True
                        )
            
            raise last_exception
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                    
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_retries - 1:
                        delay = retry_delays[min(attempt, len(retry_delays) - 1)]
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries} failed: {e}. "
                            f"Retrying in {delay}s..."
                        )
                        import time
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"All {max_retries} attempts failed for {func.__name__}",
                            exc_info=True
                        )
            
            raise last_exception
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator
