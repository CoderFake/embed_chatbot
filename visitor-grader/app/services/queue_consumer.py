"""RabbitMQ queue consumer for grading tasks."""
import asyncio
import json
from typing import Optional

from aio_pika import connect_robust, IncomingMessage
from aio_pika.abc import AbstractConnection, AbstractChannel
from aiormq.exceptions import ChannelInvalidStateError

from app.config.settings import settings
from app.core.database import AsyncSessionLocal
from app.schemas.grading import GradingTaskPayload, GradingWebhookPayload, AssessmentWebhookPayload
from app.services.scoring import scoring_service
from app.core.webhook_client import webhook_client
from app.utils.datetime_utils import now
from app.utils.logging import get_logger
from app.common.enums import TaskType, LeadCategory

logger = get_logger(__name__)


class QueueConsumer:
    """
    RabbitMQ consumer for visitor grading tasks.
    
    Responsibilities:
    - Connect to RabbitMQ
    - Consume grading tasks from queue
    - Delegate scoring to ScoringService (with DB session)
    - Send results via WebhookClient
    """
    
    def __init__(self):
        self._connection: Optional[AbstractConnection] = None
        self._channel: Optional[AbstractChannel] = None
        self._running = False
    
    async def connect(self) -> None:
        """Connect to RabbitMQ."""
        logger.info("Connecting to RabbitMQ", extra={"url": settings.RABBITMQ_URL})
        
        self._connection = await connect_robust(
            settings.RABBITMQ_URL,
            heartbeat=settings.RABBITMQ_HEARTBEAT,
            timeout=settings.RABBITMQ_CONNECTION_TIMEOUT,
        )
        self._channel = await self._connection.channel()
        
        await self._channel.set_qos(prefetch_count=settings.RABBITMQ_PREFETCH_COUNT)
        
        queue = await self._channel.declare_queue(
            settings.VISITOR_GRADING_QUEUE,
            durable=True,
        )
        
        logger.info(
            "Connected to RabbitMQ",
            extra={
                "queue": settings.VISITOR_GRADING_QUEUE,
                "prefetch": settings.RABBITMQ_PREFETCH_COUNT
            }
        )
        
        await queue.consume(self._process_message)
        self._running = True
    
    async def disconnect(self) -> None:
        """Disconnect from RabbitMQ."""
        self._running = False
        
        if self._channel:
            await self._channel.close()
            self._channel = None
        
        if self._connection:
            await self._connection.close()
            self._connection = None
        
        logger.info("Disconnected from RabbitMQ")
    
    async def _process_message(self, message: IncomingMessage) -> None:
        """
        Process a grading task message.
        
        Args:
            message: RabbitMQ message containing GradingTaskPayload
        """
        try:
            async with message.process(requeue=False, ignore_processed=True):
                task_data = json.loads(message.body.decode())
                task = GradingTaskPayload(**task_data)
                
                task_type = task.task_type or TaskType.GRADING.value
                
                logger.info(
                    f"Received {task_type} task",
                    extra={
                        "task_id": task.task_id,
                        "task_type": task_type,
                        "visitor_id": task.visitor_id,
                        "bot_id": task.bot_id
                    }
                )
                
                async with AsyncSessionLocal() as db:
                    if task_type == TaskType.ASSESSMENT.value:
                        result = await scoring_service.assess_visitor(task, db)
                        
                        webhook_payload = AssessmentWebhookPayload(
                            task_id=task.task_id,
                            visitor_id=task.visitor_id,
                            bot_id=task.bot_id,
                            session_id=task.session_id,
                            results=result["results"],
                            summary=result["summary"],
                            lead_score=result.get("lead_score", 0),
                            assessed_at=now(),
                            model_used=result["model_used"],
                            total_messages=result["total_messages"]
                        )
                    else:
                        result = await scoring_service.score_visitor(task, db)
                        webhook_payload = GradingWebhookPayload(
                            task_id=task.task_id,
                            visitor_id=task.visitor_id,
                            bot_id=task.bot_id,
                            session_id=task.session_id,
                            lead_score=result.score,
                            lead_category=result.category.value,
                            intent_signals=result.intent_signals,
                            engagement_level=result.engagement_level,
                            key_interests=result.key_interests,
                            recommended_actions=result.recommended_actions,
                            reasoning=result.reasoning,
                            graded_at=now(),
                            model_used=result.model_used,
                            conversation_count=0
                        )
                
                success = await webhook_client.send_result(webhook_payload)
                
                if success:
                    logger.info(
                        f"{task_type.capitalize()} task completed successfully",
                        extra={
                            "task_id": task.task_id,
                            "task_type": task_type,
                            "visitor_id": task.visitor_id
                        }
                    )
                else:
                    logger.error(
                        "Failed to send webhook",
                        extra={"task_id": task.task_id}
                    )
                        
        except ChannelInvalidStateError:
            logger.warning(
                "Channel closed during message processing, message will be redelivered",
                extra={"message_id": message.message_id}
            )
        except Exception as e:
            logger.error(
                "Failed to process grading task",
                extra={"error": str(e)},
                exc_info=True
            )
    
    async def run(self) -> None:
        """Run the consumer with automatic retry on connection failure."""
        max_retries = 10
        retry_delay = 1 
        
        for attempt in range(1, max_retries + 1):
            try:
                await self.connect()
                logger.info("Queue consumer is running. Press Ctrl+C to stop.")
                
                try:
                    while self._running:
                        await asyncio.sleep(1)
                except asyncio.CancelledError:
                    logger.info("Consumer cancelled, shutting down...")
                finally:
                    await self.disconnect()
                
                break
                
            except Exception as e:
                if attempt < max_retries:
                    logger.warning(
                        f"Failed to connect to RabbitMQ (attempt {attempt}/{max_retries}): {e}",
                        extra={"retry_in_seconds": retry_delay}
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, 30)
                else:
                    logger.error(
                        f"Failed to connect to RabbitMQ after {max_retries} attempts. Giving up.",
                        exc_info=True
                    )
                    raise


# Global instance
queue_consumer = QueueConsumer()
