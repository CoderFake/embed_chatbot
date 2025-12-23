"""
Email queue utility for publishing email tasks to RabbitMQ.
"""
import asyncio
from typing import Dict, Any

from app.services.rabbitmq import email_queue_publisher
from app.utils.logging import get_logger

logger = get_logger(__name__)


async def queue_email(
    template_name: str,
    recipient_email: str,
    subject: str,
    context: Dict[str, Any],
    priority: int = 5
) -> str:
    """
    Queue email task to RabbitMQ (non-blocking).
    
    Args:
        template_name: Email template filename
        recipient_email: Recipient email address
        subject: Email subject
        context: Template context data
        priority: Task priority (0-10, higher = more priority)
        
    Returns:
        task_id: Generated task ID
        
    Raises:
        Exception: If failed to queue email
    """
    try:
        task_id = await asyncio.to_thread(
            email_queue_publisher.publish_email_task,
            template_name=template_name,
            recipient_email=recipient_email,
            subject=subject,
            context=context,
            priority=priority
        )
        
        logger.info(
            "Email queued successfully",
            extra={
                "task_id": task_id,
                "recipient": recipient_email,
                "template": template_name,
                "priority": priority
            }
        )
        
        return task_id
        
    except Exception as e:
        logger.error(
            f"Failed to queue email: {e}",
            extra={
                "recipient": recipient_email,
                "template": template_name
            },
            exc_info=True
        )
        raise

