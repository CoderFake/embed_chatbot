"""
Notification service for managing user notifications.

Handles:
- Creating notifications (invite, visitor review, lead scoring, etc.)
- Fetching user notifications
- Marking notifications as read
- Sending email alerts for hot leads
"""
from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import flag_modified
from redis.asyncio import Redis

from app.models.bot import Bot
from app.models.notification import Notification
from app.models.user import User
from app.common.enums import NotificationType, UserRole
from app.schemas.webhook import VisitorGradingWebhook
from app.schemas.notification import NotificationResponse
from app.cache.invalidation import CacheInvalidation
from app.cache.service import CacheService
from app.cache.keys import CacheKeys
from app.utils.email_queue import queue_email
from app.utils.logging import get_logger
from app.utils.datetime_utils import now
from app.config.settings import settings

logger = get_logger(__name__)


class NotificationService:
    """
    Service for managing user notifications.

    Provides methods for creating, fetching, and managing notifications
    with Redis caching support.
    """

    def __init__(self, db: AsyncSession, redis: Redis):
        """
        Initialize notification service.

        Args:
            db: Database session
            redis: Redis connection
        """
        self.db = db
        self.redis = redis
        self.cache = CacheService(redis)
        self.cache_invalidation = CacheInvalidation(redis)

    async def create_notification(
        self,
        user_id: str,
        title: str,
        message: str,
        notification_type: NotificationType,
        link: Optional[str] = None,
        extra_data: Optional[dict] = None
    ) -> Notification:
        """
        Create a new notification for a user.

        Args:
            user_id: User ID to notify
            title: Notification title
            message: Notification message
            notification_type: Type of notification
            link: Optional link to redirect to
            extra_data: Optional additional data

        Returns:
            Created notification
        """
        notification = Notification(
            user_id=UUID(user_id),
            title=title,
            message=message,
            notification_type=notification_type,
            link=link,
            extra_data=extra_data or {}
        )

        self.db.add(notification)
        await self.db.flush()
        await self.db.refresh(notification)

        await self.cache_invalidation.invalidate_notifications(user_id)

        logger.info(f"Created notification for user {user_id}: {notification_type.value}")

        return notification

    async def create_task_notification(
        self,
        user_id: str,
        task_id: str,
        task_type: str,
        title: str,
        message: str,
        bot_id: Optional[str] = None
    ) -> Notification:
        """
        Create a task processing notification.

        Args:
            user_id: User ID to notify
            task_id: Task ID for SSE tracking
            task_type: Type of task (create_bot, recrawl, upload_document)
            title: Notification title
            message: Notification message
            bot_id: Optional bot ID

        Returns:
            Created notification
        """
        extra_data = {
            "task_id": task_id,
            "task_type": task_type,
            "progress": 0,
            "status": "processing"
        }

        if bot_id:
            extra_data["bot_id"] = bot_id

        return await self.create_notification(
            user_id=user_id,
            title=title,
            message=message,
            notification_type=NotificationType.TASK_PROCESSING,
            link=None,
            extra_data=extra_data
        )

    async def update_task_notification(
        self,
        task_id: str,
        progress: int,
        status: str,
        message: Optional[str] = None
    ) -> Optional[Notification]:
        """
        Update task notification progress.

        Args:
            task_id: Task ID
            progress: Progress percentage (0-100)
            status: Task status (processing, completed, failed)
            message: Optional updated message

        Returns:
            Updated notification or None if not found
        """
        query = select(Notification).where(
            and_(
                Notification.notification_type == NotificationType.TASK_PROCESSING,
                Notification.extra_data['task_id'].astext == task_id
            )
        )

        result = await self.db.execute(query)
        notification = result.scalar_one_or_none()

        if not notification:
            logger.warning(f"Task notification not found: {task_id}")
            return None

        notification.extra_data["progress"] = progress
        notification.extra_data["status"] = status
        
        flag_modified(notification, "extra_data")

        if message:
            notification.message = message

        if status in ["completed", "failed"] or progress >= 100:
            notification.is_read = True
            notification.read_at = now()

        await self.db.flush()
        await self.cache_invalidation.invalidate_notifications(str(notification.user_id))

        logger.info(f"Updated task notification: {task_id}, progress={progress}%, status={status}")

        return notification

    async def get_user_notifications(
        self,
        user_id: str,
        unread_only: bool = False,
        skip: int = 0,
        limit: int = 50
    ) -> List[NotificationResponse]:
        """
        Get notifications for a user with caching.

        Args:
            user_id: User ID
            unread_only: If True, only return unread notifications
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of notifications
        """
        cache_key = CacheKeys.user_notifications(user_id, unread_only)

        cached = await self.cache.get(cache_key)
        if cached:
            return [NotificationResponse(**n) for n in cached[skip:skip + limit]]

        query = select(Notification).where(Notification.user_id == UUID(user_id))

        if unread_only:
            query = query.where(Notification.is_read == False)

        query = query.order_by(desc(Notification.created_at))

        result = await self.db.execute(query)
        notifications = result.scalars().all()

        notification_dicts = [
            {
                "id": str(n.id),
                "user_id": str(n.user_id),
                "title": n.title,
                "message": n.message,
                "notification_type": n.notification_type.value,
                "link": n.link,
                "is_read": n.is_read,
                "extra_data": n.extra_data,
                "created_at": n.created_at.isoformat(),
                "read_at": n.read_at.isoformat() if n.read_at else None
            }
            for n in notifications
        ]

        await self.cache.set(cache_key, notification_dicts, ttl=300)

        return [NotificationResponse(**n) for n in notification_dicts[skip:skip + limit]]

    async def get_active_tasks(self, user_id: str) -> List[dict]:
        """
        Get all active task processing notifications for a user.
        Verifies task status in Redis - auto-marks completed tasks as read.

        Args:
            user_id: User ID

        Returns:
            List of active task notifications with task_id, task_type, progress, status
        """
        
        query = select(Notification).where(
            and_(
                Notification.user_id == UUID(user_id),
                Notification.notification_type == NotificationType.TASK_PROCESSING,
                Notification.is_read == False
            )
        ).order_by(desc(Notification.created_at))

        result = await self.db.execute(query)
        notifications = result.scalars().all()

        active_tasks = []
        notifications_to_mark_read = []
        
        for n in notifications:
            extra_data = n.extra_data or {}
            task_id = extra_data.get("task_id")

            if not task_id:
                continue

            task_key = CacheKeys.task_state(task_id)
            task_exists = await self.cache.exists(task_key)
            
            if not task_exists:
                logger.info(f"Task {task_id} no longer in Redis, marking notification as read")
                notifications_to_mark_read.append(n)
                continue

            active_tasks.append({
                "notification_id": str(n.id),
                "task_id": task_id,
                "task_type": extra_data.get("task_type", "unknown"),
                "bot_id": extra_data.get("bot_id"),
                "progress": extra_data.get("progress", 0),
                "status": extra_data.get("status", "processing"),
                "title": n.title,
                "message": n.message,
                "created_at": n.created_at.isoformat()
            })
        
        if notifications_to_mark_read:
            for n in notifications_to_mark_read:
                n.is_read = True
                n.read_at = now()
            
            await self.db.flush()
            await self.cache_invalidation.invalidate_notifications(user_id)
            logger.info(f"Auto-marked {len(notifications_to_mark_read)} completed task notifications as read")

        return active_tasks

    async def get_unread_count(self, user_id: str) -> int:
        """
        Get count of unread notifications for a user.

        Args:
            user_id: User ID

        Returns:
            Count of unread notifications
        """
        cache_key = CacheKeys.notification_count(user_id)

        cached = await self.cache.get(cache_key, as_json=False)
        if cached:
            return int(cached)

        query = select(Notification).where(
            and_(
                Notification.user_id == UUID(user_id),
                Notification.is_read == False
            )
        )

        result = await self.db.execute(query)
        count = len(result.scalars().all())

        await self.cache.set(cache_key, count, ttl=300, as_json=False)

        return count

    async def mark_as_read(self, notification_id: str, user_id: str) -> bool:
        """
        Mark a notification as read.

        Args:
            notification_id: Notification ID
            user_id: User ID (for verification)

        Returns:
            True if successful, False otherwise
        """
        query = select(Notification).where(
            and_(
                Notification.id == UUID(notification_id),
                Notification.user_id == UUID(user_id)
            )
        )

        result = await self.db.execute(query)
        notification = result.scalars().first()

        if not notification:
            return False

        if not notification.is_read:
            notification.is_read = True
            notification.read_at = now()
            await self.db.flush()

            await self.cache_invalidation.invalidate_notifications(user_id)

            logger.info(f"Marked notification {notification_id} as read for user {user_id}")

        return True
    
    async def delete_notification(self, notification_id: str, user_id: str) -> bool:
        """
        Delete a notification.
        
        Args:
            notification_id: Notification ID
            user_id: User ID (for verification)
            
        Returns:
            True if successful, False otherwise
        """
        query = select(Notification).where(
            and_(
                Notification.id == UUID(notification_id),
                Notification.user_id == UUID(user_id)
            )
        )
        
        result = await self.db.execute(query)
        notification = result.scalars().first()
        
        if not notification:
            return False
            
        await self.db.delete(notification)
        await self.db.flush()
        
        await self.cache_invalidation.invalidate_notifications(user_id)
        
        logger.info(f"Deleted notification {notification_id} for user {user_id}")
        
        return True

    async def mark_all_as_read(self, user_id: str) -> int:
        """
        Mark all notifications as read for a user.

        Args:
            user_id: User ID

        Returns:
            Number of notifications marked as read
        """
        query = select(Notification).where(
            and_(
                Notification.user_id == UUID(user_id),
                Notification.is_read == False
            )
        )

        result = await self.db.execute(query)
        notifications = result.scalars().all()

        count = 0
        for notification in notifications:
            notification.is_read = True
            notification.read_at = now()
            count += 1

        if count > 0:
            await self.db.flush()
            await self.cache_invalidation.invalidate_notifications(user_id)

            logger.info(f"Marked all notifications as read for user: {user_id}")
        return count 

    async def cleanup_stale_tasks(self, user_id: str, hours: int = 24) -> int:
        """
        Mark old stuck tasks as failed.
        
        Finds task notifications older than specified hours still in "processing"
        status and marks them as failed to prevent UI clutter.
        
        Args:
            user_id: User ID
            hours: Age threshold in hours (default: 24)
            
        Returns:
            Number of tasks cleaned up
        """
        from datetime import timedelta
        
        cutoff_time = now() - timedelta(hours=hours)
        
        query = select(Notification).where(
            and_(
                Notification.user_id == UUID(user_id),
                Notification.notification_type == NotificationType.TASK_PROCESSING,
                Notification.extra_data['status'].astext == 'processing',
                Notification.created_at < cutoff_time
            )
        )
        
        result = await self.db.execute(query)
        stale_tasks = result.scalars().all()
        
        updated_count = 0
        for notification in stale_tasks:
            notification.extra_data["status"] = "failed"
            notification.extra_data["progress"] = 0
            notification.message = f"Task timeout (>{hours}h)"
            notification.is_read = True
            notification.read_at = now()
            updated_count += 1
        
        if updated_count > 0:
            await self.db.flush()
            await self.cache_invalidation.invalidate_notifications(user_id)
            logger.info(f"Cleaned up {updated_count} stale tasks for user: {user_id}")
        
        return updated_count

    async def send_hot_lead_notification(
        self,
        bot_id: str,
        visitor_id: str,
        score: int,
        insights: VisitorGradingWebhook
    ) -> None:
        """
        Send email notification and create in-app notification for hot lead.

        Args:
            bot_id: Bot ID
            visitor_id: Visitor ID
            score: Lead score (70-100)
            insights: Full grading insights
        """
        try:
            stmt = select(Bot).where(Bot.id == UUID(bot_id))
            result = await self.db.execute(stmt)
            bot = result.scalars().first()

            if not bot:
                logger.error(f"Bot not found: {bot_id}")
                return


            stmt = select(User).where(User.role == UserRole.ADMIN.value)
            result = await self.db.execute(stmt)
            admin_users = result.scalars().all()

            if not admin_users:
                logger.error("No admin users found to notify")
                return

            bot_name = bot.name
            visitor_link = f"/dashboard/visitors/{visitor_id}"

            for user in admin_users:
                await self.create_notification(
                    user_id=str(user.id),
                    title=f"Hot Lead Detected - Score: {score}/100",
                    message=f"A hot lead was detected on bot '{bot_name}' with a score of {score}/100. Category: {insights.lead_category.upper()}",
                    notification_type=NotificationType.LEAD_SCORED,
                    link=visitor_link,
                    extra_data={
                        "bot_id": bot_id,
                        "visitor_id": visitor_id,
                        "score": score,
                        "category": insights.lead_category,
                        "engagement_level": insights.engagement_level
                    }
                )

                email_data = {
                    "owner_name": user.full_name or "User",
                    "bot_name": bot_name,
                    "score": score,
                    "category": insights.lead_category.upper(),
                    "intent_signals": insights.intent_signals,
                    "key_interests": insights.key_interests,
                    "recommended_actions": insights.recommended_actions,
                    "reasoning": insights.reasoning,
                    "engagement_level": insights.engagement_level.upper(),
                    "conversation_count": insights.conversation_count,
                    "visitor_profile_url": f"{settings.FRONTEND_URL}/dashboard/visitors/{visitor_id}",
                    "graded_at": now().strftime("%Y-%m-%d %H:%M"),
                    "app_name": settings.APP_NAME,
                }

                try:
                    await queue_email(
                        template_name="visitor-grader-notification.html",
                        recipient_email=user.email,
                        subject=f"Hot Lead Detected - Score: {score}/100 | {bot_name}",
                        context=email_data,
                        priority=9
                    )
                except Exception as email_error:
                    logger.error(
                        f"Failed to queue hot lead email: {email_error}",
                        extra={"admin_id": str(user.id)},
                        exc_info=True
                    )

            logger.info(
                "Hot lead notifications sent",
                extra={
                    "bot_id": bot_id,
                    "visitor_id": visitor_id,
                    "score": score,
                    "admin_count": len(admin_users)
                }
            )

        except Exception as e:
            logger.error(
                f"Failed to send hot lead notification: {e}",
                extra={
                    "bot_id": bot_id,
                    "visitor_id": visitor_id
                },
                exc_info=True
            )

    async def create_contact_notification(
        self,
        bot_id: str,
        visitor_id: str,
        visitor_info: Dict[str, Any],
        query: str,
        response: str,
        session_token: str,
        db: AsyncSession
    ) -> None:
        """
        Create notification and send email to admin when visitor requests contact.
        
        Args:
            bot_id: Bot ID
            visitor_id: Visitor ID
            visitor_info: Visitor information
            query: User query requesting contact
            response: Bot response
            session_token: Chat session token
            db: Database session
        """
        try:
            
            bot_result = await db.execute(
                select(Bot).where(Bot.id == bot_id)
            )
            bot = bot_result.scalar_one_or_none()
            bot_name = bot.name if bot else "Unknown Bot"
            
            admin_result = await db.execute(
                select(User).where(User.role == UserRole.ADMIN.value)
            )
            admin_users = admin_result.scalars().all()
            
            if not admin_users:
                logger.warning("No admin users found for contact notification")
                return
            
            visitor_name = visitor_info.get("name", "Anonymous")
            visitor_email = visitor_info.get("email", "")
            visitor_phone = visitor_info.get("phone", "")
            visitor_address = visitor_info.get("address", "")
            
            for user in admin_users:
                notification = Notification(
                    user_id=user.id,
                    title=f"Yêu cầu liên hệ từ {visitor_name}",
                    message=f"Khách hàng {visitor_name} yêu cầu liên hệ trên bot {bot_name}. Email: {visitor_email}, SĐT: {visitor_phone}",
                    notification_type=NotificationType.CONTACT_REQUEST,
                    link=f"/visitors/{visitor_id}",
                    extra_data={
                        "bot_id": bot_id,
                        "bot_name": bot_name,
                        "visitor_id": visitor_id,
                        "visitor_info": visitor_info,
                        "query": query,
                    }
                )
                db.add(notification)
                
                try:
                    email_context = {
                        "admin_name": user.full_name or user.email,
                        "bot_name": bot_name,
                        "visitor_name": visitor_name,
                        "visitor_email": visitor_email or "Chưa cung cấp",
                        "visitor_phone": visitor_phone or "Chưa cung cấp",
                        "visitor_address": visitor_address or "Chưa cung cấp",
                        "query": query,
                        "response": response,
                        "session_token": session_token,
                        "visitor_link": f"{settings.FRONTEND_URL}/visitors/{visitor_id}",
                        "app_name": settings.APP_NAME,
                    }
                    
                    await queue_email(
                        template_name="contact_request.html",
                        recipient_email=user.email,
                        subject=f"Yêu cầu liên hệ từ {visitor_name} | {bot_name}",
                        context=email_context,
                        priority=8
                    )
                except Exception as email_error:
                    logger.error(
                        f"Failed to queue contact email to {user.email}: {email_error}",
                        extra={"admin_id": str(user.id)},
                        exc_info=True
                    )
            
            await db.flush()
            
            logger.info(
                "Contact request notifications created",
                extra={
                    "bot_id": bot_id,
                    "visitor_id": visitor_id,
                    "admin_count": len(admin_users)
                }
            )
            
        except Exception as e:
            logger.error(
                f"Failed to create contact notification: {e}",
                extra={
                    "bot_id": bot_id,
                    "visitor_id": visitor_id
                },
                exc_info=True
            )
