"""
Background service to listen for task progress updates from file-server
and update task notifications in real-time.
"""
import asyncio
import json
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import db_manager, redis_manager
from app.services.notification import NotificationService
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ProgressListenerService:
    """
    Listens to Redis pub/sub channels for task progress updates
    and updates task notifications in real-time.
    """
    
    def __init__(self):
        self.listener_task: Optional[asyncio.Task] = None
        self._running = False
    
    async def start(self):
        """Start the progress listener background task."""
        if self._running:
            logger.warning("Progress listener already running")
            return
        
        self._running = True
        self.listener_task = asyncio.create_task(self._listen_loop())
        logger.info("Progress listener service started")
    
    async def stop(self):
        """Stop the progress listener background task."""
        self._running = False
        
        if self.listener_task:
            self.listener_task.cancel()
            try:
                await self.listener_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Progress listener service stopped")
    
    async def _listen_loop(self):
        """Main loop that subscribes to progress channels and processes events."""
        redis = redis_manager.get_redis()
        
        try:
            pubsub = redis.pubsub()
            await pubsub.psubscribe("progress:*")
            
            logger.info("Subscribed to Redis progress channels (progress:*)")
            
            while self._running:
                try:
                    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    
                    if message and message["type"] == "pmessage":
                        await self._handle_progress_message(message)
                        
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error processing progress message: {e}", exc_info=True)
                    await asyncio.sleep(0.1)
            
            await pubsub.punsubscribe("progress:*")
            await pubsub.close()
            
        except asyncio.CancelledError:
            logger.info("Progress listener cancelled")
        except Exception as e:
            logger.error(f"Progress listener error: {e}", exc_info=True)
    
    async def _handle_progress_message(self, message: dict):
        """
        Handle a single progress message from Redis.
        
        Args:
            message: Redis pub/sub message with progress data
        """
        try:
            channel = message["channel"]
            if isinstance(channel, bytes):
                channel = channel.decode("utf-8")
            
            task_id = channel.replace("progress:", "")

            data_raw = message["data"]
            if isinstance(data_raw, bytes):
                data_raw = data_raw.decode("utf-8")
            
            data = json.loads(data_raw)
            
            progress = data.get("progress", 0)
            status = data.get("status", "processing")
            msg = data.get("message", "")
            
            if status not in ["processing", "completed", "failed"]:
                return
            
            async with db_manager.session() as db:
                notification_service = NotificationService(db, redis_manager.get_redis())
                
                await notification_service.update_task_notification(
                    task_id=task_id,
                    progress=int(progress),
                    status=status,
                    message=msg if msg else None
                )
            
            logger.info(
                f"Updated notification for task {task_id}: {progress}% ({status})",
                extra={"task_id": task_id, "progress": progress, "status": status}
            )
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse progress message: {e}")
        except Exception as e:
            logger.error(f"Failed to handle progress message: {e}", exc_info=True)


# Singleton instance
progress_listener_service = ProgressListenerService()
