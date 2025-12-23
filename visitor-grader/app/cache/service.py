"""
Generic Redis cache service with common operations.
Provides reusable cache methods following backend's architecture.
"""

from typing import Optional, Any
import json
from redis.asyncio import Redis

from app.utils.logging import get_logger

logger = get_logger(__name__)


class CacheService:
    """
    Generic Redis cache service with common operations.
    Follows the same pattern as backend's CacheService.
    """
    
    def __init__(self, redis: Redis):
        self.redis = redis
    
    async def get(self, key: str, as_json: bool = True) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            as_json: If True, deserialize as JSON, else return raw string
            
        Returns:
            Cached value or None if not found
        """
        try:
            value = await self.redis.get(key)
            if value is None:
                return None
            
            if as_json:
                return json.loads(value)
            return value
            
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: int,
        as_json: bool = True
    ) -> bool:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
            as_json: If True, serialize as JSON, else store as string
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if as_json:
                serialized_value = json.dumps(value, ensure_ascii=False, default=str)
            else:
                serialized_value = value
            
            await self.redis.setex(key, ttl, serialized_value)
            return True
            
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """
        Delete key from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if deleted, False otherwise
        """
        try:
            await self.redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False
    
    async def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching pattern.
        
        Args:
            pattern: Key pattern (e.g., "bot:*")
            
        Returns:
            Number of keys deleted
        """
        try:
            deleted = 0
            cursor = 0
            
            while True:
                cursor, keys = await self.redis.scan(
                    cursor=cursor,
                    match=pattern,
                    count=100
                )
                
                if keys:
                    await self.redis.delete(*keys)
                    deleted += len(keys)
                
                if cursor == 0:
                    break
            
            logger.info(f"Deleted {deleted} keys matching pattern: {pattern}")
            return deleted
            
        except Exception as e:
            logger.error(f"Cache delete pattern error for {pattern}: {e}")
            return 0
    
    async def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if exists, False otherwise
        """
        try:
            result = await self.redis.exists(key)
            return result > 0
        except Exception as e:
            logger.error(f"Cache exists error for key {key}: {e}")
            return False
    
    async def expire(self, key: str, ttl: int) -> bool:
        """
        Set expiration time for a key.
        
        Args:
            key: Cache key
            ttl: Time to live in seconds
            
        Returns:
            True if successful, False otherwise
        """
        try:
            await self.redis.expire(key, ttl)
            return True
        except Exception as e:
            logger.error(f"Cache expire error for key {key}: {e}")
            return False
    
    async def publish(self, channel: str, data: Any, as_json: bool = True) -> bool:
        """
        Publish message to Redis Pub/Sub channel.
        
        Args:
            channel: Channel name
            data: Data to publish
            as_json: If True, serialize as JSON, else publish as string
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if as_json:
                message = json.dumps(data, ensure_ascii=False, default=str)
            else:
                message = data
            
            await self.redis.publish(channel, message)
            logger.debug(f"Published to channel: {channel}")
            return True
            
        except Exception as e:
            logger.error(f"Publish error for channel {channel}: {e}")
            return False
