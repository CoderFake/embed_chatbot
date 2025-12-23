from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from redis.asyncio import Redis
from fastapi import HTTPException, status
import uuid
import asyncio

from app.models.bot import Bot, BotStatus, ProviderConfig, AllowedOrigin
from app.models.provider import Provider, Model
from app.models.document import Document
from app.common.enums import DocumentStatus
from app.cache.service import CacheService
from app.cache.keys import CacheKeys
from app.cache.invalidation import CacheInvalidation
from app.services.storage import minio_service
from app.config.settings import settings
from app.schemas.bot import DisplayConfig
from app.services.rabbitmq import rabbitmq_publisher
from app.utils.logging import get_logger
from app.utils.encryption import encrypt_api_key, is_encrypted
from app.utils.image import detect_image_type
from app.utils.file_path import build_avatar_key, build_logo_key
            

logger = get_logger(__name__)


class BotService:
    """
    Bot service with cache integration.
    """
    
    def __init__(self, db: AsyncSession, redis: Redis):
        self.db = db
        self.redis = redis
        self.cache = CacheService(redis)
        self.cache_invalidation = CacheInvalidation(redis)
    
    async def get_by_id(self, bot_id: str, skip_cache: bool = False) -> Optional[Bot]:
        """
        Get bot by ID with cache-aside pattern.
        
        Args:
            bot_id: Bot UUID
            skip_cache: If True, always query from DB (needed for updates)
            
        Returns:
            Bot instance or None
        """
        cache_key = CacheKeys.bot(bot_id)
        
        if not skip_cache:
            cached_data = await self.cache.get(cache_key)
            
            if cached_data:
                logger.debug(f"Cache hit for bot: {bot_id}")
                bot_data = {
                    k: v for k, v in cached_data.items() 
                    if k in ['id', 'name', 'bot_key', 'language', 'status', 'display_config', 'created_at', 'updated_at', 'desc', 'assessment_questions']
                }
                if 'status' in bot_data and isinstance(bot_data['status'], str):
                    bot_data['status'] = BotStatus(bot_data['status'])
                return Bot(**bot_data)
        
        logger.debug(f"Cache miss for bot: {bot_id}")
        result = await self.db.execute(
            select(Bot)
            .options(
                selectinload(Bot.allowed_origins),
                selectinload(Bot.provider_config)
            )
            .where(Bot.id == bot_id)
            .where(Bot.is_deleted.is_(False))
        )
        bot = result.scalar_one_or_none()
        
        if bot:
            origin = None
            sitemap_urls = []
            if bot.allowed_origins:
                for allowed_origin in bot.allowed_origins:
                    if allowed_origin.is_active and not allowed_origin.is_deleted:
                        origin = allowed_origin.origin
                        sitemap_urls = allowed_origin.sitemap_urls or []
                        break
            
            bot_dict = {
                "id": str(bot.id),
                "name": bot.name,
                "bot_key": bot.bot_key,
                "language": bot.language,
                "status": bot.status.value,
                "display_config": bot.display_config,
                "collection_name": bot.collection_name,
                "bucket_name": bot.bucket_name,
                "desc": bot.desc,
                "assessment_questions": bot.assessment_questions,
                "origin": origin,
                "sitemap_urls": sitemap_urls,
                "created_at": bot.created_at.isoformat(),
                "updated_at": bot.updated_at.isoformat(),
            }
            await self.cache.set(cache_key, bot_dict, ttl=settings.CACHE_BOT_TTL)
        
        return bot
    
    async def get_by_bot_key(self, bot_key: str) -> Optional[Bot]:
        """
        Get bot by bot_key.
        
        Args:
            bot_key: Bot key (unique identifier)
            
        Returns:
            Bot instance or None
        """
        result = await self.db.execute(
            select(Bot)
            .options(selectinload(Bot.allowed_origins))
            .where(Bot.bot_key == bot_key)
            .where(Bot.is_deleted.is_(False))
        )
        return result.scalar_one_or_none()
    
    async def create(
        self,
        name: str,
        origin: str,
        sitemap_urls: List[str] = None,
        language: Optional[str] = None,
        desc: Optional[str] = None,
        assessment_questions: List[str] = None
    ) -> Bot:
        """
        Create new bot with auto-generated bot_key.
        Also creates Milvus collection, MinIO bucket, and AllowedOrigin record.
        
        bot_key format: bot_{uuid_without_hyphens}
        Example: bot_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
        
        Crawling logic:
        - If sitemap_urls provided and not empty → crawl specific URLs
        - If sitemap_urls empty or None → BFS crawl entire origin domain
        
        Args:
            name: Bot name
            origin: Website origin/domain (e.g., https://example.com)
            sitemap_urls: Optional list of specific URLs to crawl from sitemap
            language: Optional language code
            desc: Optional bot description
            assessment_questions: Optional list of assessment questions
            
        Returns:
            Created bot instance with default display_config
        """
        bot_uuid = str(uuid.uuid4())
        bot_key = f"bot_{bot_uuid.replace('-', '_')}"
        
        default_config = DisplayConfig()
        display_config = default_config.model_dump()
        display_config['header']['title'] = name
        
        bot = Bot(
            name=name,
            bot_key=bot_key,
            language=language,
            status=BotStatus.DRAFT,
            display_config=display_config,
            desc=desc,
            assessment_questions=assessment_questions or []
        )
        
        self.db.add(bot)
        await self.db.flush()
        await self.db.refresh(bot)
        
        minio_created = False
        
        try:
            bucket_name = bot.bucket_name
            await asyncio.to_thread(minio_service.create_bucket, bucket_name)
            minio_created = True
            logger.info(f"Created MinIO bucket: {bucket_name}")
            
            allowed_origin = AllowedOrigin(
                bot_id=bot.id,
                origin=origin,
                sitemap_urls=sitemap_urls or [],
                is_active=True
            )
            self.db.add(allowed_origin)
            await self.db.flush()
            await self.db.refresh(bot)
            
            await self._cache_allowed_origins(bot.bot_key)
            
            sitemap_info = f"with {len(sitemap_urls)} sitemap URLs" if sitemap_urls else "for crawl"
            logger.info(f"Created bot: {bot.name} (key: {bot.bot_key}) - origin: {origin} {sitemap_info}")
            
            return bot
            
        except Exception as e:
            logger.error(f"Bot creation failed, cleaning up: {e}")
            
            if minio_created:
                try:
                    bucket_name = bot.bucket_name
                    await asyncio.to_thread(minio_service.delete_bucket, bucket_name)
                    logger.info(f"Cleaned up MinIO bucket: {bucket_name}")
                except Exception as cleanup_error:
                    logger.error(f"Failed to cleanup MinIO bucket: {cleanup_error}")
            
            await self.db.rollback()
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create bot: {str(e)}"
            )
    
    async def enqueue_crawl_job(
        self, 
        bot_id: str, 
        origin: str,
        sitemap_urls: List[str] = None
    ) -> str:
        """
        Enqueue origin crawl job to file-server via RabbitMQ.
        
        Prevents duplicate crawl tasks by checking if one is already running.
        
        Crawling logic:
        - If sitemap_urls provided and not empty → crawl specific URLs
        - If sitemap_urls empty or None → BFS crawl entire origin domain
        
        Args:
            bot_id: Bot UUID
            origin: Origin URL to crawl  
            sitemap_urls: Optional list of specific URLs to crawl
            
        Returns:
            Task ID
            
        Raises:
            ValueError: If bot not found or crawl task already running
        """
        
        bot = await self.get_by_id(bot_id)
        if not bot:
            raise ValueError("Bot not found")
        
        
        crawl_lock_key = CacheKeys.crawl_lock(bot_id)
        existing_task_id = await self.redis.get(crawl_lock_key)
        
        if existing_task_id:
            task_state_key = CacheKeys.task_state(existing_task_id)
            task_state = await self.redis.hgetall(task_state_key)
            
            if task_state:
                status = task_state.get(b"status", b"").decode() if isinstance(task_state.get(b"status"), bytes) else task_state.get("status", "")
                
                if status in ["PENDING", "pending", "processing", "PROCESSING"]:
                    logger.warning(
                        f"Crawl task already running for bot {bot_id}: {existing_task_id}",
                        extra={
                            "bot_id": bot_id,
                            "existing_task_id": existing_task_id,
                            "status": status
                        }
                    )
                    raise ValueError(f"Crawl task already running for this bot (task: {existing_task_id})")
        
        task_id = str(uuid.uuid4())
        
        await self.redis.set(crawl_lock_key, task_id, ex=7200)
        
        await self.redis.hset(
            CacheKeys.task_state(task_id),
            mapping={
                "task_id": task_id,
                "bot_id": bot_id,
                "progress": "0",
                "status": "PENDING",
                "message": "Crawl task queued, waiting to start...",
                "timestamp": str(uuid.uuid4())  
            }
        )
        await self.redis.expire(CacheKeys.task_state(task_id), 86400) 
        
        await rabbitmq_publisher.publish_crawl_task(
            task_id=task_id,
            bot_id=bot_id,
            origin=origin,
            sitemap_urls=sitemap_urls or [],
            collection_name=bot.collection_name
        )
        
        crawl_mode = f"{len(sitemap_urls)} sitemap URLs" if sitemap_urls else "BFS full domain"
        logger.info(f"Published crawl task {task_id} for bot {bot_id} - origin: {origin} ({crawl_mode})")
        return task_id
    
    def _serialize_bot_to_response(self, bot: Bot) -> dict:
        """
        Serialize Bot model to BotResponse schema format.
        Extracts origin and sitemap_urls from allowed_origins relationship or direct attributes (if from cache).
        
        Args:
            bot: Bot instance with loaded allowed_origins and provider_config relationships
            
        Returns:
            Dictionary matching BotResponse schema
        """

        origin = getattr(bot, 'origin', None)
        sitemap_urls = getattr(bot, 'sitemap_urls', [])
        
        if origin is None and bot.allowed_origins:
            for allowed_origin in bot.allowed_origins:
                if allowed_origin.is_active and not allowed_origin.is_deleted:
                    origin = allowed_origin.origin
                    sitemap_urls = allowed_origin.sitemap_urls or []
                    break
        
        display_config_dict = bot.display_config
        if not display_config_dict or display_config_dict == {}:
            display_config = DisplayConfig()
        else:
            try:
                display_config = DisplayConfig(**display_config_dict)
            except Exception:
                display_config = DisplayConfig()
        
        provider_config = None
        if bot.provider_config:
            provider_config = bot.provider_config
        
        return {
            "id": bot.id,
            "name": bot.name,
            "bot_key": bot.bot_key,
            "language": bot.language,
            "status": bot.status,
            "display_config": display_config,
            "collection_name": bot.collection_name,
            "bucket_name": bot.bucket_name,
            "desc": bot.desc,
            "assessment_questions": bot.assessment_questions or [],
            "origin": origin,
            "sitemap_urls": sitemap_urls,
            "provider_config": provider_config,
            "created_at": bot.created_at,
            "updated_at": bot.updated_at
        }
    
    async def _cache_allowed_origins(self, bot_key: str) -> None:
        """
        Cache the single allowed origin for a bot (used by CORS middleware).
        Since each bot has exactly one origin, we cache it in Redis Set.
        Middleware uses bot_key for lookup.
        
        Args:
            bot_key: Bot key (e.g., bot_xxx)
        """
        result = await self.db.execute(
            select(Bot)
            .options(selectinload(Bot.allowed_origins))
            .where(Bot.bot_key == bot_key)
            .where(Bot.is_deleted.is_(False))
        )
        bot = result.scalar_one_or_none()
        
        if not bot:
            logger.warning(f"Bot not found for caching origins: {bot_key}")
            return
        
        result = await self.db.execute(
            select(AllowedOrigin).where(
                AllowedOrigin.bot_id == bot.id,
                AllowedOrigin.is_active.is_(True),
                AllowedOrigin.is_deleted.is_(False)
            )
        )
        allowed_origin = result.scalar_one_or_none()
        
        if allowed_origin:
            cache_key = CacheKeys.allowed_origins(bot_key)
            
            await self.redis.delete(cache_key)
            await self.redis.sadd(cache_key, allowed_origin.origin)
            await self.redis.expire(cache_key, settings.CACHE_BOT_TTL)
            
            logger.debug(f"Cached origin '{allowed_origin.origin}' for bot {bot_key}")
        else:
            logger.warning(f"No active origin found for bot {bot_key}")
    
    async def update(
        self,
        bot: Bot,
        name: Optional[str] = None,
        language: Optional[str] = None,
        desc: Optional[str] = None,
        assessment_questions: Optional[List[str]] = None,
        status: Optional[BotStatus] = None,
        display_config: Optional[dict] = None,
        provider_config_data: Optional[dict] = None,
        avatar_bytes: Optional[bytes] = None,
        logo_bytes: Optional[bytes] = None
    ) -> Bot:
        """
        Update existing bot and invalidate cache.
        
        Args:
            bot: Bot instance to update
            name: Optional new name
            language: Optional new language
            desc: Optional bot description
            assessment_questions: Optional list of assessment questions
            status: Optional new status  
            display_config: Optional new display config
            provider_config_data: REQUIRED provider configuration
                                  {provider_id, model_id, api_key, config}
            avatar_bytes: Optional avatar image bytes
            logo_bytes: Optional logo image bytes
            
        Returns:
            Updated bot instance
            
        Raises:
            HTTPException: If provider or model not found, or if trying to activate without provider config
        """
        if name is not None:
            bot.name = name
            if display_config is None:
                display_config = bot.display_config or {}
            if "header" not in display_config:
                display_config["header"] = {}
            display_config["header"]["title"] = name
        
        if language is not None:
            bot.language = language
        
        if desc is not None:
            bot.desc = desc
        
        if assessment_questions is not None:
            bot.assessment_questions = assessment_questions
        
        if avatar_bytes or logo_bytes:
            
            if display_config is None:
                display_config = bot.display_config or {}
            
            old_avatar_url = None
            old_logo_url = None
            
            if avatar_bytes:
                img_type = detect_image_type(avatar_bytes)
                content_type = f"image/{img_type}"
                
                if display_config.get("header", {}).get("avatar_url"):
                    old_avatar_url = display_config["header"]["avatar_url"]
                
                object_key = build_avatar_key(img_type)
                avatar_url = minio_service.upload_public_file(
                    object_key,
                    avatar_bytes,
                    content_type
                )
                
                if "header" not in display_config:
                    display_config["header"] = {}
                display_config["header"]["avatar_url"] = avatar_url
            
            if logo_bytes:
                img_type = detect_image_type(logo_bytes)
                content_type = f"image/{img_type}"
                
                if display_config.get("branding", {}).get("company_logo_url"):
                    old_logo_url = display_config["branding"]["company_logo_url"]
                
                object_key = build_logo_key(img_type)
                logo_url = minio_service.upload_public_file(
                    object_key,
                    logo_bytes,
                    content_type
                )
                
                if "branding" not in display_config:
                    display_config["branding"] = {}
                display_config["branding"]["company_logo_url"] = logo_url
        
        if display_config is not None:
            bot.display_config = display_config
        
        if provider_config_data:
            await self._upsert_provider_config(bot.id, provider_config_data)
        
        if status is not None:
            if status == BotStatus.ACTIVE:
                has_config = await self._has_provider_config(bot.id)
                if not has_config:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Cannot activate bot without provider configuration"
                    )
            bot.status = status
        
        await self.db.flush()
        await self.db.refresh(bot)
        
        if avatar_bytes and old_avatar_url:
            await self._cleanup_file_if_unused(bot.id, old_avatar_url)
        if logo_bytes and old_logo_url:
            await self._cleanup_file_if_unused(bot.id, old_logo_url)
        
        await self.cache_invalidation.invalidate_bot(str(bot.id))
        
        logger.info(f"Updated bot: {bot.name}")
        
        return bot
    
    async def _cleanup_file_if_unused(self, current_bot_id: uuid.UUID, file_url: str) -> None:
        """
        Delete file from MinIO if not used by other bots.
        
        Args:
            current_bot_id: ID of current bot (to exclude from check)
            file_url: URL of file to potentially delete
        """
        if settings.MINIO_PUBLIC_BUCKET not in file_url:
            return
        
        try:
            from sqlalchemy import or_
            stmt = select(Bot).where(
                Bot.id != current_bot_id,
                or_(
                    Bot.display_config['header']['avatar_url'].astext == file_url,
                    Bot.display_config['branding']['company_logo_url'].astext == file_url
                )
            )
            result = await self.db.execute(stmt)
            other_bots_using_file = result.first()
            
            if not other_bots_using_file:
                object_name = file_url.split(f"{settings.MINIO_PUBLIC_BUCKET}/")[-1]
                minio_service.delete_public_file(object_name)
                logger.info(f"Deleted unused file: {object_name}")
            else:
                logger.info(f"Skipped deleting file (used by other bots): {file_url}")
        except Exception as e:
            logger.warning(f"Failed to cleanup file {file_url}: {e}")
    
    async def delete(self, bot: Bot) -> None:
        """
        Soft delete bot by setting is_deleted=True.
        Also soft deletes the associated AllowedOrigin.
        Does NOT delete Milvus collection or MinIO bucket (kept for recovery).
        
        Args:
            bot: Bot instance to soft delete
        """
        bot_id = str(bot.id)
        bot_name = bot.name
        bot.is_deleted = True
        
        result = await self.db.execute(
            select(AllowedOrigin).where(
                AllowedOrigin.bot_id == bot.id,
                AllowedOrigin.is_deleted.is_(False)
            )
        )
        allowed_origin = result.scalar_one_or_none()
        
        if allowed_origin:
            allowed_origin.is_deleted = True
            logger.info(f"Soft deleted origin: {allowed_origin.origin}")
        
        await self.redis.set(CacheKeys.crawl_stop(bot_id), "1", ex=3600)
        await self.redis.delete(CacheKeys.crawl_lock(bot_id))
        
        await self.db.flush()
        await self.cache_invalidation.invalidate_bot(bot_id)
        
        logger.info(f"Soft deleted bot: {bot_name} (id: {bot_id}) and signalled crawl cancellation")
    
    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[BotStatus] = None
    ) -> List[dict]:
        """
        Get all bots with optional filtering.
        Returns serialized bot responses with origin and sitemap_urls.
        
        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            status: Optional filter by status
            
        Returns:
            List of serialized bot response dicts
        """
        query = select(Bot).options(
            selectinload(Bot.allowed_origins),
            selectinload(Bot.provider_config)
        )
        
        query = query.where(Bot.is_deleted.is_(False))
        
        if status:
            query = query.where(Bot.status == status)
        
        query = query.offset(skip).limit(limit).order_by(Bot.created_at.desc())
        
        result = await self.db.execute(query)
        bots = result.scalars().all()
        
        return [self._serialize_bot_to_response(bot) for bot in bots]
   
    
    async def activate(self, bot: Bot) -> Bot:
        """
        Activate bot (set status to ACTIVE).
        
        Args:
            bot: Bot instance
            
        Returns:
            Updated bot instance
        """
        bot.status = BotStatus.ACTIVE
        await self.db.flush()
        await self.db.refresh(bot)
        
        await self.cache_invalidation.invalidate_bot(str(bot.id))
        
        logger.info(f"Activated bot: {bot.name}")
        return bot
    
    async def deactivate(self, bot: Bot) -> Bot:
        """
        Deactivate bot (set status to INACTIVE).
        
        Args:
            bot: Bot instance
            
        Returns:
            Updated bot instance
        """
        bot.status = BotStatus.INACTIVE
        await self.db.flush()
        await self.db.refresh(bot)
        
        await self.cache_invalidation.invalidate_bot(str(bot.id))
        
        logger.info(f"Deactivated bot: {bot.name}")
        return bot
    
    async def update_allowed_origin(self, bot_id: str, new_origin: str) -> AllowedOrigin:
        """
        Update the single allowed origin for a bot.
        Since each bot has exactly one origin, this replaces the existing one.
        
        Args:
            bot_id: Bot UUID
            new_origin: New origin URL (e.g., https://example.com)
            
        Returns:
            Updated AllowedOrigin instance
        """
        result = await self.db.execute(
            select(AllowedOrigin).where(
                AllowedOrigin.bot_id == bot_id,
                AllowedOrigin.is_deleted.is_(False)
            )
        )
        allowed_origin = result.scalar_one_or_none()
        
        if not allowed_origin:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No origin found for this bot"
            )
        
        allowed_origin.origin = new_origin
        await self.db.flush()
        await self.db.refresh(allowed_origin)
        
        result = await self.db.execute(
            select(Bot).where(Bot.id == bot_id).where(Bot.is_deleted.is_(False))
        )
        bot = result.scalar_one_or_none()
        
        if bot:
            await self._cache_allowed_origins(bot.bot_key)
        
        logger.info(f"Updated origin for bot {bot_id}: {new_origin}")
        
        return allowed_origin
    
    async def get_allowed_origin(self, bot_id: str) -> Optional[AllowedOrigin]:
        """
        Get the single allowed origin for a bot.
        
        Args:
            bot_id: Bot UUID
            
        Returns:
            AllowedOrigin instance or None
        """
        result = await self.db.execute(
            select(AllowedOrigin)
            .where(AllowedOrigin.bot_id == bot_id)
            .where(AllowedOrigin.is_active.is_(True))
            .where(AllowedOrigin.is_deleted.is_(False))
        )
        return result.scalar_one_or_none()


    async def recrawl_origin(self, bot_id: str) -> dict:
        """
        Re-crawl bot's origin domain.

        Process:
        1. Find all crawled documents (URL-based, not uploaded files)
        2. Publish RECRAWL task to file-server to delete vectors from Milvus
        3. Delete documents from database
        4. Enqueue new crawl job to re-crawl the domain

        Args:
            bot_id: Bot UUID

        Returns:
            Dict with job_id, deleted_count, and origin

        Raises:
            ValueError: If bot or origin not found
        """

        bot = await self.get_by_id(bot_id)
        if not bot:
            raise ValueError("Bot not found")
        
        origin_obj = await self.get_allowed_origin(bot_id)
        if not origin_obj:
            raise ValueError("No origin configured for this bot")
        
        result = await self.db.execute(
            select(Document).where(
                and_(
                    Document.bot_id == bot_id,
                    Document.url.isnot(None), 
                    Document.file_path.is_(None)
                )
            )
        )
        crawled_docs = result.scalars().all()
        
        deleted_count = 0
        
        if crawled_docs:
            completed_doc_ids = [str(doc.id) for doc in crawled_docs if doc.status == DocumentStatus.COMPLETED]
            if completed_doc_ids:
                try:
                    recrawl_task_id = str(uuid.uuid4())
                    await rabbitmq_publisher.publish_recrawl_task(
                        task_id=recrawl_task_id,
                        bot_id=bot_id,
                        document_ids=completed_doc_ids,
                        collection_name=bot.collection_name
                    )
                    logger.info(f"Published recrawl task {recrawl_task_id} to delete {len(completed_doc_ids)} documents from Milvus for bot {bot_id}")
                except Exception as e:
                    logger.error(f"Failed to publish recrawl task: {e}")

            for doc in crawled_docs:
                await self.db.delete(doc)

            deleted_count = len(crawled_docs)
            logger.info(f"Deleted {deleted_count} crawled documents for bot {bot_id}")
        else:
            logger.info(f"No crawled documents found for bot {bot_id}")

        job_id = await self.enqueue_crawl_job(
            bot_id=bot_id,
            origin=origin_obj.origin
        )
        
        logger.info(f"Re-crawl initiated for bot {bot_id}, job: {job_id}")
        
        return {
            "job_id": job_id,
            "deleted_documents": deleted_count,
            "origin": origin_obj.origin
        }
    
    # ========================================================================
    # Provider Configuration Methods
    # ========================================================================
    
    async def _has_provider_config(self, bot_id: uuid.UUID) -> bool:
        """
        Check if bot has provider configuration.
        
        Args:
            bot_id: Bot UUID
            
        Returns:
            True if provider config exists
        """
        result = await self.db.execute(
            select(ProviderConfig)
            .where(ProviderConfig.bot_id == bot_id)
            .where(ProviderConfig.is_deleted.is_(False))
        )
        config = result.scalar_one_or_none()
        return config is not None
    
    async def _upsert_provider_config(
        self,
        bot_id: uuid.UUID,
        config_data: dict
    ) -> ProviderConfig:
        """
        Create or update provider configuration for bot.
        Validates provider and model, encrypts API keys.
        
        Args:
            bot_id: Bot UUID
            config_data: {provider_id, model_id, api_keys, config}
            
        Returns:
            ProviderConfig instance
            
        Raises:
            HTTPException: If provider or model not found
        """
        provider_id = config_data["provider_id"]
        model_id = config_data["model_id"]
        api_keys_input = config_data["api_keys"]
        extra_config = config_data.get("config", {})
        
        provider_result = await self.db.execute(
            select(Provider).where(Provider.id == provider_id)
        )
        provider = provider_result.scalar_one_or_none()
        if not provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Provider {provider_id} not found"
            )
        
        model_result = await self.db.execute(
            select(Model).where(
                Model.id == model_id,
                Model.provider_id == provider_id
            )
        )
        model = model_result.scalar_one_or_none()
        if not model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model {model_id} not found or does not belong to provider {provider_id}"
            )
        
        api_keys = []
        for key_item in api_keys_input:
            key_value = key_item["key"]

            if is_encrypted(key_value):
                encrypted_key = key_value
            else:
                encrypted_key = encrypt_api_key(key_value)

            api_keys.append({
                "key": encrypted_key,
                "name": key_item.get("name", "default"),
                "active": key_item.get("active", True)
            })
        
        result = await self.db.execute(
            select(ProviderConfig)
            .where(ProviderConfig.bot_id == bot_id)
            .where(ProviderConfig.is_deleted.is_(False))
        )
        existing_config = result.scalar_one_or_none()
        
        if existing_config:
            existing_config.provider_id = provider_id
            existing_config.model_id = model_id
            existing_config.api_keys = api_keys
            existing_config.config = extra_config
            existing_config.is_active = True
            
            await self.db.flush()
            await self.db.refresh(existing_config)
            
            logger.info(f"Updated provider config for bot {bot_id}")
            return existing_config
        else:
            new_config = ProviderConfig(
                bot_id=bot_id,
                provider_id=provider_id,
                model_id=model_id,
                api_keys=api_keys,
                is_active=True,
                config=extra_config
            )
            self.db.add(new_config)
            await self.db.flush()
            await self.db.refresh(new_config)
            
            logger.info(f"Created provider config for bot {bot_id}")
            return new_config
    
    async def get_provider_config(self, bot_id: str) -> Optional[ProviderConfig]:
        """
        Get provider configuration for bot with caching.
        
        Args:
            bot_id: Bot UUID
            
        Returns:
            ProviderConfig instance or None
        """
        cache_key = CacheKeys.bot_config(bot_id)
        
        cached_data = await self.cache.get(cache_key)
        if cached_data:
            return ProviderConfig(**cached_data)
        
        result = await self.db.execute(
            select(ProviderConfig)
            .where(ProviderConfig.bot_id == bot_id)
            .where(ProviderConfig.is_deleted.is_(False))
        )
        config = result.scalar_one_or_none()
        
        if config:
            config_dict = {
                "id": str(config.id),
                "bot_id": str(config.bot_id),
                "provider_id": str(config.provider_id),
                "model_id": str(config.model_id),
                "api_keys": config.api_keys,
                "is_active": config.is_active,
                "is_deleted": config.is_deleted,
                "config": config.config,
                "created_at": config.created_at.isoformat(),
                "updated_at": config.updated_at.isoformat()
            }
            await self.cache.set(cache_key, config_dict, ttl=settings.CACHE_BOT_CONFIG_TTL)
        
        return config
    


