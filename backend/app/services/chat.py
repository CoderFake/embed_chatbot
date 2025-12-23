"""
Chat Service - Complete chat management
Handles: task queue, cancellation, state tracking, webhook processing, and session creation
"""
from __future__ import annotations

import json
import uuid
from typing import Dict, Optional

from fastapi import HTTPException, status


from aio_pika import Message, connect_robust
from aio_pika.abc import AbstractChannel, AbstractConnection
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.cache.keys import CacheKeys
from app.config.settings import settings
from app.models.visitor import ChatMessage, ChatSession
from app.models.usage import UsageLog
from app.common.enums import SessionStatus, TaskStatus
from app.schemas.chat import ChatAskRequest, TaskState
from app.schemas.webhook import ChatCompletionPayload
from app.services.visitor import VisitorService
from app.utils.datetime_utils import now
from app.core.database import redis_manager
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ChatService:
    """
    Centralized service for all chat operations:
    1. Session Management: Create new chat sessions
    2. Task Management: Create, publish, track tasks in RabbitMQ
    3. Cancellation: Cancel active tasks via Redis Pub/Sub
    4. State Management: Store/retrieve task state in Redis
    5. Webhook Processing: Handle chat completion from chat-worker
    """

    def __init__(self, db: Optional[AsyncSession] = None) -> None:
        self._connection: Optional[AbstractConnection] = None
        self._channel: Optional[AbstractChannel] = None
        self._redis: Optional[Redis] = None
        self._db = db

    # ========================================================================
    # Session Management
    # ========================================================================

    async def create_session(
        self, 
        bot_id: str, 
        ip_address: str, 
        db: AsyncSession,
        redis: Redis = None
    ) -> ChatSession:
        """
        Create a new chat session.
        
        Args:
            bot_id: Bot ID
            ip_address: Client IP address
            db: Database session
            redis: Redis client (optional, for caching)
            
        Returns:
            ChatSession: Created session with unique token
            
        Raises:
            HTTPException: If bot not found or creation fails
        """
        from app.services.bot import BotService
        
        bot_service = BotService(db, redis)
        bot = await bot_service.get_by_id(bot_id)
        if not bot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bot not found"
            )
        
        visitor_service = VisitorService(db)
        visitor = await visitor_service.find_or_create_visitor(
            bot_id=bot_id,
            ip_address=ip_address
        )
        
        session_token = str(uuid.uuid4())
        
        session = ChatSession(
            bot_id=bot_id,
            visitor_id=visitor.id,
            session_token=session_token,
            status=SessionStatus.ACTIVE,
            extra_data={}
        )
        db.add(session)
        
        try:
            await db.commit()
            await db.refresh(session)
        except Exception as e:
            await db.rollback()
            logger.error(
                f"Failed to create session in database: {str(e)}",
                extra={
                    "bot_id": bot_id,
                    "visitor_id": str(visitor.id),
                    "error": str(e)
                },
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create chat session"
            )
        
        logger.info(
            "Created new chat session",
            extra={
                "session_token": session_token,
                "visitor_id": str(visitor.id),
                "bot_id": bot_id,
                "ip_address": ip_address
            }
        )
        
        return session

    async def close_session(
        self,
        session_token: str,
        reason: Optional[str],
        duration_seconds: Optional[int],
        db: AsyncSession
    ) -> ChatSession:
        """
        Close a chat session.
        
        Args:
            session_token: Session token to close
            reason: Reason for closing (user_closed, timeout, etc.)
            duration_seconds: Total session duration in seconds
            db: Database session
            
        Returns:
            ChatSession: Closed session
            
        Raises:
            HTTPException: If session not found
        """
        
        stmt = select(ChatSession).where(ChatSession.session_token == session_token)
        result = await db.execute(stmt)
        session = result.scalar_one_or_none()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session not found: {session_token}"
            )
        
        if session.status == SessionStatus.CLOSED:
            logger.warning(
                "Attempted to close already closed session",
                extra={"session_id": str(session.id), "session_token": session_token}
            )
            return session
        
        session.status = SessionStatus.CLOSED
        session.ended_at = now()
        
        if reason or duration_seconds:
            extra_data = session.extra_data or {}
            if reason:
                extra_data["close_reason"] = reason
            if duration_seconds:
                extra_data["duration_seconds"] = duration_seconds
            session.extra_data = extra_data
        
        try:
            await db.commit()
            await db.refresh(session)
        except Exception as e:
            await db.rollback()
            logger.error(
                "Failed to close session in database",
                extra={"session_token": session_token, "error": str(e)},
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to close session"
            )
        
        logger.info(
            "Session closed",
            extra={
                "session_id": str(session.id),
                "visitor_id": str(session.visitor_id),
                "session_token": session_token,
                "reason": reason,
                "duration": duration_seconds,
            }
        )
        
        return session

    async def get_session_status(
        self,
        session_token: str,
        db: AsyncSession
    ) -> ChatSession:
        """
        Get current status of a chat session.
        
        Args:
            session_token: Session token to query
            db: Database session
            
        Returns:
            ChatSession: Session object
            
        Raises:
            HTTPException: If session not found
        """
        
        stmt = select(ChatSession).where(ChatSession.session_token == session_token)
        result = await db.execute(stmt)
        session = result.scalar_one_or_none()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session not found: {session_token}"
            )
        
        return session
    
    async def get_session_by_token(
        self,
        session_token: str,
        db: AsyncSession
    ) -> Optional[ChatSession]:
        """
        Get session by token (for widget API).
        
        Args:
            session_token: Session token to query
            db: Database session
            
        Returns:
            ChatSession or None if not found
        """
        stmt = select(ChatSession).where(ChatSession.session_token == session_token)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    # ========================================================================
    # RabbitMQ Connection
    # ========================================================================

    async def connect(self) -> None:
        """Connect to RabbitMQ queue."""
        if self._connection:
            return
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
            self._redis = redis_manager.get_redis()
        return self._redis

    # ========================================================================
    # Task Management
    # ========================================================================

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
        visitor_profile = await visitor_service.get_visitor_profile_by_session(request.session_token)
        long_term_memory = visitor_profile.pop("long_term_memory", None)
        
        logger.info(
            "Retrieved visitor profile for chat task",
            extra={
                "session_token": request.session_token,
                "has_visitor_profile": bool(visitor_profile),
                "visitor_profile_keys": list(visitor_profile.keys()) if visitor_profile else [],
                "visitor_profile": visitor_profile,
                "has_long_term_memory": bool(long_term_memory),
                "long_term_memory_preview": long_term_memory[:200] if long_term_memory and len(long_term_memory) > 200 else long_term_memory,
            }
        )

        task_state = TaskState(
            task_id=task_id,
            status=TaskStatus.QUEUED,
            query=request.query,
            bot_id=request.bot_id,
            session_token=request.session_token,
            conversation_history=request.conversation_history,
            visitor_profile=visitor_profile,
            long_term_memory=long_term_memory,
            created_at=now(),
            updated_at=now(),
        )

        await self._store_state(redis, task_state)
        await self._publish_queued_event(redis, task_id)
        
        await self._publish_task(task_state)

        logger.info("Created chat task", extra={"task_id": task_id})
        return task_id

    async def _publish_queued_event(self, redis: Redis, task_id: str) -> None:
        """Publish initial queued event to SSE channel."""
        stream_key = CacheKeys.task_progress_channel(task_id)
        event_data = {
            "task_id": task_id,
            "status": "queued",
            "timestamp": now().isoformat(),
        }
        await redis.publish(stream_key, json.dumps(event_data))
        logger.info(f"Published queued event for task", extra={"task_id": task_id})

    async def _store_state(self, redis: Redis, task_state: TaskState) -> None:
        """Store task state in Redis."""
        key = CacheKeys.task_state(task_state.task_id)
        await redis.setex(key, settings.CHAT_TASK_TTL, task_state.model_dump_json())

    async def _publish_task(self, task_state: TaskState) -> None:
        """Publish task to RabbitMQ."""
        await self.connect()
        assert self._channel is not None

        logger.info(
            "Publishing chat task to RabbitMQ",
            extra={
                "task_id": task_state.task_id,
                "bot_id": task_state.bot_id,
                "session_token": task_state.session_token,
                "has_visitor_profile": bool(task_state.visitor_profile),
                "visitor_profile": task_state.visitor_profile,
                "has_long_term_memory": bool(task_state.long_term_memory),
                "long_term_memory_preview": task_state.long_term_memory[:200] if task_state.long_term_memory and len(task_state.long_term_memory) > 200 else task_state.long_term_memory,
            }
        )

        payload = {
            "task_id": task_state.task_id,
            "query": task_state.query,
            "bot_id": task_state.bot_id,
            "session_token": task_state.session_token,
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

    # ========================================================================
    # Task Cancellation
    # ========================================================================

    async def cancel_session_tasks(self, session_token: str) -> bool:
        """
        Cancel all active tasks for a session.
        
        Publishes a cancel message to Redis Pub/Sub channel that chat-worker monitors.
        The chat-worker will cancel any in-progress tasks for this session.
        
        Args:
            session_token: Session token (UUID string) to cancel tasks for
            
        Returns:
            True if cancel signal was sent successfully
        """
        try:
            redis = await self._get_redis()
            cancel_channel = CacheKeys.task_cancel_channel(session_token)
            
            message = {
                "action": "cancel",
                "session_token": session_token,
                "reason": "session_closed"
            }
            
            await redis.publish(cancel_channel, json.dumps(message))
            
            logger.info(
                "Published cancel signal for session",
                extra={"session_token": session_token, "channel": cancel_channel}
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Failed to publish cancel signal",
                extra={"session_token": session_token, "error": str(e)},
                exc_info=True
            )
            return False


chat_service = ChatService()
