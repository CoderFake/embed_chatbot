"""Redis client for visitor grader service."""
from redis.asyncio import Redis, ConnectionPool

from app.config.settings import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class RedisClient:
    """
    Redis client manager.
    
    Responsible for connection lifecycle only.
    For cache and Pub/Sub operations, use CacheService.
    """
    
    def __init__(self):
        self.pool: ConnectionPool | None = None
        self.client: Redis | None = None
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize Redis connection."""
        if self._initialized:
            return
        
        try:
            self.pool = ConnectionPool.from_url(
                settings.REDIS_URL,
                max_connections=10,
                decode_responses=True,
            )
            
            self.client = Redis(connection_pool=self.pool)
            await self.client.ping()
            
            self._initialized = True
            logger.info("Redis connection initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize Redis: {e}", exc_info=True)
            raise
    
    async def cleanup(self) -> None:
        """Cleanup Redis connections."""
        if self.client:
            await self.client.aclose()
            self.client = None
        
        if self.pool:
            await self.pool.disconnect()
            self.pool = None
        
        self._initialized = False
        logger.info("Redis connections cleaned up")
    
    def get_client(self) -> Redis:
        """
        Get Redis client.
        
        Returns:
            Redis client instance
            
        Raises:
            RuntimeError: If Redis not initialized
        """
        if not self.client:
            raise RuntimeError("Redis not initialized")
        return self.client


# Global instance
redis_client = RedisClient()
