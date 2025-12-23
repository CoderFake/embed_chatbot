"""Chat API endpoints."""
from __future__ import annotations

import json
import uuid
import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks, status
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.keys import CacheKeys
from app.core.database import get_db, get_redis
from app.core.dependencies import get_redis
from app.common.enums import TaskStatus
from app.schemas.chat import (
    ChatAskRequest, 
    ChatAskResponse,
    CreateSessionRequest,
    CreateSessionResponse,
    CloseSessionRequest,
    CloseSessionResponse,
    SessionStatusResponse,
)
from app.services.bot import BotService
from app.services.chat import chat_service
from app.utils.datetime_utils import now
from app.utils.logging import get_logger
from app.utils.request_utils import get_client_ip

router = APIRouter()
logger = get_logger(__name__)


@router.post("/sessions", response_model=CreateSessionResponse)
async def create_session(
    payload: CreateSessionRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> CreateSessionResponse:
    """
    Create a new chat session.
    
    - Extracts visitor IP from request headers
    - Creates or finds existing visitor
    - Generates new session with unique token
    - Returns session_token for subsequent chat requests
    """
    try:
        ip_address = get_client_ip(request)
        session = await chat_service.create_session(
            bot_id=payload.bot_id,
            ip_address=ip_address,
            db=db,
            redis=redis
        )
        
        return CreateSessionResponse(
            session_token=session.session_token,
            visitor_id=str(session.visitor_id),
            bot_id=str(session.bot_id),
            created_at=session.started_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.error(
            f"Failed to create session: {str(e)}\n{tb}",
            extra={"bot_id": payload.bot_id, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create chat session: {str(e)}"
        )


@router.post("/ask", response_model=ChatAskResponse)
async def create_chat_task(
    payload: ChatAskRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> ChatAskResponse:
    try:
        bot_service = BotService(db, redis)
        bot = await bot_service.get_by_id(payload.bot_id)
        if not bot:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bot not found")

        task_id = await chat_service.create_task(payload, db, redis)
        stream_url = f"{request.app.root_path or ''}/api/v1/chat/stream/{task_id}"

        return ChatAskResponse(
            task_id=task_id,
            status=TaskStatus.QUEUED,
            stream_url=stream_url,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create chat task: %s", e, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create chat task")


@router.get("/task/{task_id}")
async def get_task_status(task_id: str, redis: Redis = Depends(get_redis)):
    state = await chat_service.get_task_state(task_id, redis)
    if not state:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return state


@router.get("/stream/{task_id}")
async def stream_task_events(task_id: str, redis: Redis = Depends(get_redis)):
    """
    SSE endpoint for streaming chat task events.

    Returns real-time updates about task progress, completion, and errors.
    """
    state = await chat_service.get_task_state(task_id, redis)
    if not state:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    async def event_generator():
        """Generate SSE events from Redis PubSub."""
        pubsub = redis.pubsub()
        channel = CacheKeys.task_progress_channel(task_id)
      
        try:
            await pubsub.subscribe(channel)

            yield f"event: connected\ndata: {{\"message\": \"Connected to task stream\", \"task_id\": \"{task_id}\"}}\n\n"
            
            last_heartbeat = asyncio.get_event_loop().time()
            heartbeat_interval = 5

            while True:
                try:
                    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)

                    if message:
                        event_data = message.get("data", b"")
                        if isinstance(event_data, bytes):
                            event_data = event_data.decode("utf-8")
                        
                        if event_data:
                            try:
                                event_dict = json.loads(event_data)
                                
                                event_type = event_dict.get("type") or event_dict.get("status", "update")
                                
                                if "data" in event_dict:
                                    event_payload = event_dict["data"]
                                else:
                                    event_payload = {k: v for k, v in event_dict.items() 
                                                   if k not in ["task_id", "timestamp", "status"]}

                                yield f"event: {event_type}\ndata: {json.dumps(event_payload)}\n\n"

                                if event_dict.get("status") in ["completed", "failed"]:
                                    break

                            except json.JSONDecodeError:
                                logger.warning("Invalid event data received", extra={
                                    "task_id": task_id,
                                    "data": event_data[:100]
                                })
                        
                        last_heartbeat = asyncio.get_event_loop().time()

                    else:
                        current_time = asyncio.get_event_loop().time()
                        if current_time - last_heartbeat >= heartbeat_interval:
                            yield f": heartbeat\n\n"
                            last_heartbeat = current_time

                except asyncio.TimeoutError:
                    current_time = asyncio.get_event_loop().time()
                    if current_time - last_heartbeat >= heartbeat_interval:
                        yield f": heartbeat\n\n"
                        last_heartbeat = current_time
                    continue

                except Exception as e:
                    logger.error("Error in event stream", extra={
                        "task_id": task_id,
                        "error": str(e)
                    }, exc_info=e)
                    yield f"event: error\ndata: {{\"error\": \"Stream error\", \"message\": \"{str(e)}\"}}\n\n"
                    break

        except asyncio.CancelledError:
            raise
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control",
        }
    )


# ============================================================================
# Session Management Endpoints
# ============================================================================


@router.post("/sessions/{session_token}/close", response_model=CloseSessionResponse)
async def close_session(
    session_token: str,
    payload: CloseSessionRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> CloseSessionResponse:
    """
    Close a chat session.
    
    This endpoint:
    1. Finds session by session_token
    2. Updates status to CLOSED
    3. Sets ended_at timestamp
    4. Cancels active chat tasks for this session
    
    **Note**: This should be called when:
    - User closes the chat widget
    - Session times out after inactivity
    - System detects session should end
    """
    try:
        session = await chat_service.close_session(
            session_token=session_token,
            reason=payload.reason,
            duration_seconds=payload.duration_seconds,
            db=db
        )
        
        background_tasks.add_task(
            chat_service.cancel_session_tasks,
            session_token=session_token
        )
        
        return CloseSessionResponse(
            session_id=str(session.id),
            status=session.status.value,
            ended_at=session.ended_at.isoformat() if session.ended_at else "",
            message="Session closed successfully" if session.ended_at else "Session already closed"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to close session",
            extra={"session_token": session_token, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to close session"
        )


@router.get("/sessions/{session_token}/status", response_model=SessionStatusResponse)
async def get_session_status(
    session_token: str,
    db: AsyncSession = Depends(get_db),
) -> SessionStatusResponse:
    """Get current status of a chat session."""
    try:
        session = await chat_service.get_session_status(
            session_token=session_token,
            db=db
        )
        
        return SessionStatusResponse(
            session_id=str(session.id),
            session_token=session_token,
            status=session.status.value,
            started_at=session.started_at.isoformat(),
            ended_at=session.ended_at.isoformat() if session.ended_at else None,
            visitor_id=str(session.visitor_id),
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get session status",
            extra={"session_token": session_token, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get session status"
        )

