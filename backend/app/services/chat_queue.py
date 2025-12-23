"""Chat queue publisher service for managing chat tasks."""
from __future__ import annotations

import asyncio
import json
import uuid
from typing import Dict, Optional

from aio_pika import Message, connect_robust
from aio_pika.abc import AbstractChannel, AbstractConnection
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.keys import CacheKeys
from app.config.settings import settings
from app.common.enums import TaskStatus
from app.schemas.chat import ChatAskRequest, TaskState
from app.services.visitor import VisitorService
from app.utils.datetime_utils import now
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ChatQueueService:
    """
    Service for managing chat tasks: publish, cancel, and track state.
    Handles both RabbitMQ task publishing and Redis Pub/Sub cancellation.
    """

    def __init__(self) -> None:
        self._connection: Optional[AbstractConnection] = None
        self._channel: Optional[AbstractChannel] = None
        self._redis: Optional[Redis] = None

    async def connect(self, max_retries: int = 5, retry_delay: int = 2) -> None:
        """
        Connect to RabbitMQ queue with retry logic.
        
        Args:
            max_retries: Maximum number of connection attempts
            retry_delay: Delay in seconds between retries
        """
        if self._connection:
            return
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(
                    f"Attempting to connect to RabbitMQ (attempt {attempt}/{max_retries})",
                    extra={"rabbitmq_url": settings.RABBITMQ_URL.split('@')[-1]}  # Hide credentials
                )
                self._connection = await connect_robust(settings.RABBITMQ_URL)
                self._channel = await self._connection.channel()
                await self._channel.declare_queue(
                    settings.CHAT_QUEUE_NAME,
                    durable=True,
                    arguments={
                        "x-max-length": settings.MAX_CONCURRENT_TASKS,
                        "x-overflow": "reject-publish",
                    },
                )
                logger.info("Connected to RabbitMQ queue", extra={"queue": settings.CHAT_QUEUE_NAME})
                return
            except Exception as e:
                logger.warning(
                    f"Failed to connect to RabbitMQ (attempt {attempt}/{max_retries}): {e}",
                    extra={"error": str(e)}
                )
                if attempt < max_retries:
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error("Failed to connect to RabbitMQ after all retries")
                    raise

    async def disconnect(self) -> None:
        """Disconnect from RabbitMQ."""
        if self._channel:
            await self._channel.close()
            self._channel = None
        if self._connection:
            await self._connection.close()
            self._connection = None
        logger.info("Disconnected from RabbitMQ queue")
    
    async def _get_redis(self) -> Redis:
        """Get Redis connection lazily."""
        if self._redis is None:
            from app.core.database import redis_manager
            self._redis = redis_manager.get_redis()
        return self._redis

    async def create_task(self, request: ChatAskRequest, db: AsyncSession, redis: Redis) -> str:
        """
        Create and publish a new chat task to RabbitMQ queue.
        
        Args:
            request: Chat request with query, bot_id, session_id
            db: Database session
            redis: Redis connection
            
        Returns:
            task_id: UUID of created task
        """
        task_id = str(uuid.uuid4())

        visitor_service = VisitorService(db)
        visitor_profile = await visitor_service.get_visitor_profile_by_session(request.session_id)
        long_term_memory = visitor_profile.pop("long_term_memory", None)

        task_state = TaskState(
            task_id=task_id,
            status=TaskStatus.QUEUED,
            query=request.query,
            bot_id=request.bot_id,
            session_id=request.session_id,
            conversation_history=request.conversation_history,
            visitor_profile=visitor_profile,
            long_term_memory=long_term_memory,
            created_at=now(),
            updated_at=now(),
        )

        await self._store_state(redis, task_state)
        await self._publish_task(task_state)

        logger.info("Created chat task", extra={"task_id": task_id})
        return task_id

    async def _store_state(self, redis: Redis, task_state: TaskState) -> None:
        """Store task state in Redis."""
        key = CacheKeys.task_state(task_state.task_id)
        await redis.setex(key, settings.CHAT_TASK_TTL, task_state.model_dump_json())

    async def _publish_task(self, task_state: TaskState) -> None:
        """Publish task to RabbitMQ."""
        await self.connect()
        assert self._channel is not None

        payload = {
            "task_id": task_state.task_id,
            "query": task_state.query,
            "bot_id": task_state.bot_id,
            "session_id": task_state.session_id,
            "conversation_history": task_state.conversation_history,
            "visitor_profile": task_state.visitor_profile,
            "long_term_memory": task_state.long_term_memory,
            "created_at": task_state.created_at.isoformat(),
        }

        message = Message(
            body=json.dumps(payload).encode("utf-8"),
            content_type="application/json",
            delivery_mode=2,
            message_id=task_state.task_id,
            timestamp=now(),
        )

        await self._channel.default_exchange.publish(message, routing_key=settings.CHAT_QUEUE_NAME)
        logger.debug("Published chat task", extra={"task_id": task_state.task_id})

    async def cancel_session_tasks(self, session_id: str) -> bool:
        """
        Cancel all active tasks for a session.
        
        Publishes a cancel message to Redis Pub/Sub channel that chat-worker monitors.
        The chat-worker will cancel any in-progress tasks for this session.
        
        Args:
            session_id: Session ID to cancel tasks for
            
        Returns:
            True if cancel signal was sent successfully
        """
        try:
            redis = await self._get_redis()
            cancel_channel = CacheKeys.task_cancel_channel(session_id)
            
            message = {
                "action": "cancel",
                "session_id": session_id,
                "reason": "session_closed"
            }
            
            await redis.publish(cancel_channel, json.dumps(message))
            
            logger.info(
                "Published cancel signal for session",
                extra={"session_id": session_id, "channel": cancel_channel}
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Failed to publish cancel signal",
                extra={"session_id": session_id, "error": str(e)},
                exc_info=True
            )
            return False

    async def get_task_state(self, task_id: str, redis: Redis) -> Optional[TaskState]:
        """Get task state from Redis."""
        key = CacheKeys.task_state(task_id)
        data = await redis.get(key)
        if not data:
            return None
        return TaskState.model_validate_json(data)

    async def update_task_status(
        self,
        task_id: str,
        *,
        status: TaskStatus,
        redis: Redis,
        error: str | None = None,
        result: Dict | None = None,
    ) -> None:
        """Update task status in Redis."""
        state = await self.get_task_state(task_id, redis)
        if not state:
            logger.warning("Task not found when updating", extra={"task_id": task_id})
            return

        state.status = status
        state.updated_at = now()

        if status == TaskStatus.COMPLETED:
            state.completed_at = now()
            state.result = result
        elif status == TaskStatus.FAILED:
            state.error = error

        await self._store_state(redis, state)


chat_queue_service = ChatQueueService()
