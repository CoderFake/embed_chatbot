"""
Widget API endpoints.
Handles widget initialization and visitor session management.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status, UploadFile, File
from fastapi.responses import StreamingResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
from typing import Optional
import io

from app.core.database import get_db
from app.core.dependencies import get_redis, Root
from app.schemas.widget import (
    WidgetInitRequest, 
    WidgetInitResponse, 
    WidgetConfigResponse,
    WidgetChatRequest,
    WidgetChatResponse,
    VisitorProfile
)
from app.schemas.bot import DisplayConfig
from app.schemas.chat import ChatAskRequest
from app.services.visitor import VisitorService
from app.services.bot import BotService
from app.services.chat import chat_service
from app.services.widget import widget_service
from app.common.enums import TaskStatus
from app.common.constants import WidgetFile
from app.utils.logging import get_logger
from app.utils.request_utils import get_client_ip

router = APIRouter()
logger = get_logger(__name__)


@router.get("/config/{bot_id}", response_model=WidgetConfigResponse)
async def get_widget_config(
    bot_id: str,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> WidgetConfigResponse:
    """
    Get widget configuration for a specific bot.
    
    Returns complete display configuration including:
    - Position, size, colors (header, background, message, input, button, scrollbar)
    - Header settings (title, subtitle, avatar)
    - Welcome message and quick replies
    - Input configuration (placeholder, max length, file upload)
    - Behavior settings (auto-open, typing indicator, sound)
    - Branding (company name, logo, powered by)
    
    This is called when widget first loads to get styling/config.
    """
    try:
        bot_service = BotService(db, redis)
        bot = await bot_service.get_by_id(bot_id)
        
        if not bot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bot not found"
            )
        

        display_config_dict = bot.display_config or {}
        
        try:
            if display_config_dict:
                display_config = DisplayConfig(**display_config_dict)
            else:
                display_config = DisplayConfig()
            
            display_config_dict = display_config.model_dump()
        except Exception as e:
            logger.warning(
                f"Failed to parse display_config, using defaults: {e}",
                extra={"bot_id": bot_id}
            )
            
            display_config = DisplayConfig()
            display_config_dict = display_config.model_dump()
        
        welcome_msg = None
        header_title = None
        header_subtitle = None
        avatar_url = None
        placeholder = None
        primary_color = None
        
        if "welcome_message" in display_config_dict:
            welcome_msg = display_config_dict["welcome_message"].get("message")
        
        if "header" in display_config_dict:
            header_title = display_config_dict["header"].get("title")
            header_subtitle = display_config_dict["header"].get("subtitle")
            avatar_url = display_config_dict["header"].get("avatar_url")
        
        if "input" in display_config_dict:
            placeholder = display_config_dict["input"].get("placeholder")
        
        if "colors" in display_config_dict and "header" in display_config_dict["colors"]:
            primary_color = display_config_dict["colors"]["header"].get("background")
        
        return WidgetConfigResponse(
            bot_id=str(bot.id),
            bot_name=bot.name,
            bot_key=bot.bot_key,
            language=bot.language,
            display_config=display_config_dict,
            welcome_message=welcome_msg,
            header_title=header_title,
            header_subtitle=header_subtitle,
            avatar_url=avatar_url,
            placeholder=placeholder,
            primary_color=primary_color
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get widget config",
            extra={"bot_id": bot_id, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get widget configuration"
        )


@router.post("/init", response_model=WidgetInitResponse)
async def initialize_widget(
    request: Request,
    payload: WidgetInitRequest,
    db: AsyncSession = Depends(get_db),
) -> WidgetInitResponse:
    """
    Initialize widget session.
    
    This endpoint:
    1. Extracts client IP address
    2. Finds or creates visitor based on bot_id + IP (same IP = same visitor)
    3. Creates or finds session with the provided session_token
    4. Returns visitor info and session details
    
    **Note**: This is called when widget first loads on a page.
    """
    try:
        client_ip = get_client_ip(request)
        user_agent = request.headers.get("User-Agent", "Unknown")
        referer = request.headers.get("Referer") or request.headers.get("Referrer")
        
        visitor_service = VisitorService(db)
        
        extra_data = {
            "user_agent": user_agent,
            "referrer": referer,
        }
        
        visitor = await visitor_service.find_or_create_visitor(
            bot_id=payload.bot_id,
            ip_address=client_ip,
            extra_data=extra_data
        )
        
        session = await visitor_service.create_or_find_session(
            bot_id=payload.bot_id,
            visitor_id=str(visitor.id),
            session_token=payload.session_token,
            extra_data=extra_data
        )
        
        await db.commit()
        
        visitor_profile = VisitorProfile(
            name=visitor.name,
            email=visitor.email,
            phone=visitor.phone,
            address=visitor.address
        )
        
        logger.info(
            "Widget initialized",
            extra={
                "bot_id": payload.bot_id,
                "visitor_id": str(visitor.id),
                "session_id": str(session.id),
                "ip": client_ip,
                "is_new_visitor": visitor.created_at == visitor.updated_at,
            }
        )
        
        return WidgetInitResponse(
            visitor_id=str(visitor.id),
            session_id=str(session.id),
            session_token=payload.session_token,
            visitor_profile=visitor_profile
        )
    
    except Exception as e:
        await db.rollback()
        logger.error(
            "Widget initialization failed",
            extra={"bot_id": payload.bot_id, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initialize widget session"
        )


@router.post("/chat", response_model=WidgetChatResponse)
async def widget_chat(
    payload: WidgetChatRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> WidgetChatResponse:
    """
    Create a chat task for widget message.
    
    This is a convenience endpoint that wraps /api/v1/chat/ask
    but uses session_token instead of bot_id for widget usage.
    
    Flow:
    1. Get session by session_token
    2. Create chat task with bot_id from session
    3. Return task_id and stream_url
    """
    try:
        session = await chat_service.get_session_by_token(payload.session_token, db)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        chat_request = ChatAskRequest(
            bot_id=str(session.bot_id),
            session_token=payload.session_token,
            query=payload.message,
            conversation_history=payload.conversation_history
        )
        
        task_id = await chat_service.create_task(chat_request, db, redis)
        stream_url = f"{request.app.root_path or ''}/api/v1/chat/stream/{task_id}"
        
        return WidgetChatResponse(
            task_id=task_id,
            status=TaskStatus.QUEUED.value,
            stream_url=stream_url
        )
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error(
            f"Widget chat failed: {str(e)}\n{traceback.format_exc()}",
            extra={"session_token": payload.session_token, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process chat message"
        )


@router.post("/admin/upload", dependencies=[Depends(Root)])
async def upload_widget_file(
    request: Request,
    file: UploadFile = File(...),
    version: Optional[str] = None,
) -> dict:
    """
    Upload widget JavaScript file to MinIO.
    
    **Root user only.**
    
    This endpoint allows root users to:
    - Upload new widget.js file
    - Update existing widget
    - Specify version (default: latest)
    
    The file will be stored in MinIO public bucket and served via CDN.
    """
    try:
        content = await file.read()
        file_size = len(content)
        
        uploaded_keys = widget_service.upload_widget(
            file_data=io.BytesIO(content),
            filename=file.filename,
            file_size=file_size,
            version=version
        )
        
        # Get base URL from request
        base_url = f"{request.url.scheme}://{request.url.netloc}"
        
        latest_url = widget_service.get_public_url(base_url=base_url)
        versioned_url = widget_service.get_public_url(version=version, base_url=base_url) if version else None
        embed_snippet = widget_service.generate_embed_snippet(base_url=base_url)
        
        return {
            "success": True,
            "message": WidgetFile.SUCCESS_UPLOADED,
            "file": {
                "filename": file.filename,
                "size": file_size,
                "version": version or "latest"
            },
            "urls": {
                "latest": latest_url,
                "versioned": versioned_url
            },
            "embed_snippet": embed_snippet
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            "Failed to upload widget",
            extra={"error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload widget: {str(e)}"
        )


@router.get("/admin/list", dependencies=[Depends(Root)])
async def list_widget_files() -> dict:
    """
    List all uploaded widget files in MinIO.
    
    **Root user only.**
    """
    try:
        files = widget_service.list_widgets()
        
        return {
            "success": True,
            "count": len(files),
            "files": files
        }
        
    except Exception as e:
        logger.error(
            "Failed to list widget files",
            extra={"error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list widget files: {str(e)}"
        )


@router.delete("/admin/delete/{filename:path}", dependencies=[Depends(Root)])
async def delete_widget_file(filename: str) -> dict:
    """
    Delete a widget file from MinIO.
    
    **Root user only.**
    
    Example: DELETE /api/v1/widget/admin/delete/widget/widget.v1.0.0.js
    """
    try:
        widget_service.delete_widget(filename)
        
        return {
            "success": True,
            "message": f"{WidgetFile.SUCCESS_DELETED}: {filename}"
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            "Failed to delete widget file",
            extra={"file_name": filename, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete widget file: {str(e)}"
        )


@router.get("/js")
async def serve_widget_js(v: Optional[str] = None):
    """
    Serve widget JavaScript file from MinIO.
    
    **Public endpoint - no authentication required.**
    
    Query parameters:
    - v: Version (optional). If not specified, serves latest version.
    
    Examples:
    - GET /api/v1/widget/js                    → Latest version
    - GET /api/v1/widget/js?v=1.0.0           → Specific version
    
    This endpoint:
    1. Fetches widget.js from MinIO public bucket
    2. Sets proper cache headers for Cloudflare CDN
    3. Returns JavaScript content
    """
    try:
        content = widget_service.get_widget(version=v)
        
        is_versioned = v is not None
        cache_control = widget_service.get_cache_control(is_versioned)
        
        return Response(
            content=content,
            media_type="application/javascript",
            headers={
                "Cache-Control": cache_control,
                "Access-Control-Allow-Origin": "*",
                "X-Content-Type-Options": "nosniff",
                "X-Widget-Version": v or "latest"
            }
        )
        
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{WidgetFile.ERROR_FILE_NOT_FOUND}{f' (version {v})' if v else ''}"
        )
    except Exception as e:
        logger.error(
            "Failed to serve widget",
            extra={"version": v, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to serve widget file"
        )

