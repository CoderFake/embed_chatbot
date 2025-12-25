from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from redis.asyncio import Redis
from fastapi import HTTPException, status
from uuid import UUID

from app.models.bot_worker import BotWorker
from app.models.bot import Bot
from app.common.enums import ScheduleType
from app.cache.keys import CacheKeys
from app.utils.logging import get_logger

logger = get_logger(__name__)


class WorkerService:
    """
    Bot Worker service for managing scheduled automation tasks.
    """
    
    def __init__(self, db: AsyncSession, redis: Redis):
        self.db = db
        self.redis = redis
    
    async def create_or_update(
        self,
        bot_id: UUID,
        schedule_type: ScheduleType,
        auto: bool,
        schedule_time: any,
        frequency: any,
        user_email: str
    ) -> BotWorker:
        """
        Create or update bot worker configuration.
        Uses (bot_id, schedule_type) unique constraint for upsert behavior.
        
        Args:
            bot_id: Bot UUID
            schedule_type: Type of worker (crawl, visitor_email, grading)
            auto: Enable/disable automatic execution
            schedule_time: Time to run the worker
            frequency: How often to run (daily, weekly, monthly, yearly)
            user_email: Email of user making the change (for logging)
            
        Returns:
            BotWorker instance
            
        Raises:
            HTTPException: If bot not found
        """
        
        await self._verify_bot_exists(bot_id)
        
        result = await self.db.execute(
            select(BotWorker).where(
                BotWorker.bot_id == bot_id,
                BotWorker.schedule_type == schedule_type
            )
        )
        existing_worker = result.scalar_one_or_none()
        
        if existing_worker:
            existing_worker.auto = auto
            existing_worker.schedule_time = schedule_time
            existing_worker.frequency = frequency
            
            await self.db.flush()
            await self.db.refresh(existing_worker)
            
            await self._invalidate_worker_cache(bot_id, schedule_type)
            
            logger.info(f"Updated worker {schedule_type} for bot {bot_id} by {user_email}")
            return existing_worker
        else:
            new_worker = BotWorker(
                bot_id=bot_id,
                schedule_type=schedule_type,
                auto=auto,
                schedule_time=schedule_time,
                frequency=frequency
            )
            
            self.db.add(new_worker)
            await self.db.flush()
            await self.db.refresh(new_worker)
            
            await self._invalidate_worker_cache(bot_id, schedule_type)
            
            logger.info(f"Created worker {schedule_type} for bot {bot_id} by {user_email}")
            return new_worker
    
    async def get_all(self, bot_id: UUID) -> List[BotWorker]:
        """
        Get all workers configured for a bot.
        
        Args:
            bot_id: Bot UUID
            
        Returns:
            List of BotWorker instances
            
        Raises:
            HTTPException: If bot not found
        """
        await self._verify_bot_exists(bot_id)
        
        result = await self.db.execute(
            select(BotWorker).where(BotWorker.bot_id == bot_id)
        )
        workers = result.scalars().all()
        
        return list(workers)
    
    async def get_by_type(
        self,
        bot_id: UUID,
        schedule_type: ScheduleType
    ) -> BotWorker:
        """
        Get specific worker configuration by schedule type.
        
        Args:
            bot_id: Bot UUID
            schedule_type: Type of worker
            
        Returns:
            BotWorker instance
            
        Raises:
            HTTPException: If worker not found
        """
        result = await self.db.execute(
            select(BotWorker).where(
                BotWorker.bot_id == bot_id,
                BotWorker.schedule_type == schedule_type
            )
        )
        worker = result.scalar_one_or_none()
        
        if not worker:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Worker {schedule_type} not found for this bot"
            )
        
        return worker
    
    async def update(
        self,
        bot_id: UUID,
        schedule_type: ScheduleType,
        auto: Optional[bool] = None,
        schedule_time: Optional[any] = None,
        frequency: Optional[any] = None,
        user_email: str = ""
    ) -> BotWorker:
        """
        Partially update worker configuration.
        
        Args:
            bot_id: Bot UUID
            schedule_type: Type of worker
            auto: Optional new auto value
            schedule_time: Optional new schedule time
            frequency: Optional new frequency value
            user_email: Email of user making the change (for logging)
            
        Returns:
            Updated BotWorker instance
            
        Raises:
            HTTPException: If worker not found
        """
        worker = await self.get_by_type(bot_id, schedule_type)
        
        # Update only provided fields
        if auto is not None:
            worker.auto = auto
        if schedule_time is not None:
            worker.schedule_time = schedule_time
        if frequency is not None:
            worker.frequency = frequency
        
        await self.db.flush()
        await self.db.refresh(worker)
        
        # Invalidate cache
        await self._invalidate_worker_cache(bot_id, schedule_type)
        
        logger.info(f"Updated worker {schedule_type} for bot {bot_id} by {user_email}")
        return worker
    
    async def delete(
        self,
        bot_id: UUID,
        schedule_type: ScheduleType,
        user_email: str
    ) -> None:
        """
        Delete worker configuration.
        
        Args:
            bot_id: Bot UUID
            schedule_type: Type of worker
            user_email: Email of user making the change (for logging)
            
        Raises:
            HTTPException: If worker not found
        """
        worker = await self.get_by_type(bot_id, schedule_type)
        
        await self.db.delete(worker)
        await self.db.flush()
        
        await self._invalidate_worker_cache(bot_id, schedule_type)
        
        logger.info(f"Deleted worker {schedule_type} for bot {bot_id} by {user_email}")
    
    async def _verify_bot_exists(self, bot_id: UUID) -> Bot:
        """
        Verify that a bot exists and is not deleted.
        Checks cache first for performance.
        
        Args:
            bot_id: Bot UUID
            
        Returns:
            Bot instance
            
        Raises:
            HTTPException: If bot not found
        """
        cache_key = CacheKeys.bot(str(bot_id))
        cached_bot = await self.redis.get(cache_key)
        
        if cached_bot:
            return Bot(id=bot_id) 
        result = await self.db.execute(
            select(Bot).where(Bot.id == bot_id, Bot.is_deleted == False)
        )
        bot = result.scalar_one_or_none()
        
        if not bot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bot not found"
            )
        
        return bot
    
    async def _invalidate_worker_cache(self, bot_id: UUID, schedule_type: ScheduleType) -> None:
        """
        Invalidate worker cache after create/update/delete.
        
        Args:
            bot_id: Bot UUID
            schedule_type: Type of worker
        """
        await self.redis.delete(CacheKeys.bot_worker(str(bot_id), schedule_type.value))
    
        await self.redis.delete(CacheKeys.bot_workers(str(bot_id)))
        
        logger.debug(f"Invalidated cache for worker {schedule_type} of bot {bot_id}")
