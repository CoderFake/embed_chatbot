"""Service for managing visitor and chat session data."""
from __future__ import annotations

import json
import uuid
import asyncio
import time
from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, cast
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.dialects.postgresql import INET
from uuid import UUID
import pika
from pika.exceptions import (
    AMQPConnectionError,
    StreamLostError, 
    ChannelWrongStateError
)

from app.models.visitor import Visitor, ChatSession, ChatMessage
from app.models.bot import Bot
from app.services.notification import NotificationService
from app.config.settings import settings
from app.cache.keys import CacheKeys
from app.core.database import redis_manager
from app.utils.logging import get_logger
from app.utils.datetime_utils import now

logger = get_logger(__name__)


class VisitorService:
    """Centralized service for managing visitors and sessions."""
    
    REQUIRED_FIELDS = ["name", "email", "phone"]
    GRADING_LOCK_TTL = 300
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def find_or_create_visitor(
        self, 
        bot_id: str, 
        ip_address: str,
        extra_data: Optional[Dict[str, Any]] = None
    ) -> Visitor:
        """
        Find existing visitor by bot_id + ip_address, or create new one.
        Same IP for the same bot = same visitor (don't duplicate).
        """
        
        stmt = select(Visitor).where(
            and_(
                Visitor.bot_id == bot_id,
                Visitor.ip_address == cast(ip_address, INET)
            )
        )
        result = await self.db.execute(stmt)
        visitor = result.scalars().first()
        
        if visitor:
            logger.info(
                "Found existing visitor",
                extra={"visitor_id": str(visitor.id), "ip": ip_address}
            )
            return visitor
        
        visitor = Visitor(
            bot_id=bot_id,
            ip_address=ip_address,
            lead_score=0,
            lead_assessment=extra_data or {}
        )
        self.db.add(visitor)
        await self.db.flush()
        
        logger.info(
            "Created new visitor",
            extra={"visitor_id": str(visitor.id), "ip": ip_address}
        )
        return visitor
    
    async def get_visitor_by_session(self, session_token: str) -> Optional[Visitor]:
        """Get visitor by session token - always get the LATEST session."""
        stmt = (
            select(ChatSession)
            .where(ChatSession.session_token == session_token)
            .options(selectinload(ChatSession.visitor))
            .order_by(ChatSession.started_at.desc())
        )
        result = await self.db.execute(stmt)
        session = result.scalars().first()
        
        return session.visitor if session else None

    async def get_visitor_profile_by_session(self, session_id: str) -> Dict[str, Any]:
        """
        Fetches the visitor profile associated with a given session token.
        This is used to send visitor profile to chat worker.
        Includes long_term_memory and is_contact from session extra_data.
        """
        if not session_id:
            return {}
        
        visitor = await self.get_visitor_by_session(session_id)
        
        if not visitor:
            return {}
        
        profile = {
            "id": str(visitor.id),
            "name": visitor.name,
            "email": visitor.email,
            "phone": visitor.phone,
            "address": visitor.address,
            "lead_score": visitor.lead_score,
        }
        
        stmt = (
            select(ChatSession)
            .where(ChatSession.session_token == session_id)
            .order_by(ChatSession.started_at.desc())
        )
        result = await self.db.execute(stmt)
        session = result.scalars().first()
        
        if session:
            profile["is_contact"] = session.is_contact
            
            if session.extra_data:
                long_term_memory = session.extra_data.get("long_term_memory")
                if long_term_memory:
                    profile["long_term_memory"] = long_term_memory
        else:
            profile["is_contact"] = False
        
        return profile
    
    def get_missing_fields(self, visitor_profile: Dict[str, Any]) -> list[str]:
        """Determine which required fields are still missing."""
        return [
            field for field in self.REQUIRED_FIELDS
            if not visitor_profile.get(field)
        ]
    
    async def update_visitor_info(
        self, 
        visitor_id: str, 
        validated_info: Dict[str, Any]
    ) -> bool:
        """
        Update visitor information with already-validated data from API layer.
        Updates fields if empty OR if new value is different from current value.
        
        Args:
            visitor_id: Visitor UUID
            validated_info: Pre-validated visitor data (validated by Pydantic schema in API layer)
            
        Returns:
            True if any field was updated, False otherwise
        """
        try:
            stmt = select(Visitor).where(Visitor.id == visitor_id)
            result = await self.db.execute(stmt)
            visitor = result.scalars().first()
            
            if not visitor:
                logger.warning(
                    "Visitor not found for update",
                    extra={"visitor_id": visitor_id}
                )
                return False
            
            if not validated_info:
                logger.info(
                    "No info to update",
                    extra={"visitor_id": visitor_id}
                )
                return False

            updated_fields = []
            for field_name, field_value in validated_info.items():
                if hasattr(visitor, field_name):
                    current_value = getattr(visitor, field_name)
                    if field_value and (not current_value or current_value != field_value):
                        setattr(visitor, field_name, field_value)
                        updated_fields.append(f"{field_name}: {current_value} → {field_value}")
            
            if updated_fields:
                await self.db.flush()
                logger.info(
                    "Updated visitor info",
                    extra={
                        "visitor_id": visitor_id,
                        "updated_fields": updated_fields
                    }
                )
                return True
            
            logger.debug(
                "No fields needed updating (all values same as current)",
                extra={"visitor_id": visitor_id}
            )
            return False
            
        except Exception as e:
            logger.error(
                "Failed to update visitor info",
                extra={"visitor_id": visitor_id},
                exc_info=e
            )
            return False
    
    async def create_or_find_session(
        self,
        bot_id: str,
        visitor_id: str,
        session_token: str,
        extra_data: Optional[Dict[str, Any]] = None
    ) -> ChatSession:
        """
        Find existing session by token or create new one.
        """
        stmt = (
            select(ChatSession)
            .where(ChatSession.session_token == session_token)
            .options(selectinload(ChatSession.visitor))
        )
        result = await self.db.execute(stmt)
        session = result.scalars().first()
        
        if session:
            if extra_data:
                session.extra_data = {**session.extra_data, **extra_data}
            return session
        
        session = ChatSession(
            bot_id=bot_id,
            visitor_id=visitor_id,
            session_token=session_token,
            extra_data=extra_data or {}
        )
        self.db.add(session)
        await self.db.flush()
        
        logger.info(
            "Created new chat session",
            extra={"session_token": session_token, "visitor_id": visitor_id}
        )
        return session
    
    async def trigger_lead_grading(
        self,
        visitor_id: str,
        bot_id: str,
        session_id: str,
        force: bool = False
    ) -> str:
        """
        Trigger visitor lead scoring/grading evaluation.
        
        Includes anti-spam protection - prevents re-grading same visitor within 5 minutes
        unless forced by admin.
        
        Fetches conversation history and visitor profile, then publishes to visitor-grader queue.
        
        Args:
            visitor_id: Visitor UUID to grade
            bot_id: Bot ID for context
            session_id: Session ID that just closed
            force: Skip lock check (admin manual trigger)
            
        Returns:
            task_id: UUID of grading task
            
        Raises:
            ValueError: If visitor not found or grading already in progress
        """
        lock_key = CacheKeys.grading_lock(visitor_id)
        redis_client = redis_manager.get_redis()
        
        if not force:
            existing_lock = await redis_client.get(lock_key)
            if existing_lock:
                remaining_ttl = await redis_client.ttl(lock_key)
                logger.warning(
                    "Grading already in progress for visitor",
                    extra={
                        "visitor_id": visitor_id,
                        "remaining_ttl": remaining_ttl,
                        "locked_by_task_id": existing_lock.decode() if existing_lock else None
                    }
                )
                raise ValueError(
                    f"Grading already in progress for visitor. "
                    f"Please wait {remaining_ttl} seconds before retrying."
                )
        
        task_id = str(uuid.uuid4())
        
        await redis_client.setex(
            lock_key,
            self.GRADING_LOCK_TTL,
            task_id
        )
        
        logger.info(
            "Set grading lock for visitor",
            extra={
                "visitor_id": visitor_id,
                "task_id": task_id,
                "ttl": self.GRADING_LOCK_TTL
            }
        )
        
        try:
            await asyncio.to_thread(
                self._publish_grading_task_blocking,
                task_id=task_id,
                visitor_id=visitor_id,
                bot_id=bot_id,
                session_id=session_id
            )
            return task_id
        except Exception as e:
            await redis_client.delete(lock_key)
            logger.error(
                "Failed to publish grading task, released lock",
                extra={"visitor_id": visitor_id, "task_id": task_id},
                exc_info=True
            )
            raise
    
    def _publish_grading_task_blocking(
        self,
        task_id: str,
        visitor_id: str,
        bot_id: str,
        session_id: str,
        priority: int = 3
    ) -> None:
        """
        Publish visitor grading task to RabbitMQ (BLOCKING).
        Only sends IDs - visitor-grader will query DB for data.
        
        Args:
            task_id: Pre-generated task UUID
            visitor_id: Visitor UUID
            bot_id: Bot ID
            session_id: Session ID that just closed
            priority: Task priority (0-5, higher = more priority)
        """
        max_retries = 3
        retry_delay = 1
        
        task_payload = {
            "task_id": task_id,
            "visitor_id": visitor_id,
            "bot_id": bot_id,
            "session_id": session_id
        }
        
        for attempt in range(max_retries):
            connection = None
            try:
                parameters = pika.URLParameters(settings.RABBITMQ_URL)
                parameters.socket_timeout = 5
                parameters.connection_attempts = 3
                parameters.retry_delay = 2
                
                connection = pika.BlockingConnection(parameters)
                channel = connection.channel()
                
                channel.queue_declare(
                    queue=settings.RABBITMQ_VISITOR_GRADER_QUEUE,
                    durable=True
                )
                
                channel.basic_publish(
                    exchange='',
                    routing_key=settings.RABBITMQ_VISITOR_GRADER_QUEUE,
                    body=json.dumps(task_payload),
                    properties=pika.BasicProperties(
                        delivery_mode=2,
                        content_type='application/json'
                    )
                )
                
                connection.close()
                
                logger.info(
                    "Published visitor grading task",
                    extra={
                        "task_id": task_id,
                        "visitor_id": visitor_id,
                        "bot_id": bot_id,
                        "session_id": session_id
                    }
                )
                
                return
                
            except (StreamLostError, ChannelWrongStateError, AMQPConnectionError) as e:
                if connection and not connection.is_closed:
                    connection.close()
                
                logger.warning(
                    f"RabbitMQ connection error (attempt {attempt + 1}/{max_retries}): {e}"
                )
                
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    logger.error(
                        f"Failed to publish grading task after {max_retries} attempts",
                        extra={"task_id": task_id, "visitor_id": visitor_id},
                        exc_info=True
                    )
                    raise
                    
            except Exception as e:
                if connection and not connection.is_closed:
                    connection.close()
                
                logger.error(
                    "Failed to publish grading task",
                    extra={"task_id": task_id, "visitor_id": visitor_id},
                    exc_info=True
                )
                raise

    async def trigger_visitor_assessment(
        self,
        visitor_id: str,
        bot_id: str,
        session_id: str,
        force: bool = False
    ) -> str:
        """
        Trigger visitor assessment using bot's assessment questions.
        
        Includes anti-spam protection - prevents re-assessment within 5 minutes
        unless forced by admin.
        
        Creates temporary Milvus collection from chat history,
        retrieves relevant context for each question, and uses LLM to answer.
        
        Args:
            visitor_id: Visitor UUID to assess
            bot_id: Bot ID (used to get assessment_questions)
            session_id: Session ID
            force: Skip lock check (admin manual trigger)
            
        Returns:
            task_id: UUID of assessment task
            
        Raises:
            ValueError: If bot has no assessment questions or assessment already in progress
        """
        lock_key = CacheKeys.assessment_lock(visitor_id)
        redis_client = redis_manager.get_redis()
        
        if not force:
            existing_lock = await redis_client.get(lock_key)
            if existing_lock:
                remaining_ttl = await redis_client.ttl(lock_key)
                logger.warning(
                    "Assessment already in progress for visitor",
                    extra={
                        "visitor_id": visitor_id,
                        "remaining_ttl": remaining_ttl,
                        "locked_by_task_id": existing_lock.decode() if existing_lock else None
                    }
                )
                raise ValueError(
                    f"Assessment already in progress for visitor. "
                    f"Please wait {remaining_ttl} seconds before retrying."
                )
        
        bot_uuid = UUID(bot_id) if isinstance(bot_id, str) else bot_id
        
        stmt = select(Bot).where(Bot.id == bot_uuid)
        result = await self.db.execute(stmt)
        bot = result.scalars().first()
        
        if not bot:
            raise ValueError(f"Bot not found: {bot_id}")
        
        if not bot.assessment_questions or len(bot.assessment_questions) == 0:
            raise ValueError(f"Bot {bot.name} has no assessment questions configured")
        
        task_id = str(uuid.uuid4())
        
        await redis_client.setex(
            lock_key,
            self.GRADING_LOCK_TTL,
            task_id
        )
        
        active_key = CacheKeys.assessment_active(visitor_id)
        await redis_client.setex(
            active_key,
            600, 
            task_id
        )
        
        logger.info(
            "Set assessment lock and active mapping for visitor",
            extra={
                "visitor_id": visitor_id,
                "bot_id": bot_id,
                "task_id": task_id,
                "ttl": self.GRADING_LOCK_TTL,
                "num_questions": len(bot.assessment_questions)
            }
        )
        
        try:
            await asyncio.to_thread(
                self._publish_assessment_task_blocking,
                task_id=task_id,
                visitor_id=visitor_id,
                bot_id=bot_id,
                session_id=session_id,
                assessment_questions=bot.assessment_questions
            )
            return task_id
        except Exception as e:
            await redis_client.delete(lock_key)
            logger.error(
                "Failed to publish assessment task, released lock",
                extra={"visitor_id": visitor_id, "task_id": task_id},
                exc_info=True
            )
            raise
    
    def _publish_assessment_task_blocking(
        self,
        task_id: str,
        visitor_id: str,
        bot_id: str,
        session_id: str,
        assessment_questions: List[str]
    ) -> None:
        """
        Publish visitor assessment task to RabbitMQ (BLOCKING).
        
        Args:
            task_id: Pre-generated task UUID
            visitor_id: Visitor UUID
            bot_id: Bot ID
            session_id: Session ID
            assessment_questions: List of assessment questions
        """
        max_retries = 3
        retry_delay = 1
        
        task_payload = {
            "task_id": task_id,
            "task_type": "assessment",
            "visitor_id": visitor_id,
            "bot_id": bot_id,
            "session_id": session_id,
            "assessment_questions": assessment_questions
        }
        
        for attempt in range(max_retries):
            connection = None
            try:
                parameters = pika.URLParameters(settings.RABBITMQ_URL)
                parameters.socket_timeout = 5
                parameters.connection_attempts = 3
                parameters.retry_delay = 2
                
                connection = pika.BlockingConnection(parameters)
                channel = connection.channel()
                
                channel.queue_declare(
                    queue=settings.RABBITMQ_VISITOR_GRADER_QUEUE,
                    durable=True
                )
                
                channel.basic_publish(
                    exchange='',
                    routing_key=settings.RABBITMQ_VISITOR_GRADER_QUEUE,
                    body=json.dumps(task_payload),
                    properties=pika.BasicProperties(
                        delivery_mode=2,
                        content_type='application/json'
                    )
                )
                
                connection.close()
                
                logger.info(
                    "Published visitor assessment task",
                    extra={
                        "task_id": task_id,
                        "visitor_id": visitor_id,
                        "bot_id": bot_id,
                        "session_id": session_id,
                        "num_questions": len(assessment_questions)
                    }
                )
                
                return
                
            except (StreamLostError, ChannelWrongStateError, AMQPConnectionError) as e:
                if attempt < max_retries - 1:
                    logger.warning(
                        f"RabbitMQ connection error, retrying in {retry_delay}s (attempt {attempt + 1}/{max_retries})",
                        extra={"task_id": task_id, "error": str(e)}
                    )
                    if connection and not connection.is_closed:
                        connection.close()
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    if connection and not connection.is_closed:
                        connection.close()
                    raise
                    
            except Exception as e:
                if connection and not connection.is_closed:
                    connection.close()
                
                logger.error(
                    "Failed to publish assessment task",
                    extra={"task_id": task_id, "visitor_id": visitor_id},
                    exc_info=True
                )
                raise

    async def get_visitor(self, visitor_id: str) -> Optional[Visitor]:
        """
        Get visitor by ID.
        
        Args:
            visitor_id: Visitor UUID
            
        Returns:
            Visitor if found, None otherwise
        """
        stmt = select(Visitor).where(Visitor.id == visitor_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def list_visitors(
        self,
        bot_id: Optional[str] = None,
        min_score: Optional[int] = None,
        limit: int = 20,
        offset: int = 0,
        sort_by: Optional[str] = "assessed_at"
    ) -> List[Visitor]:
        """
        List visitors with optional filtering and sorting.
        
        Args:
            bot_id: Optional bot filter
            min_score: Optional minimum lead score filter
            limit: Max results to return
            offset: Pagination offset
            sort_by: Sort column (assessed_at, lead_score, created_at)
            
        Returns:
            List of visitors matching criteria, sorted by selected column
        """
        if sort_by == "lead_score":
            stmt = select(Visitor).order_by(desc(Visitor.lead_score), desc(Visitor.created_at))
        elif sort_by == "created_at":
            stmt = select(Visitor).order_by(desc(Visitor.created_at))
        else:
            stmt = select(Visitor).order_by(
                desc(Visitor.assessed_at).nullslast(),
                desc(Visitor.created_at)
            )
        
        if bot_id:
            stmt = stmt.where(Visitor.bot_id == bot_id)
        
        if min_score is not None:
            stmt = stmt.where(Visitor.lead_score >= min_score)
        
        stmt = stmt.limit(limit).offset(offset)
        
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
    
    async def count_visitors(
        self,
        bot_id: Optional[str] = None,
        min_score: Optional[int] = None
    ) -> int:
        """
        Count total visitors with optional filtering.
        
        Args:
            bot_id: Optional bot filter
            min_score: Optional minimum lead score filter
            
        Returns:
            Total count of visitors matching criteria
        """
        from sqlalchemy import func
        
        stmt = select(func.count(Visitor.id))
        
        if bot_id:
            stmt = stmt.where(Visitor.bot_id == bot_id)
        
        if min_score is not None:
            stmt = stmt.where(Visitor.lead_score >= min_score)
        
        result = await self.db.execute(stmt)
        return result.scalar() or 0
    
    async def store_assessment_results(
        self,
        visitor_id: str,
        assessment_data: dict,
        lead_score: int = 0
    ) -> None:
        """
        Store assessment results in visitor's lead_assessment field and update lead_score.
        
        Args:
            visitor_id: Visitor UUID
            assessment_data: Assessment results dict
            lead_score: Lead score 0-100 from assessment
        """
        stmt = select(Visitor).where(Visitor.id == visitor_id)
        result = await self.db.execute(stmt)
        visitor = result.scalars().first()
        
        if not visitor:
            logger.error(f"Visitor not found: {visitor_id}")
            return
        
        current_assessment = dict(visitor.lead_assessment or {})
        current_assessment["assessment"] = assessment_data
        current_assessment["last_assessed_at"] = assessment_data.get("assessed_at")
        current_assessment["lead_score"] = lead_score
        
        visitor.lead_assessment = current_assessment
        visitor.lead_score = lead_score
        visitor.assessed_at = now()
        visitor.is_new = True
        
        flag_modified(visitor, "lead_assessment")
        
        await self.db.commit()
        
        logger.info(
            "Stored assessment results",
            extra={
                "visitor_id": visitor_id,
                "lead_score": lead_score,
                "num_results": len(assessment_data.get("results", []))
            }
        )
    
    async def get_latest_session_for_visitor(self, visitor_id: str) -> Optional[ChatSession]:
        """
        Get the most recent chat session for a visitor.
        
        Args:
            visitor_id: Visitor UUID
            
        Returns:
            ChatSession if found, None otherwise
        """

        visitor_uuid = UUID(visitor_id) if isinstance(visitor_id, str) else visitor_id
        
        stmt = (
            select(ChatSession)
            .where(ChatSession.visitor_id == visitor_uuid)
            .order_by(ChatSession.started_at.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_session(self, session_id: str) -> Optional[ChatSession]:
        """
        Get chat session by ID.
        
        Args:
            session_id: Session UUID
            
        Returns:
            ChatSession if found, None otherwise
        """
        stmt = select(ChatSession).where(ChatSession.id == session_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_lead_score(
        self,
        visitor_id: str,
        lead_score: int,
        lead_category: str,
        scoring_data: Dict[str, Any]
    ) -> None:
        """
        Update visitor lead score from grading service.
        
        Args:
            visitor_id: Visitor ID
            lead_score: Score 0-100
            lead_category: hot/warm/cold
            scoring_data: Scoring insights and metadata
        """
        try:
            stmt = select(Visitor).where(Visitor.id == visitor_id)
            result = await self.db.execute(stmt)
            visitor = result.scalars().first()
            
            if not visitor:
                logger.error(f"Visitor not found: {visitor_id}")
                return
            
            visitor.lead_score = lead_score
            visitor.lead_category = lead_category
            visitor.is_new = True
            
            extra_data = dict(visitor.extra_data or {})
            extra_data["lead_scoring"] = scoring_data
            visitor.extra_data = extra_data
            
            flag_modified(visitor, "extra_data")
            
            await self.db.commit()
            
            logger.info(
                "Updated visitor lead score",
                extra={
                    "visitor_id": visitor_id,
                    "lead_score": lead_score,
                    "lead_category": lead_category
                }
            )
            
        except Exception as e:
            await self.db.rollback()
            logger.error(
                f"Failed to update lead score: {e}",
                extra={"visitor_id": visitor_id},
                exc_info=True
            )
            raise

    async def handle_contact_request(
        self,
        bot_id: str,
        visitor_id: str,
        visitor_info: Dict[str, Any],
        query: str,
        response: str,
        session_token: str,
    ) -> None:
        """
        Handle contact request from visitor.
        Send email notification and create notification for admin.
        
        Args:
            bot_id: Bot ID
            visitor_id: Visitor ID
            visitor_info: Visitor information
            query: User query
            response: Bot response
            session_token: Chat session token
        """

        logger.info(
            "Handling contact request",
            extra={
                "bot_id": bot_id,
                "visitor_id": visitor_id,
                "visitor_info": visitor_info,
            }
        )
        
        try:
            bot_result = await self.db.execute(
                select(Bot).where(Bot.id == bot_id)
            )
            bot = bot_result.scalar_one_or_none()
            visitor = await self.get_visitor(visitor_id)
            
            redis_client = redis_manager.get_redis()
            notification_service = NotificationService(self.db, redis_client)
            
            await notification_service.create_contact_notification(
                bot_id=bot_id,
                visitor_id=visitor_id,
                visitor_info=visitor_info,
                query=query,
                response=response,
                session_token=session_token,
                db=self.db
            )
            
            logger.info(
                "Contact request handled successfully",
                extra={"bot_id": bot_id, "visitor_id": visitor_id}
            )
            
        except Exception as e:
            logger.error(
                f"Failed to handle contact request: {e}",
                exc_info=True,
                extra={"bot_id": bot_id, "visitor_id": visitor_id}
            )
            pass

    async def get_chat_history(self, visitor_id: str) -> List[Dict[str, Any]]:
        """
        Get chat history for a visitor including all sessions and messages.
        
        Args:
            visitor_id: Visitor UUID
            
        Returns:
            List of chat sessions with messages
        """
        stmt = (
            select(ChatSession)
            .where(ChatSession.visitor_id == visitor_id)
            .order_by(ChatSession.started_at.desc())
        )
        result = await self.db.execute(stmt)
        sessions = result.scalars().all()
        
        chat_history = []
        for session in sessions:
            msg_stmt = (
                select(ChatMessage)
                .where(ChatMessage.session_id == session.id)
                .order_by(ChatMessage.created_at)
            )
            msg_result = await self.db.execute(msg_stmt)
            messages = msg_result.scalars().all()
            
            chat_history.append({
                "id": str(session.id),
                "session_token": session.session_token,
                "created_at": session.started_at.isoformat(),
                "closed_at": session.ended_at.isoformat() if session.ended_at else None,
                "messages": [
                    {
                        "id": str(msg.id),
                        "query": msg.query,
                        "response": msg.response,
                        "created_at": msg.created_at.isoformat()
                    }
                    for msg in messages
                ]
            })
        
        logger.info(
            "Fetched chat history",
            extra={
                "visitor_id": visitor_id,
                "sessions_count": len(chat_history)
            }
        )
        
        return chat_history
