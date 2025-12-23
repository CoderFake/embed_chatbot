"""
Progress publisher - publishes progress updates to Redis with throttling
"""
from typing import Dict, Any, Optional
from enum import Enum
import asyncio
from datetime import datetime

from app.core.redis_client import RedisClient
from app.core.redis_keys import RedisKeys
from app.progress.throttle import ProgressThrottle
from app.config.settings import settings
from app.utils.logging import get_logger
from app.utils.datetime_utils import now

logger = get_logger(__name__)


class TaskStatus(str, Enum):
    """Task status enumeration"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ProgressPublisher:
    """
    Publishes task progress updates to Redis with throttling.
    
    Features:
    - Throttled progress updates (5% or 3s intervals)
    - State persistence in Redis for refresh-safe tracking
    - Automatic cleanup of completed tasks
    """
    
    def __init__(self, redis_client: RedisClient):
        """
        Initialize publisher
        
        Args:
            redis_client: Redis client for publishing
        """
        self.redis_client = redis_client
        self.throttle = ProgressThrottle(
            min_delta=settings.PROGRESS_MIN_DELTA,
            min_interval=settings.PROGRESS_MIN_INTERVAL
        )
    
    async def publish_progress(
        self,
        task_id: str,
        bot_id: str,
        progress: float,
        status: str,
        message: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        force: bool = False
    ):
        """
        Publish progress update with throttling

        Args:
            task_id: Unique task identifier
            bot_id: Bot ID
            progress: Progress percentage (0-100)
            status: Task status (string or TaskStatus enum)
            message: Status message
            metadata: Additional metadata
            force: Force publish regardless of throttle
        """
        status_str = status.value if isinstance(status, TaskStatus) else status

        if status_str in ["completed", "failed"]:
            force = True

        if not self.throttle.should_publish(task_id, progress, force):
            return

        progress_data = {
            "task_id": task_id,
            "bot_id": bot_id,
            "progress": round(progress, 2),
            "status": status_str,
            "message": message,
            "timestamp": now().isoformat()
        }
        
        if metadata:
            progress_data["metadata"] = metadata
        
        try:
            await self.redis_client.publish_progress(task_id, progress_data)
            
            await self.redis_client.set_task_state(
                task_id,
                {
                    "task_id": task_id,
                    "bot_id": bot_id,
                    "progress": str(round(progress, 2)),
                    "status": status_str,
                    "message": message,
                    "timestamp": now().isoformat()
                }
            )

            logger.debug(
                f"Published progress: task_id={task_id}, progress={progress}%, status={status_str}",
                extra={
                    "task_id": task_id,
                    "bot_id": bot_id,
                    "progress": progress,
                    "status": status_str
                }
            )
        
        except Exception as e:
            logger.error(
                f"Failed to publish progress: {e}",
                extra={
                    "task_id": task_id,
                    "bot_id": bot_id,
                    "error": str(e)
                }
            )
    
    async def publish_start(
        self,
        task_id: str,
        bot_id: str,
        task_type: str,
        total_items: int = 0
    ):
        """
        Publish task start event
        
        Args:
            task_id: Unique task identifier
            bot_id: Bot ID
            task_type: Type of task (e.g., 'file_upload', 'crawl')
            total_items: Total number of items to process
        """
        await self.publish_progress(
            task_id=task_id,
            bot_id=bot_id,
            progress=0.0,
            status=TaskStatus.PROCESSING,
            message=f"Started processing {task_type}",
            metadata={
                "task_type": task_type,
                "total_items": total_items
            },
            force=True
        )
    
    async def publish_completion(
        self,
        task_id: str,
        bot_id: str,
        success: bool = True,
        message: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Publish task completion event and cleanup task state
        
        Args:
            task_id: Unique task identifier
            bot_id: Bot ID
            success: Whether task completed successfully
            message: Completion message
            metadata: Additional metadata (e.g., inserted_count, failed_count)
        """
        status = TaskStatus.COMPLETED if success else TaskStatus.FAILED
        progress = 100.0 if success else 0.0
        
        await self.publish_progress(
            task_id=task_id,
            bot_id=bot_id,
            progress=progress,
            status=status,
            message=message or ("Processing completed" if success else "Processing failed"),
            metadata=metadata,
            force=True
        )
        
        await self.redis_client.delete_task_state(task_id)
        
        self.throttle.reset(task_id)
    
    async def get_task_state(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current task state from Redis
        
        Args:
            task_id: Unique task identifier
            
        Returns:
            Task state or None if not found
        """
        return await self.redis_client.get_task_state(task_id)