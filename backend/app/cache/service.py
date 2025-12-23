from typing import Optional, Any, List
import json
from redis.asyncio import Redis

from app.config.settings import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class CacheService:
    """
    Generic Redis cache service with common operations.
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
        ttl: Optional[int] = None,
        as_json: bool = True
    ) -> bool:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (default: CACHE_DEFAULT_TTL)
            as_json: If True, serialize as JSON, else store as string
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if as_json:
                serialized_value = json.dumps(value, ensure_ascii=False, default=str)
            else:
                serialized_value = value
            
            cache_ttl = ttl or settings.CACHE_DEFAULT_TTL
            await self.redis.setex(key, cache_ttl, serialized_value)
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
            pattern: Key pattern (e.g., "user:*")
            
        Returns:
            Number of keys deleted
        """
        try:
            cursor = 0
            deleted_count = 0
            
            while True:
                cursor, keys = await self.redis.scan(
                    cursor=cursor,
                    match=pattern,
                    count=100
                )
                
                if keys:
                    deleted_count += await self.redis.delete(*keys)
                
                if cursor == 0:
                    break
            
            logger.info(f"Deleted {deleted_count} keys matching pattern: {pattern}")
            return deleted_count
            
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
            return await self.redis.exists(key) > 0
        except Exception as e:
            logger.error(f"Cache exists check error for key {key}: {e}")
            return False
    
    async def expire(self, key: str, ttl: int) -> bool:
        """
        Set expiration time for key.
        
        Args:
            key: Cache key
            ttl: Time to live in seconds
            
        Returns:
            True if successful, False otherwise
        """
        try:
            return await self.redis.expire(key, ttl)
        except Exception as e:
            logger.error(f"Cache expire error for key {key}: {e}")
            return False
    
    async def ttl(self, key: str) -> int:
        """
        Get remaining TTL for key.
        
        Args:
            key: Cache key
            
        Returns:
            Remaining TTL in seconds, -1 if no expiration, -2 if key doesn't exist
        """
        try:
            return await self.redis.ttl(key)
        except Exception as e:
            logger.error(f"Cache TTL check error for key {key}: {e}")
            return -2
    
    async def incr(self, key: str, amount: int = 1) -> int:
        """
        Increment integer value.
        
        Args:
            key: Cache key
            amount: Amount to increment
            
        Returns:
            New value after increment
        """
        try:
            return await self.redis.incrby(key, amount)
        except Exception as e:
            logger.error(f"Cache increment error for key {key}: {e}")
            return 0
    
    async def decr(self, key: str, amount: int = 1) -> int:
        """
        Decrement integer value.
        
        Args:
            key: Cache key
            amount: Amount to decrement
            
        Returns:
            New value after decrement
        """
        try:
            return await self.redis.decrby(key, amount)
        except Exception as e:
            logger.error(f"Cache decrement error for key {key}: {e}")
            return 0
    
    async def get_many(self, keys: List[str], as_json: bool = True) -> dict:
        """
        Get multiple values from cache.
        
        Args:
            keys: List of cache keys
            as_json: If True, deserialize as JSON
            
        Returns:
            Dictionary mapping keys to values (None for missing keys)
        """
        try:
            if not keys:
                return {}
            
            values = await self.redis.mget(keys)
            result = {}
            
            for key, value in zip(keys, values):
                if value is None:
                    result[key] = None
                elif as_json:
                    try:
                        result[key] = json.loads(value)
                    except json.JSONDecodeError:
                        result[key] = value
                else:
                    result[key] = value
            
            return result
            
        except Exception as e:
            logger.error(f"Cache get_many error: {e}")
            return {key: None for key in keys}
    
    async def set_many(
        self,
        mapping: dict,
        ttl: Optional[int] = None,
        as_json: bool = True
    ) -> bool:
        """
        Set multiple key-value pairs.
        
        Args:
            mapping: Dictionary of key-value pairs
            ttl: Time to live in seconds
            as_json: If True, serialize as JSON
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not mapping:
                return True
            
            pipe = self.redis.pipeline()
            cache_ttl = ttl or settings.CACHE_DEFAULT_TTL
            
            for key, value in mapping.items():
                if as_json:
                    serialized_value = json.dumps(value, ensure_ascii=False, default=str)
                else:
                    serialized_value = value
                
                pipe.setex(key, cache_ttl, serialized_value)
            
            await pipe.execute()
            return True
            
        except Exception as e:
            logger.error(f"Cache set_many error: {e}")
            return False
    
    async def flush_db(self) -> bool:
        """
        Flush entire database (use with caution!).
        
        Returns:
            True if successful, False otherwise
        """
        try:
            await self.redis.flushdb()
            logger.warning("Cache database flushed")
            return True
        except Exception as e:
            logger.error(f"Cache flush error: {e}")
            return False
        