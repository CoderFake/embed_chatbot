"""
Provider and Model service for managing LLM providers (OpenAI, Gemini, Ollama).

Only ROOT users can manage providers and models.
Providers are initialized from settings and cannot be created via API.
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload
from redis.asyncio import Redis
from fastapi import HTTPException, status
from uuid import UUID

from app.models.provider import Provider, Model, ProviderStatus, ModelType
from app.models.bot import ProviderConfig
from app.cache.service import CacheService
from app.cache.keys import CacheKeys
from app.config.settings import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ProviderService:
    """
    Service for managing LLM providers and models.
    
    Permissions:
    - Only ROOT can manage providers and models
    - Providers cannot be created (initialized from settings)
    - Providers can only be updated (activate/deactivate/modify base_url)
    """
    
    def __init__(self, db: AsyncSession, redis: Redis):
        self.db = db
        self.redis = redis
        self.cache = CacheService(redis)
    

    async def get_provider_by_id(self, provider_id: str) -> Optional[Provider]:
        """Get provider by ID."""
        result = await self.db.execute(
            select(Provider)
            .options(selectinload(Provider.models))
            .where(Provider.id == provider_id)
        )
        return result.scalar_one_or_none()
    
    async def get_provider_by_slug(self, slug: str) -> Optional[Provider]:
        """Get provider by slug."""
        result = await self.db.execute(
            select(Provider).where(Provider.slug == slug)
        )
        return result.scalar_one_or_none()
    
    async def get_all_providers(
        self,
        include_deleted: bool = False,
        status_filter: Optional[ProviderStatus] = None
    ) -> List[Provider]:
        """
        Get all providers.
        
        Args:
            include_deleted: Include soft-deleted providers
            status_filter: Filter by status (ACTIVE/INACTIVE)
            
        Returns:
            List of providers
        """
        query = select(Provider).options(selectinload(Provider.models))
        
        if not include_deleted:
            query = query.where(Provider.deleted_at.is_(None))
        
        if status_filter:
            query = query.where(Provider.status == status_filter)
        
        query = query.order_by(Provider.created_at)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def update_provider(
        self,
        provider_id: str,
        name: Optional[str] = None,
        api_base_url: Optional[str] = None,
        status: Optional[ProviderStatus] = None
    ) -> Provider:
        """
        Update provider details.
        Only ROOT can update providers.
        
        Args:
            provider_id: Provider UUID
            name: Optional new name
            api_base_url: Optional new base URL (can modify)
            status: Optional new status
            
        Returns:
            Updated provider
            
        Raises:
            HTTPException: If provider not found
        """
        provider = await self.get_provider_by_id(provider_id)
        
        if not provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Provider not found"
            )
        
        if name is not None:
            provider.name = name
        if api_base_url is not None:
            provider.api_base_url = api_base_url
        if status is not None:
            provider.status = status
        
        await self.db.flush()
        await self.db.refresh(provider)
        
        await self.redis.delete(CacheKeys.provider(provider_id))
        await self.redis.delete(CacheKeys.providers_list())
        
        logger.info(f"Updated provider: {provider.name}")
        
        return provider
    
    async def soft_delete_provider(self, provider_id: str) -> None:
        """
        Soft delete provider and cascade soft delete related data.
        
        Cascade:
        1. Soft delete all models of this provider
        2. Soft delete all provider_configs using this provider
        
        Args:
            provider_id: Provider UUID
            
        Raises:
            HTTPException: If provider not found
        """
        provider = await self.get_provider_by_id(provider_id)
        
        if not provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Provider not found"
            )
        
        provider.soft_delete()
        provider.status = ProviderStatus.INACTIVE
        
        result = await self.db.execute(
            select(Model).where(
                Model.provider_id == provider_id,
                Model.deleted_at.is_(None)
            )
        )
        models = result.scalars().all()
        for model in models:
            model.soft_delete()
            model.is_active = False
            logger.info(f"Soft deleted model: {model.name}")
        
        config_result = await self.db.execute(
            select(ProviderConfig).where(
                ProviderConfig.provider_id == provider_id,
                ProviderConfig.is_deleted.is_(False)
            )
        )
        configs = config_result.scalars().all()
        for config in configs:
            config.is_deleted = True
            config.is_active = False

            await self.redis.delete(CacheKeys.bot_config(str(config.bot_id)))
            logger.info(f"Soft deleted provider_config for bot: {config.bot_id}")
        
        await self.db.flush()
        
        await self.redis.delete(CacheKeys.provider(provider_id))
        await self.redis.delete(CacheKeys.providers_list())
        
        logger.info(f"Soft deleted provider: {provider.name} (with {len(models)} models, {len(configs)} configs)")
    
    async def restore_provider(self, provider_id: str) -> Provider:
        """
        Restore soft-deleted provider.
        
        Args:
            provider_id: Provider UUID
            
        Returns:
            Restored provider
            
        Raises:
            HTTPException: If provider not found
        """
        provider = await self.get_provider_by_id(provider_id)
        
        if not provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Provider not found"
            )
        
        provider.restore()
        provider.status = ProviderStatus.ACTIVE
        
        await self.db.flush()
        await self.db.refresh(provider)
        
        await self.redis.delete(CacheKeys.provider(provider_id))
        await self.redis.delete(CacheKeys.providers_list())
        
        logger.info(f"Restored provider: {provider.name}")
        
        return provider
    
    # ========================================================================
    
    async def get_model_by_id(self, model_id: str) -> Optional[Model]:
        """Get model by ID."""
        result = await self.db.execute(
            select(Model).where(Model.id == model_id)
        )
        return result.scalar_one_or_none()
    
    async def get_models_by_provider(
        self,
        provider_id: str,
        include_deleted: bool = False
    ) -> List[Model]:
        """
        Get all models for a provider.
        
        Args:
            provider_id: Provider UUID
            include_deleted: Include soft-deleted models
            
        Returns:
            List of models
        """
        query = select(Model).where(Model.provider_id == provider_id)
        
        if not include_deleted:
            query = query.where(Model.deleted_at.is_(None))
        
        query = query.order_by(Model.name)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_active_models_by_provider(self, provider_id: str) -> List[Model]:
        """
        Get only ACTIVE models for a provider.
        Used for bot configuration - only show selectable models.
        
        Args:
            provider_id: Provider UUID
            
        Returns:
            List of active, non-deleted models
        """
        result = await self.db.execute(
            select(Model).where(
                Model.provider_id == provider_id,
                Model.is_active.is_(True),
                Model.deleted_at.is_(None)
            ).order_by(Model.name)
        )
        return result.scalars().all()
    
    async def create_model(
        self,
        provider_id: UUID,
        name: str,
        model_type: ModelType,
        context_window: int,
        pricing: float = 0.0,
        extra_data: Optional[Dict[str, Any]] = None
    ) -> Model:
        """
        Create new model or restore if exists.
        
        If model with same name and provider already exists:
        - If deleted: Restore it and update fields
        - If active: Return existing
        
        Args:
            provider_id: Provider UUID
            name: Model name
            model_type: Model type (CHAT, etc.)
            context_window: Context window size
            pricing: Cost per 1M tokens (legacy)
            extra_data: Additional config including pricing (cost_per_1k_input, cost_per_1k_output)
            
        Returns:
            Created or restored model
            
        Raises:
            HTTPException: If provider not found
        """

        provider = await self.get_provider_by_id(str(provider_id))
        if not provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Provider {provider_id} not found"
            )
        
        result = await self.db.execute(
            select(Model).where(
                Model.provider_id == provider_id,
                Model.name == name
            )
        )
        existing_model = result.scalar_one_or_none()
        
        if existing_model:
            if existing_model.is_deleted:
                existing_model.restore()
                existing_model.is_active = True
                existing_model.model_type = model_type
                existing_model.context_window = context_window
                existing_model.pricing = pricing
                if extra_data:
                    existing_model.extra_data = extra_data
                
                await self.db.flush()
                await self.db.refresh(existing_model)
                
                logger.info(f"Restored model: {name} for provider {provider.name}")
                return existing_model
            else:
                logger.info(f"Model already exists: {name} for provider {provider.name}")
                return existing_model
        
        new_model = Model(
            provider_id=provider_id,
            name=name,
            model_type=model_type,
            context_window=context_window,
            pricing=pricing,
            extra_data=extra_data or {},
            is_active=True
        )
        
        self.db.add(new_model)
        await self.db.flush()
        await self.db.refresh(new_model)
        
        await self.redis.delete(CacheKeys.models_list(str(provider_id)))
        
        logger.info(f"Created model: {name} for provider {provider.name}")
        
        return new_model
    
    async def update_model(
        self,
        model_id: str,
        name: Optional[str] = None,
        model_type: Optional[ModelType] = None,
        context_window: Optional[int] = None,
        pricing: Optional[float] = None,
        is_active: Optional[bool] = None
    ) -> Model:
        """
        Update model details.
        
        Args:
            model_id: Model UUID
            name: Optional new name
            model_type: Optional new type
            context_window: Optional new context window
            pricing: Optional new pricing
            is_active: Optional active status
            
        Returns:
            Updated model
            
        Raises:
            HTTPException: If model not found
        """
        model = await self.get_model_by_id(model_id)
        
        if not model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Model not found"
            )
        
        if name is not None:
            model.name = name
        if model_type is not None:
            model.model_type = model_type
        if context_window is not None:
            model.context_window = context_window
        if pricing is not None:
            model.pricing = pricing
        if is_active is not None:
            model.is_active = is_active
        
        await self.db.flush()
        await self.db.refresh(model)
        
        await self.redis.delete(CacheKeys.model(model_id))
        await self.redis.delete(CacheKeys.models_list(str(model.provider_id)))
        
        logger.info(f"Updated model: {model.name}")
        
        return model
    
    async def soft_delete_model(self, model_id: str) -> None:
        """
        Soft delete model and cascade soft delete related provider_configs.
        
        Args:
            model_id: Model UUID
            
        Raises:
            HTTPException: If model not found
        """
        model = await self.get_model_by_id(model_id)
        
        if not model:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Model not found"
            )
        
        model.soft_delete()
        model.is_active = False
        
        config_result = await self.db.execute(
            select(ProviderConfig).where(
                ProviderConfig.model_id == model_id,
                ProviderConfig.is_deleted.is_(False)
            )
        )
        configs = config_result.scalars().all()
        for config in configs:
            config.is_deleted = True
            config.is_active = False

            await self.redis.delete(CacheKeys.bot_config(str(config.bot_id)))
            logger.info(f"Soft deleted provider_config for bot: {config.bot_id}")
        
        await self.db.flush()
        
        await self.redis.delete(CacheKeys.model(model_id))
        await self.redis.delete(CacheKeys.models_list(str(model.provider_id)))
        
        logger.info(f"Soft deleted model: {model.name} (with {len(configs)} configs)")
