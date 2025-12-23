"""
Cache invalidation rules per entity.
Defines which cache keys need to be invalidated when entities are modified.
"""

from typing import List
from redis.asyncio import Redis

from app.cache.keys import CacheKeys
from app.cache.service import CacheService
from app.utils.logging import get_logger

logger = get_logger(__name__)


class CacheInvalidation:
    """
    Cache invalidation logic for different entities.
    """
    
    def __init__(self, redis: Redis):
        self.cache = CacheService(redis)
    
    async def invalidate_user(self, user_id: str) -> None:
        """
        Invalidate user-related cache.
        
        Args:
            user_id: User UUID
        """
        keys_to_delete = [
            CacheKeys.user(user_id),
        ]
        
        for key in keys_to_delete:
            await self.cache.delete(key)
        
        # Invalidate user lists
        await self.cache.delete_pattern("users:list:*")
        
        logger.info(f"Invalidated cache for user: {user_id}")
    
    async def invalidate_bot(self, bot_id: str) -> None:
        """
        Invalidate bot-related cache.
        
        Args:
            bot_id: Bot UUID
        """
        keys_to_delete = [
            CacheKeys.bot(bot_id),
            CacheKeys.bot_config(bot_id),
            CacheKeys.bot_service_config(bot_id),
            CacheKeys.bot_origins(bot_id),
        ]
        
        for key in keys_to_delete:
            await self.cache.delete(key)
        
        # Invalidate bot lists and analytics
        await self.cache.delete_pattern("bots:list:*")
        await self.cache.delete_pattern(CacheKeys.bot_pattern(bot_id))
        await self.cache.delete(CacheKeys.analytics_bot(bot_id))
        
        logger.info(f"Invalidated cache for bot: {bot_id}")
    
    async def invalidate_document(self, document_id: str, bot_id: str) -> None:
        """
        Invalidate document-related cache.
        
        Args:
            document_id: Document UUID
            bot_id: Associated bot UUID
        """
        keys_to_delete = [
            CacheKeys.document(document_id),
        ]
        
        for key in keys_to_delete:
            await self.cache.delete(key)
        
        # Invalidate bot's document lists
        await self.cache.delete_pattern(f"bot:{bot_id}:documents:*")
        
        logger.info(f"Invalidated cache for document: {document_id}")
    
    async def invalidate_visitor(self, visitor_id: str, bot_id: str) -> None:
        """
        Invalidate visitor-related cache.
        
        Args:
            visitor_id: Visitor UUID
            bot_id: Associated bot UUID
        """
        keys_to_delete = [
            CacheKeys.visitor(visitor_id),
        ]
        
        for key in keys_to_delete:
            await self.cache.delete(key)
        
        # Invalidate visitor lists
        await self.cache.delete_pattern(f"bot:{bot_id}:visitors:*")
        await self.cache.delete_pattern("visitors:list:*")
        
        logger.info(f"Invalidated cache for visitor: {visitor_id}")
    
    async def invalidate_session(self, session_id: str) -> None:
        """
        Invalidate session-related cache.
        
        Args:
            session_id: Session UUID
        """
        await self.cache.delete(CacheKeys.session(session_id))
        logger.info(f"Invalidated cache for session: {session_id}")
    
    async def invalidate_provider(self, provider_id: str) -> None:
        """
        Invalidate provider-related cache.
        
        Args:
            provider_id: Provider UUID
        """
        keys_to_delete = [
            CacheKeys.provider(provider_id),
        ]
        
        for key in keys_to_delete:
            await self.cache.delete(key)
        
        # Invalidate provider lists
        await self.cache.delete_pattern("providers:list:*")
        
        logger.info(f"Invalidated cache for provider: {provider_id}")
    
    async def invalidate_model(self, model_id: str, provider_id: str) -> None:
        """
        Invalidate model-related cache.
        
        Args:
            model_id: Model UUID
            provider_id: Associated provider UUID
        """
        keys_to_delete = [
            CacheKeys.model(model_id),
        ]
        
        for key in keys_to_delete:
            await self.cache.delete(key)
        
        # Invalidate model lists
        await self.cache.delete_pattern("models:list:*")
        
        logger.info(f"Invalidated cache for model: {model_id}")
    
    async def invalidate_analytics(self, bot_id: str = None) -> None:
        """
        Invalidate analytics cache.
        
        Args:
            bot_id: Optional bot UUID for bot-specific analytics
        """
        if bot_id:
            await self.cache.delete(CacheKeys.analytics_bot(bot_id))
            await self.cache.delete_pattern(f"analytics:usage:bot:{bot_id}:*")
        else:
            await self.cache.delete(CacheKeys.analytics_overview())
            await self.cache.delete_pattern("analytics:*")
        
        logger.info(f"Invalidated analytics cache{f' for bot: {bot_id}' if bot_id else ''}")
    
    async def invalidate_notifications(self, user_id: str) -> None:
        """
        Invalidate notification cache for user.
        
        Args:
            user_id: User UUID
        """
        keys_to_delete = [
            CacheKeys.user_notifications(user_id, unread_only=True),
            CacheKeys.user_notifications(user_id, unread_only=False),
            CacheKeys.notification_count(user_id),
        ]
        
        for key in keys_to_delete:
            await self.cache.delete(key)
        
        logger.info(f"Invalidated notification cache for user: {user_id}")
    
    async def invalidate_all_lists(self) -> None:
        """
        Invalidate all list caches (useful after bulk operations).
        """
        patterns = [
            "users:list:*",
            "bots:list:*",
            "visitors:list:*",
            "providers:list:*",
            "models:list:*",
        ]
        
        for pattern in patterns:
            await self.cache.delete_pattern(pattern)
        
        logger.info("Invalidated all list caches")

