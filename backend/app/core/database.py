from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker
)
from redis.asyncio import Redis, ConnectionPool

from app.config.settings import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class DatabaseManager:
    """
    PostgreSQL database connection manager with async support.
    """
    
    def __init__(self):
        self.engine: Optional[AsyncEngine] = None
        self.session_factory: Optional[async_sessionmaker[AsyncSession]] = None
    
    async def connect(self) -> None:
        """
        Initialize database connection pool.
        """
        try:
            self.engine = create_async_engine(
                settings.DATABASE_URL,
                echo=settings.DB_ECHO,
                pool_size=settings.DB_POOL_SIZE,
                max_overflow=settings.DB_MAX_OVERFLOW,
                pool_timeout=settings.DB_POOL_TIMEOUT,
                pool_recycle=settings.DB_POOL_RECYCLE,
                pool_pre_ping=True,
            )
            
            self.session_factory = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
                autocommit=False,
            )
            
            logger.info("Database connection pool initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize database connection: {e}")
            raise
    
    async def disconnect(self) -> None:
        """
        Close database connections.
        """
        if self.engine:
            await self.engine.dispose()
            logger.info("Database connection pool closed")
    
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get database session for dependency injection.
        This is an async generator for FastAPI Depends() usage.
        
        Yields:
            AsyncSession: Database session
        """
        if not self.session_factory:
            raise RuntimeError("Database not initialized. Call connect() first.")
        
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get database session as async context manager.
        Use this in background tasks with 'async with db_manager.session() as db:'
        
        Yields:
            AsyncSession: Database session
        """
        if not self.session_factory:
            raise RuntimeError("Database not initialized. Call connect() first.")
        
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()


class RedisManager:
    """
    Redis connection manager with connection pooling.
    """
    
    def __init__(self):
        self.pool: Optional[ConnectionPool] = None
        self.redis: Optional[Redis] = None
    
    async def connect(self) -> None:
        """
        Initialize Redis connection pool.
        """
        try:
            redis_url = settings.REDIS_URL
            if not redis_url:
                auth_part = f":{settings.REDIS_PASSWORD}@" if settings.REDIS_PASSWORD else ""
                redis_url = f"redis://{auth_part}{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
            
            self.pool = ConnectionPool.from_url(
                redis_url,
                max_connections=settings.REDIS_MAX_CONNECTIONS,
                socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
                socket_connect_timeout=settings.REDIS_SOCKET_CONNECT_TIMEOUT,
                decode_responses=True,  
                encoding="utf-8",
            )
            
            self.redis = Redis(connection_pool=self.pool)
            
            await self.redis.ping()
            
            logger.info("Redis connection pool initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Redis connection: {e}")
            raise
    
    async def disconnect(self) -> None:
        """
        Close Redis connections.
        """
        if self.redis:
            await self.redis.aclose()
            logger.info("Redis connection closed")
        
        if self.pool:
            await self.pool.disconnect()
            logger.info("Redis connection pool closed")
    
    def get_redis(self) -> Redis:
        """
        Get Redis client instance.
        
        Returns:
            Redis: Redis client
            
        Raises:
            RuntimeError: If Redis not initialized
        """
        if not self.redis:
            raise RuntimeError("Redis not initialized. Call connect() first.")
        return self.redis


db_manager = DatabaseManager()
redis_manager = RedisManager()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting database session.
    
    Usage:
        @app.get("/users")
        async def get_users(db: AsyncSession = Depends(get_db)):
            ...
    """
    async for session in db_manager.get_session():
        yield session


def get_redis() -> Redis:
    """
    Dependency for getting Redis client.
    
    Usage:
        @app.get("/cached")
        async def get_cached(redis: Redis = Depends(get_redis)):
            ...
    """
    return redis_manager.get_redis()

