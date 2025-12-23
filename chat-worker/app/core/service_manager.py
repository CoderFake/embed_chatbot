"""
Service manager for chat worker - centralized initialization and cleanup.
Similar to backend's core/database.py pattern.
"""
from __future__ import annotations

import aio_pika
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from redis.asyncio import Redis, ConnectionPool

from app.config.settings import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ServiceManager:
    """
    Centralized service manager for chat worker.
    Handles all external service connections: Database, Redis, RabbitMQ.
    """

    def __init__(self):
        # Database
        self.db_engine = None
        self.db_session_maker: async_sessionmaker | None = None

        # Redis
        self.redis_pool: ConnectionPool | None = None
        self.redis_client: Redis | None = None

        # RabbitMQ
        self.rabbitmq_connection: aio_pika.Connection | None = None
        self.rabbitmq_channel: aio_pika.Channel | None = None

        self._initialized = False

    async def initialize(self) -> None:
        """Initialize all services."""
        if self._initialized:
            return

        try:
            await self._init_database()
            await self._init_redis()
            await self._init_rabbitmq()
            self._initialized = True
            logger.info("All services initialized successfully")

        except Exception as e:
            logger.error("Failed to initialize services", exc_info=e)
            await self.cleanup()
            raise

    async def cleanup(self) -> None:
        """Cleanup all services."""
        if self._initialized:
            await self._cleanup_rabbitmq()
            await self._cleanup_redis()
            await self._cleanup_database()
            self._initialized = False
            logger.info("All services cleaned up")

    async def _init_database(self) -> None:
        """Initialize database connection."""
        try:
            database_url = settings.DATABASE_URL
            if not database_url:
                database_url = (
                    f"postgresql+asyncpg://{settings.POSTGRES_USER}:"
                    f"{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:"
                    f"{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
                )

            self.db_engine = create_async_engine(
                database_url,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,
                pool_recycle=3600,
                echo=settings.DEBUG,
            )

            self.db_session_maker = async_sessionmaker(
                self.db_engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )

            logger.info("Database connection initialized")

        except Exception as e:
            logger.error("Failed to initialize database", exc_info=e)
            raise

    async def _cleanup_database(self) -> None:
        """Cleanup database connections."""
        if self.db_engine:
            await self.db_engine.dispose()
            self.db_engine = None
            self.db_session_maker = None
            logger.info("Database connections cleaned up")

    async def _init_redis(self) -> None:
        """Initialize Redis connection."""
        try:
            redis_url = settings.REDIS_URL
            if not redis_url:
                redis_url = "redis://redis:6379/0"
                logger.warning("REDIS_URL not set, using default: redis://redis:6379/0")

            self.redis_pool = ConnectionPool.from_url(
                redis_url,
                max_connections=50,
                decode_responses=True,
            )

            self.redis_client = Redis(connection_pool=self.redis_pool)
            await self.redis_client.ping()

            logger.info("Redis connection initialized", extra={"redis_url": redis_url.split("@")[-1]})

        except Exception as e:
            logger.error("Failed to initialize Redis", exc_info=e)
            raise

    async def _cleanup_redis(self) -> None:
        """Cleanup Redis connections."""
        if self.redis_client:
            await self.redis_client.aclose()
            self.redis_client = None

        if self.redis_pool:
            await self.redis_pool.disconnect()
            self.redis_pool = None

        logger.info("Redis connections cleaned up")

    async def _init_rabbitmq(self) -> None:
        """Initialize RabbitMQ connection."""
        try:
            self.rabbitmq_connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
            self.rabbitmq_channel = await self.rabbitmq_connection.channel()
            await self.rabbitmq_channel.set_qos(prefetch_count=settings.MAX_CONCURRENT_CHAT_TASKS)

            await self.rabbitmq_channel.declare_queue(
                settings.CHAT_QUEUE_NAME,
                durable=True,
                arguments={
                    "x-max-length": settings.CHAT_QUEUE_MAX_LENGTH,
                    "x-overflow": "reject-publish",
                },
            )

            logger.info("RabbitMQ connection initialized", extra={
                "prefetch_count": settings.MAX_CONCURRENT_CHAT_TASKS,
                "queue_name": settings.CHAT_QUEUE_NAME
            })

        except Exception as e:
            logger.error("Failed to initialize RabbitMQ", exc_info=e)
            raise

    async def _cleanup_rabbitmq(self) -> None:
        """Cleanup RabbitMQ connections."""
        if self.rabbitmq_channel:
            await self.rabbitmq_channel.close()
            self.rabbitmq_channel = None

        if self.rabbitmq_connection:
            await self.rabbitmq_connection.close()
            self.rabbitmq_connection = None

        logger.info("RabbitMQ connections cleaned up")

    async def get_db_session(self) -> AsyncSession:
        """Get database session."""
        if not self.db_session_maker:
            raise RuntimeError("Database not initialized")
        return self.db_session_maker()

    def get_redis(self) -> Redis:
        """Get Redis client."""
        if not self.redis_client:
            raise RuntimeError("Redis not initialized")
        return self.redis_client

    def get_rabbitmq_channel(self) -> aio_pika.Channel:
        """Get RabbitMQ channel."""
        if not self.rabbitmq_channel:
            raise RuntimeError("RabbitMQ not initialized")
        return self.rabbitmq_channel


service_manager = ServiceManager()
