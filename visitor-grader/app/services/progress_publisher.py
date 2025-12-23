"""Progress publisher for real-time grading progress updates."""
import asyncio
import time
from typing import Optional

from app.core.redis_client import redis_client
from app.cache import CacheService, CacheKeys
from app.config.settings import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ProgressPublisher:
    """
    Publishes grading/assessment progress updates to Redis Pub/Sub.
    
    Similar to file-server's ProgressPublisher but for visitor grading tasks.
    """
    
    def __init__(self, task_id: str, task_type: str = "grading"):
        self.task_id = task_id
        self.task_type = task_type
        self.channel = CacheKeys.task_progress_channel(task_id)
        self.cache = CacheService(redis_client.get_client())
        self._last_progress = 0.0
        self._last_update_time = 0.0
        self._min_delta = settings.PROGRESS_MIN_DELTA
        self._min_interval = settings.PROGRESS_UPDATE_INTERVAL
    
    async def publish(
        self,
        progress: float,
        status: str,
        message: str,
        details: Optional[dict] = None,
        force: bool = False
    ) -> None:
        """
        Publish progress update.
        
        Args:
            progress: Progress percentage (0-100)
            status: Status (PROCESSING, COMPLETED, FAILED)
            message: Human-readable message
            details: Additional details
            force: Force publish even if delta/interval checks fail
        """
        current_time = time.time()
        
        delta = abs(progress - self._last_progress)
        time_elapsed = current_time - self._last_update_time
        
        should_publish = (
            force or
            delta >= self._min_delta or
            time_elapsed >= self._min_interval or
            progress == 0 or
            progress == 100
        )
        
        if not should_publish:
            return
        
        payload = {
            "task_id": self.task_id,
            "progress": round(progress, 2),
            "status": status,
            "message": message,
            "timestamp": current_time
        }
        
        if details:
            payload["details"] = details
        
        try:
            await self.cache.publish(self.channel, payload, as_json=True)
            self._last_progress = progress
            self._last_update_time = current_time
            
            logger.debug(
                "Published progress",
                extra={
                    "task_id": self.task_id,
                    "progress": progress,
                    "status": status,
                    "message": message
                }
            )
        except Exception as e:
            logger.warning(
                f"Failed to publish progress: {e}",
                extra={"task_id": self.task_id}
            )
    
    async def start(self) -> None:
        """Mark task as started."""
        message = f"Starting visitor {self.task_type}"
        await self.publish(0, "PROCESSING", message, force=True)
    
    async def complete(self, message: str = None) -> None:
        """Mark task as completed and cleanup task state."""
        if not message:
            message = f"{self.task_type.capitalize()} completed"
        await self.publish(100, "COMPLETED", message, force=True)
        
        try:
            task_state_key = CacheKeys.task_state(self.task_id)
            await self.cache.delete(task_state_key)
            logger.debug("Cleaned up task state", extra={"task_id": self.task_id})
        except Exception as e:
            logger.warning(
                f"Failed to cleanup task state: {e}",
                extra={"task_id": self.task_id}
            )
    
    async def fail(self, error: str) -> None:
        """Mark task as failed and cleanup task state."""
        await self.publish(
            self._last_progress,
            "FAILED",
            f"{self.task_type.capitalize()} failed: {error}",
            force=True
        )
        
        try:
            task_state_key = CacheKeys.task_state(self.task_id)
            await self.cache.delete(task_state_key)
            logger.debug("Cleaned up task state", extra={"task_id": self.task_id})
        except Exception as e:
            logger.warning(
                f"Failed to cleanup task state: {e}",
                extra={"task_id": self.task_id}
            )
