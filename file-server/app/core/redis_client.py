"""
Redis client for progress publishing
"""
import redis
import asyncio
from typing import Dict, Any
import json

from app.config.settings import settings
from app.core.redis_keys import RedisKeys
from app.utils.logging import get_logger

logger = get_logger(__name__)


class RedisClient:
    """
    Redis client for publishing progress updates
    """
    
    def __init__(self):
        self.client: redis.Redis = None
        
    def connect(self):
        """Connect to Redis server"""
        try:
            self.client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5
            )
            
            self.client.ping()
            
            logger.info(
                f"Connected to Redis: {settings.REDIS_HOST}:{settings.REDIS_PORT}",
                extra={"db": settings.REDIS_DB}
            )
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}", exc_info=True)
            raise
    
    def disconnect(self):
        """Close Redis connection"""
        if self.client:
            self.client.close()
            logger.info("Disconnected from Redis")
    
    async def publish_progress(self, task_id: str, data: Dict[str, Any]):
        """
        Publish progress update to Redis channel
        
        Args:
            task_id: Task ID
            data: Progress data (progress, status, message, etc.)
        """
        try:
            channel = RedisKeys.task_progress_channel(task_id)
            message = json.dumps(data)
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: self.client.publish(channel, message))
            
            logger.debug(
                f"Published progress to channel",
                extra={
                    "task_id": task_id,
                    "channel": channel,
                    "progress": data.get("progress")
                }
            )
            
        except Exception as e:
            logger.error(
                f"Failed to publish progress: {e}",
                extra={"task_id": task_id},
                exc_info=True
            )
    
    async def set_task_state(self, task_id: str, state: Dict[str, Any], ttl: int = None):
        """
        Set task state in Redis (for resume after refresh)
        
        Args:
            task_id: Task ID
            state: Task state data
            ttl: Time to live in seconds (default: PROGRESS_STATE_TTL from settings)
        """
        if ttl is None:
            ttl = settings.PROGRESS_STATE_TTL
        
        try:
            key = RedisKeys.task_state(task_id)
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: self.client.hset(key, mapping=state))
            await loop.run_in_executor(None, lambda: self.client.expire(key, ttl))
            
            logger.debug(
                f"Set task state",
                extra={"task_id": task_id, "ttl": ttl, "key": key}
            )
            
        except Exception as e:
            logger.error(
                f"Failed to set task state: {e}",
                extra={"task_id": task_id},
                exc_info=True
            )
    
    async def get_task_state(self, task_id: str) -> Dict[str, Any]:
        """
        Get task state from Redis
        
        Args:
            task_id: Task ID
            
        Returns:
            Task state dict
        """
        try:
            key = RedisKeys.task_state(task_id)
            
            loop = asyncio.get_event_loop()
            state = await loop.run_in_executor(None, lambda: self.client.hgetall(key))
            
            return state
            
        except Exception as e:
            logger.error(
                f"Failed to get task state: {e}",
                extra={"task_id": task_id}
            )
            return {}
    
    async def exists(self, key: str) -> bool:
        """
        Check if key exists in Redis
        
        Args:
            key: Redis key
            
        Returns:
            True if key exists, False otherwise
        """
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lambda: self.client.exists(key))
            return bool(result)
            
        except Exception as e:
            logger.error(
                f"Failed to check key existence: {e}",
                extra={"key": key}
            )
            return False

    async def delete_task_state(self, task_id: str):
        """
        Delete task state from Redis (cleanup after task completion)
        
        Args:
            task_id: Task ID
        """
        try:
            key = RedisKeys.task_state(task_id)
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: self.client.delete(key))
            
            logger.debug(
                f"Deleted task state",
                extra={"task_id": task_id, "key": key}
            )
            
        except Exception as e:
            logger.error(
                f"Failed to delete task state: {e}",
                extra={"task_id": task_id},
                exc_info=True
            )
    
    async def close(self):
        """Close Redis connection"""
        if self.client:
            await asyncio.to_thread(self.client.close)


redis_client = RedisClient()