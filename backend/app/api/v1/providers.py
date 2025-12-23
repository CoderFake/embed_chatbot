"""
Provider and Model management endpoints.

- Public endpoints: List active providers/models (for bot configuration)
- ROOT endpoints: Full CRUD management
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
from typing import List, Optional
from uuid import UUID

from app.core.database import get_db, get_redis
from app.core.dependencies import Root, Admin
from app.common.types import CurrentUser
from app.services.provider import ProviderService
from app.schemas.provider import (
    ProviderUpdate,
    ProviderResponse,
    ModelCreate,
    ModelUpdate,
    ModelResponse
)
from app.models.provider import ProviderStatus
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/active", response_model=List[ProviderResponse], dependencies=[Depends(Admin)])
async def get_active_providers(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(Admin)
):
    """
    Get all active providers for bot configuration.
    
    **Required role:** admin, root
    
    Returns only ACTIVE and non-deleted providers with their models.
    Used when admin configures provider for a bot.
    """
    provider_service = ProviderService(db, redis)
    
    providers = await provider_service.get_all_providers(
        include_deleted=False,
        status_filter=ProviderStatus.ACTIVE
    )
    
    return providers


@router.get("/{provider_id}/models/active", response_model=List[ModelResponse], dependencies=[Depends(Admin)])
async def get_active_models(
    provider_id: UUID,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(Admin)
):
    """
    Get all active models for a provider.
    
    **Required role:** admin, root
    
    Returns only active and non-deleted models.
    Used when selecting model for bot provider configuration.
    """
    provider_service = ProviderService(db, redis)
    
    models = await provider_service.get_active_models_by_provider(str(provider_id))
    
    return models


# ============================================================================
# ROOT-only Management Endpoints
# ============================================================================

@router.get("", response_model=List[ProviderResponse], dependencies=[Depends(Root)])
async def get_providers(
    include_deleted: bool = Query(False, description="Include soft-deleted providers"),
    status_filter: Optional[ProviderStatus] = Query(None, description="Filter by status"),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(Root)
):
    """
    Get all providers.
    
    **Required role:** root
    
    Query Parameters:
    - **include_deleted**: Include soft-deleted providers
    - **status_filter**: Filter by ACTIVE or INACTIVE
    """
    provider_service = ProviderService(db, redis)
    
    providers = await provider_service.get_all_providers(
        include_deleted=include_deleted,
        status_filter=status_filter
    )
    
    return providers


@router.get("/{provider_id}", response_model=ProviderResponse, dependencies=[Depends(Root)])
async def get_provider(
    provider_id: UUID,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(Root)
):
    """
    Get provider by ID.
    
    **Required role:** root
    """
    provider_service = ProviderService(db, redis)
    
    provider = await provider_service.get_provider_by_id(str(provider_id))
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found"
        )
    
    return provider


@router.put("/{provider_id}", response_model=ProviderResponse, dependencies=[Depends(Root)])
async def update_provider(
    provider_id: UUID,
    provider_data: ProviderUpdate,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(Root)
):
    """
    Update provider details.
    
    **Required role:** root
    
    **Only ROOT can modify api_base_url.**
    
    Fields:
    - **name**: Provider display name
    - **api_base_url**: API base URL (e.g., https://api.openai.com/v1)
    - **status**: ACTIVE or INACTIVE
    """
    provider_service = ProviderService(db, redis)
    
    try:
        updated_provider = await provider_service.update_provider(
            provider_id=str(provider_id),
            name=provider_data.name,
            api_base_url=provider_data.api_base_url,
            status=provider_data.status
        )
        
        await db.commit()
        
        logger.info(f"Provider updated: {updated_provider.name} by {current_user.email}")
        
        return updated_provider
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to update provider {provider_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update provider: {str(e)}"
        )


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(Root)])
async def delete_provider(
    provider_id: UUID,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(Root)
):
    """
    Soft delete provider.
    
    **Required role:** root
    
    **Cascade soft delete:**
    1. All models of this provider
    2. All bot provider_configs using this provider
    
    **Warning:** This will deactivate all bots using this provider!
    """
    provider_service = ProviderService(db, redis)
    
    try:
        await provider_service.soft_delete_provider(str(provider_id))
        
        await db.commit()
        
        logger.warning(f"Provider soft deleted: {provider_id} by {current_user.email}")
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to delete provider {provider_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete provider: {str(e)}"
        )


@router.post("/{provider_id}/restore", response_model=ProviderResponse, dependencies=[Depends(Root)])
async def restore_provider(
    provider_id: UUID,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(Root)
):
    """
    Restore soft-deleted provider.
    
    **Required role:** root
    
    Note: This does NOT restore models or bot configs. Those must be restored separately.
    """
    provider_service = ProviderService(db, redis)
    
    try:
        restored_provider = await provider_service.restore_provider(str(provider_id))
        
        await db.commit()
        
        logger.info(f"Provider restored: {restored_provider.name} by {current_user.email}")
        
        return restored_provider
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to restore provider {provider_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to restore provider: {str(e)}"
        )


# ============================================================================
# Model Endpoints 
# ============================================================================

@router.get("/{provider_id}/models", response_model=List[ModelResponse], dependencies=[Depends(Root)])
async def get_models(
    provider_id: UUID,
    include_deleted: bool = Query(False, description="Include soft-deleted models"),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(Root)
):
    """
    Get all models for a provider.
    
    **Required role:** root
    """
    provider_service = ProviderService(db, redis)
    
    models = await provider_service.get_models_by_provider(
        provider_id=str(provider_id),
        include_deleted=include_deleted
    )
    
    return models


@router.post("/{provider_id}/models", response_model=ModelResponse, dependencies=[Depends(Root)])
async def create_model(
    provider_id: UUID,
    model_data: ModelCreate,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(Root)
):
    """
    Create new model or restore if exists.
    
    **Required role:** root
    
    **Logic:**
    - If model with same name exists and is deleted → Restore and update
    - If model exists and is active → Return existing
    - Otherwise → Create new model
    
    Fields:
    - **name**: Model name (e.g., gpt-4o, gemini-1.5-pro)
    - **model_type**: Model type (CHAT, etc.)
    - **context_window**: Maximum context window size
    - **pricing**: Cost per 1M tokens (legacy)
    - **extra_data**: Pricing config (cost_per_1k_input, cost_per_1k_output)
    """
    provider_service = ProviderService(db, redis)
    
    try:
        model = await provider_service.create_model(
            provider_id=provider_id,
            name=model_data.name,
            model_type=model_data.model_type,
            context_window=model_data.context_window,
            pricing=model_data.pricing,
            extra_data=model_data.extra_data.model_dump() if model_data.extra_data else {}
        )
        
        await db.commit()
        
        logger.info(f"Model created/restored: {model.name} by {current_user.email}")
        
        return model
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to create model: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create model: {str(e)}"
        )


@router.put("/models/{model_id}", response_model=ModelResponse, dependencies=[Depends(Root)])
async def update_model(
    model_id: UUID,
    model_data: ModelUpdate,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(Root)
):
    """
    Update model details.
    
    **Required role:** root
    
    Fields:
    - **name**: Model name
    - **model_type**: Model type
    - **context_window**: Context window size
    - **pricing**: Cost per 1M tokens
    - **is_active**: Active status
    """
    provider_service = ProviderService(db, redis)
    
    try:
        updated_model = await provider_service.update_model(
            model_id=str(model_id),
            name=model_data.name,
            model_type=model_data.model_type,
            context_window=model_data.context_window,
            pricing=model_data.pricing,
            is_active=model_data.is_active
        )
        
        await db.commit()
        
        logger.info(f"Model updated: {updated_model.name} by {current_user.email}")
        
        return updated_model
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to update model {model_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update model: {str(e)}"
        )


@router.delete("/models/{model_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(Root)])
async def delete_model(
    model_id: UUID,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(Root)
):
    """
    Soft delete model.
    
    **Required role:** root
    
    **Cascade soft delete:**
    - All bot provider_configs using this model
    
    **Warning:** This will deactivate all bots using this model!
    """
    provider_service = ProviderService(db, redis)
    
    try:
        await provider_service.soft_delete_model(str(model_id))
        
        await db.commit()
        
        logger.warning(f"Model soft deleted: {model_id} by {current_user.email}")
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to delete model {model_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete model: {str(e)}"
        )
