from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
from typing import List, Optional
from uuid import UUID
import json

from app.core.database import get_db, get_redis
from app.core.dependencies import Admin, Member
from app.common.types import CurrentUser
from app.services.bot import BotService
from app.services.storage import minio_service
from app.config.settings import settings
from app.schemas.upload import (
    UpdateDisplayConfigBody, 
    SelfContaindGenerateSchema
)
from app.schemas.bot import (
    BotCreate, 
    BotUpdate, 
    BotResponse,
    BotProcessing,
    AllowedOriginCreate,
    AllowedOriginResponse,
    RecrawlResponse,
    DisplayConfig,
    ProviderConfigResponse,
    RevealKeyRequest,
    RevealKeyResponse
)
from app.utils.encryption import decrypt_api_key
from app.models.bot import BotStatus, Bot
from app.utils.logging import get_logger
from app.utils.image import detect_image_type

logger = get_logger(__name__)

router = APIRouter()


@router.post("", response_model=BotProcessing, dependencies=[Depends(Admin)])
async def create_bot(
    bot_data: BotCreate,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(Admin)
):
    """
    Create a new bot with origin and optional sitemap URLs.
    
    **Required role:** root, admin
    
    - **name**: Bot name
    - **origin**: Allowed origin (e.g., https://example.com)
    - **sitemap_urls**: Optional list of specific URLs to crawl (max 100)
    - **language**: Optional language code (e.g., 'vi', 'en')
    - **display_config**: Optional widget UI customization
    
    **Crawling behavior:**
    - If `sitemap_urls` provided and not empty → Crawl only those specific URLs
    - If `sitemap_urls` empty or omitted → BFS crawl entire origin domain
    
    **bot_key will be auto-generated** as: bot_{uuid}
    Example: bot_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
    
    When created, the system will:
    1. Generate unique bot_key
    2. Create Milvus collection for vector storage
    3. Create MinIO bucket for document storage
    4. Create AllowedOrigin record with origin and sitemap_urls
    5. Cache the origin for CORS middleware validation
    6. Enqueue background crawl job
    
    Returns BotProcessing with:
    - bot: Bot details including origin and sitemap_urls
    - task_id: Crawl job ID for progress tracking
    - sse_endpoint: SSE endpoint path to monitor crawl progress (e.g., /tasks/{task_id}/progress)
    """
    bot_service = BotService(db, redis)

    from app.services.notification import NotificationService
    notification_service = NotificationService(db, redis)

    try:
        bot = await bot_service.create(
            name=bot_data.name,
            origin=bot_data.origin,
            sitemap_urls=bot_data.sitemap_urls,
            language=bot_data.language,
            desc=bot_data.desc,
            assessment_questions=bot_data.assessment_questions
        )

        job_id = await bot_service.enqueue_crawl_job(
            bot_id=str(bot.id),
            origin=bot_data.origin,
            sitemap_urls=bot_data.sitemap_urls
        )

        await notification_service.create_task_notification(
            user_id=current_user.user_id,
            task_id=job_id,
            task_type="create_bot",
            title=f"Creating bot: {bot_data.name}",
            message="Crawling website...",
            bot_id=str(bot.id)
        )

        await db.commit()
        
        await db.refresh(bot, ["allowed_origins", "provider_config"])
        
        crawl_mode = f"with {len(bot_data.sitemap_urls)} sitemap URLs" if bot_data.sitemap_urls else "BFS full domain"
        logger.info(f"Bot created: {bot.name} by {current_user.email}, crawl job: {job_id} ({crawl_mode})")
        
        bot_response = BotResponse.model_validate(bot_service._serialize_bot_to_response(bot))
        
        return BotProcessing(
            bot=bot_response,
            task_id=job_id,
            sse_endpoint=f"/tasks/{job_id}/progress"
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        await db.rollback()
        error_msg = str(e)
        
        if "already running" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=error_msg
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to create bot: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create bot: {str(e)}"
        )


@router.get("", response_model=List[BotResponse], dependencies=[Depends(Member)])
async def list_bots(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    status: Optional[BotStatus] = None,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """
    List all bots with optional filtering.
    
    **Required role:** root, admin, member
    
    - **status**: Optional filter by status (active, inactive, draft)
    - **skip**: Number of records to skip
    - **limit**: Maximum number of records to return
    """
    bot_service = BotService(db, redis)
    
    bots = await bot_service.get_all(
        skip=skip,
        limit=limit,
        status=status
    )
    
    return bots


@router.get("/{bot_id}", response_model=BotResponse, dependencies=[Depends(Member)])
async def get_bot(
    bot_id: UUID,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """
    Get bot details by ID.
    
    **Required role:** root, admin, member
    """
    bot_service = BotService(db, redis)
    
    bot = await bot_service.get_by_id(str(bot_id), skip_cache=True)
    
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )
    
    return bot_service._serialize_bot_to_response(bot)


@router.put("/{bot_id}", response_model=BotResponse, dependencies=[Depends(Admin)])
async def update_bot(
    bot_id: UUID,
    bot_data: BotUpdate,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(Admin)
):
    """
    Update bot details including provider configuration.

    
    **Provider Configuration (REQUIRED):**
    - Each bot must have exactly one provider configuration (OpenAI, Gemini, Ollama)
    - Bot cannot be ACTIVE without provider configuration
    - API key will be encrypted before storage
    
    **Permissions:**
    - ADMIN and ROOT can configure provider for bots
    - Only ROOT can modify provider's api_base_url (in separate provider endpoint)
    
    **Required role:** admin, root
    """
    bot_service = BotService(db, redis)
    
    try:
        bot = await bot_service.get_by_id(str(bot_id), skip_cache=True)
        
        if not bot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bot not found"
            )
        
        provider_config_data = None
        if bot_data.provider_config:
            provider_config_data = {
                "provider_id": bot_data.provider_config.provider_id,
                "model_id": bot_data.provider_config.model_id,
                "api_keys": [key.model_dump() for key in bot_data.provider_config.api_keys],
                "config": bot_data.provider_config.config
            }
        
        updated_bot = await bot_service.update(
            bot=bot,
            name=bot_data.name,
            language=bot_data.language,
            desc=bot_data.desc,
            assessment_questions=bot_data.assessment_questions,
            status=bot_data.status,
            provider_config_data=provider_config_data
        )
        
        await db.commit()
        
        await db.refresh(updated_bot, ["allowed_origins"])
        
        logger.info(f"Bot updated: {bot.name} by {current_user.email}")
        
        return bot_service._serialize_bot_to_response(updated_bot)
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to update bot {bot_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update bot: {str(e)}"
        )


@router.delete("/{bot_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(Admin)])
async def delete_bot(
    bot_id: UUID,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(Admin)
):
    """
    Soft delete bot and related allowed origins.
    
    **Atomic Transaction:**
    - Soft deletes bot (sets is_deleted=True)
    - Soft deletes all allowed_origins
    - Rolls back if any operation fails
    
    **Required role:** root, admin
    """
    bot_service = BotService(db, redis)
    
    try:
        bot = await bot_service.get_by_id(str(bot_id), skip_cache=True)
        
        if not bot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bot not found"
            )
        
        await bot_service.delete(bot)
        await db.commit()
        
        logger.info(f"Bot deleted: {bot.name} by {current_user.email}")
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to delete bot {bot_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reveal key: {str(e)}"
        )



@router.post("/{bot_id}/activate", response_model=BotResponse, dependencies=[Depends(Admin)])
async def activate_bot(
    bot_id: UUID,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(Admin)
):
    """
    Activate bot (set status to ACTIVE).
    
    **Required:** Bot must have provider configuration to be activated.
    
    **Required role:** admin, root
    """
    bot_service = BotService(db, redis)
    
    try:
        bot = await bot_service.get_by_id(str(bot_id), skip_cache=True)
        
        if not bot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bot not found"
            )
        
        has_config = await bot_service._has_provider_config(bot.id)
        if not has_config:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot activate bot without provider configuration. Please configure provider first."
            )
        
        activated_bot = await bot_service.activate(bot)
        await db.commit()
        
        logger.info(f"Bot activated: {bot.name} by {current_user.email}")
        
        return activated_bot
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to activate bot {bot_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to activate bot: {str(e)}"
        )


@router.post("/{bot_id}/deactivate", response_model=BotResponse, dependencies=[Depends(Admin)])
async def deactivate_bot(
    bot_id: UUID,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(Admin)
):
    """
    Deactivate bot (set status to INACTIVE).
    
    **Required role:** admin, root
    """
    bot_service = BotService(db, redis)
    
    try:
        bot = await bot_service.get_by_id(str(bot_id), skip_cache=True)
        
        if not bot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bot not found"
            )
        
        deactivated_bot = await bot_service.deactivate(bot)
        await db.commit()
        
        logger.info(f"Bot deactivated: {bot.name} by {current_user.email}")
        
        return deactivated_bot
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to deactivate bot {bot_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to deactivate bot: {str(e)}"
        )


@router.put("/{bot_id}/origin", response_model=AllowedOriginResponse, dependencies=[Depends(Admin)])
async def update_allowed_origin(
    bot_id: UUID,
    origin_data: AllowedOriginCreate,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(Admin)
):
    """
    Update the allowed origin for a bot.
    Since each bot has exactly one origin, this replaces the existing origin.
    
    **Atomic Transaction:**
    - Updates allowed_origin table
    - Updates cache
    - Rolls back if any operation fails
    
    **Required role:** admin, root
    
    - **origin**: New origin URL (e.g., https://example.com)
    """
    bot_service = BotService(db, redis)
    
    try:
        bot = await bot_service.get_by_id(str(bot_id))
        if not bot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bot not found"
            )
        
        allowed_origin = await bot_service.update_allowed_origin(
            bot_id=str(bot_id),
            new_origin=origin_data.origin
        )
        
        await db.commit()
        
        logger.info(f"Updated origin for bot {bot.name} to {origin_data.origin} by {current_user.email}")
        
        return allowed_origin
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to update origin for bot {bot_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update origin: {str(e)}"
        )


@router.get("/{bot_id}/origin", response_model=AllowedOriginResponse, dependencies=[Depends(Member)])
async def get_allowed_origin(
    bot_id: UUID,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """
    Get the allowed origin for a bot.
    
    **Required role:** root, admin, member
    """
    bot_service = BotService(db, redis)
    
    bot = await bot_service.get_by_id(str(bot_id))
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )
    
    origin = await bot_service.get_allowed_origin(str(bot_id))
    
    if not origin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No origin found for this bot"
        )
    
    return origin


@router.post("/{bot_id}/recrawl", response_model=RecrawlResponse, dependencies=[Depends(Admin)])
async def recrawl_bot_origin(
    bot_id: UUID,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(Admin)
):
    """
    Re-crawl bot's origin domain.
    
    **Required role:** root, admin
    
    Process:
    1. Delete all documents from URL crawls (not uploaded files)
    2. Delete corresponding vectors from Milvus
    3. Re-index Milvus collection
    4. Enqueue new crawl task to file-server
    
    **Note:** This only affects documents from crawling, NOT uploaded files.
    
    Returns:
        Task ID, SSE endpoint, and status
    """
    bot_service = BotService(db, redis)

    from app.services.notification import NotificationService
    notification_service = NotificationService(db, redis)

    try:
        result = await bot_service.recrawl_origin(str(bot_id))

        bot = await bot_service.get_by_id(str(bot_id))

        await notification_service.create_task_notification(
            user_id=current_user.user_id,
            task_id=result['job_id'],
            task_type="recrawl",
            title=f"Re-crawling bot: {bot.name if bot else 'Unknown'}",
            message="Re-crawling website...",
            bot_id=str(bot_id)
        )

        await db.commit()

        logger.info(f"Re-crawl initiated for bot {bot_id} by {current_user.email}")

        return {
            "message": "Re-crawl initiated successfully",
            "sse_endpoint": f"/tasks/{result['job_id']}/progress",
            **result
        }
        
    except ValueError as e:
        await db.rollback()
        error_msg = str(e)
        
        if "already running" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=error_msg
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg
            )
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to initiate re-crawl for bot {bot_id}: {e}", exc_info=True)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate re-crawl: {str(e)}"
        )


@router.get(
    "/{bot_id}/display-config",
    response_model=DisplayConfig,
    dependencies=[Depends(Admin)]
)
async def get_bot_display_config(
    bot_id: UUID,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(Admin)
):
    """
    Get bot's display configuration as structured model.
    
    Returns the widget UI configuration with full validation and default values.
    This endpoint returns a structured DisplayConfig model instead of raw JSON.
    
    **Required role:** root, admin
    """
    bot_service = BotService(db, redis)
    
    bot = await bot_service.get_by_id(str(bot_id))
    
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )
    
    try:
        if bot.display_config:
            display_config = DisplayConfig(**bot.display_config)
        else:
            display_config = DisplayConfig()
        
        return display_config
        
    except Exception as e:
        logger.error(f"Failed to parse display_config for bot {bot_id}: {e}")
        return DisplayConfig()


@router.put(
    "/{bot_id}/display-config",
    response_model=DisplayConfig,
    dependencies=[Depends(Admin)],
    openapi_extra={
        "requestBody": {
            "content": {
                "multipart/form-data": {
                    "schema": UpdateDisplayConfigBody.model_json_schema(schema_generator=SelfContaindGenerateSchema),
                    "encoding": {
                        "avatar": {
                            "contentType": "image/*"
                        },
                        "logo": {
                            "contentType": "image/*"
                        }
                    }
                }
            }
        }
    }
)
async def update_bot_display_config(
    bot_id: UUID,
    config: Optional[str] = Form(None),
    avatar: Optional[UploadFile] = File(None),
    logo: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(Admin)
):
    """
    Update bot's display configuration with optional file uploads.
    
    **Content-Type**: multipart/form-data
    
    **Form fields**:
    - `config` (optional): JSON string of DisplayConfig
    - `avatar` (optional): Bot avatar image file (max 5MB, jpg/png)
    - `logo` (optional): Company logo image file (max 5MB, jpg/png)
    
    **Example using curl**:
    ```bash
    curl -X PUT "http://localhost:18000/api/v1/bots/{bot_id}/display-config" \\
      -H "Authorization: Bearer YOUR_TOKEN" \\
      -F 'config={"header":{"title":"New Title"}}' \\
      -F "avatar=@/path/to/avatar.jpg" \\
      -F "logo=@/path/to/logo.png"
    ```
    
    **Example using JavaScript**:
    ```javascript
    const formData = new FormData();
    formData.append('config', JSON.stringify({
      header: { title: "Chat Support" }
    }));
    formData.append('avatar', avatarFile);
    formData.append('logo', logoFile);
    
    fetch('/api/v1/bots/{bot_id}/display-config', {
      method: 'PUT',
      body: formData
    });
    ```
    
    Files are uploaded to MinIO public bucket.
    Old files are automatically deleted when replaced.
    
    **Required role:** root, admin
    """
    # Parse config JSON
    config_obj = None
    if config:
        try:
            config_dict = json.loads(config)
            config_obj = DisplayConfig(**config_dict)
        except (json.JSONDecodeError, ValueError) as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid config JSON: {str(e)}"
            )
    
    # Read avatar file
    avatar_bytes = None
    if avatar:
        avatar_bytes = await avatar.read()
        if len(avatar_bytes) > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Avatar file size must not exceed 5MB")
        if not detect_image_type(avatar_bytes):
            raise HTTPException(status_code=400, detail="Avatar must be a valid image")
    
    # Read logo file
    logo_bytes = None
    if logo:
        logo_bytes = await logo.read()
        if len(logo_bytes) > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Logo file size must not exceed 5MB")
        if not detect_image_type(logo_bytes):
            raise HTTPException(status_code=400, detail="Logo must be a valid image")
    
    bot_service = BotService(db, redis)
    bot = await bot_service.get_by_id(str(bot_id), skip_cache=True)
    
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found"
        )
    
    try:
        config_dict = config_obj.model_dump() if config_obj else (bot.display_config or {})
        
        await bot_service.update(
            bot=bot,
            display_config=config_dict,
            avatar_bytes=avatar_bytes,
            logo_bytes=logo_bytes
        )
        await db.commit()
        
        logger.info(f"Display config updated for bot {bot_id} by {current_user.email}")
        
        return DisplayConfig(**bot.display_config)
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to update display_config for bot {bot_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update display config: {str(e)}"
        )


# ============================================================================
# Provider Configuration Endpoints
# ============================================================================

@router.get("/{bot_id}/provider-config", response_model=ProviderConfigResponse, dependencies=[Depends(Admin)])
async def get_provider_config(
    bot_id: UUID,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(Admin)
):
    """
    Get provider configuration for bot.
    
    Returns encrypted API key. Use POST /bots/{bot_id}/reveal-api-key to decrypt.
    
    **Required role:** admin, root
    """
    bot_service = BotService(db, redis)
    
    config = await bot_service.get_provider_config(str(bot_id))
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider configuration not found"
        )
    
    return config


@router.post("/{bot_id}/reveal-api-key", response_model=RevealKeyResponse, dependencies=[Depends(Admin)])
async def reveal_api_key(
    bot_id: UUID,
    request: RevealKeyRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(Admin)
):
    """
    Decrypt and reveal specific API key.
    
    **Security:**
    - This endpoint should only be called when user explicitly clicks "reveal" button
    - Action is logged for audit purposes
    
    **Required role:** admin, root
    
    **Request:**
    ```json
    {
        "encrypted_key": "gAAAAABl..."
    }
    ```
    
    **Response:**
    ```json
    {
        "key": "sk-proj-xxx",
        "name": "key1",
        "active": true
    }
    ```
    """
    bot_service = BotService(db, redis)
    
    logger.info(f"Attempting to get provider config for bot_id: {bot_id}")
    config = await bot_service.get_provider_config(str(bot_id))
    logger.info(f"Provider config result: {config}")
    
    if not config:
        logger.error(f"Provider configuration not found for bot_id: {bot_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider configuration not found"
        )
    
    for key_obj in config.api_keys:
        if key_obj.get("key") == request.encrypted_key:
            plain_key = decrypt_api_key(key_obj["key"])
            logger.warning(f"API key '{key_obj.get('name')}' revealed for bot {bot_id} by {current_user.email}")
            
            return {
                "key": plain_key,
                "name": key_obj.get("name", "unknown"),
                "active": key_obj.get("active", False)
            }
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Encrypted key not found in API keys"
    )
