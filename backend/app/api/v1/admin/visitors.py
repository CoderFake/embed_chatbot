"""
Admin API for visitor management and lead grading.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
from typing import Optional
import json
import asyncio

from app.core.dependencies import Admin, get_db, get_redis, verify_admin_token
from app.core.database import redis_manager
from app.common.types import CurrentUser
from app.schemas.visitor import VisitorResponse, VisitorAssessmentResponse
from app.services.visitor import VisitorService
from app.cache.keys import CacheKeys
from app.utils.logging import get_logger
from app.services.auth import AuthService
from app.common.enums import UserRole
from app.core.security import decode_token
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/visitors/stats/count")
async def get_visitors_count(
    bot_id: Optional[str] = Query(None, description="Filter by bot ID"),
    min_score: Optional[int] = Query(None, ge=0, le=100, description="Minimum lead score"),
    current_user: CurrentUser = Depends(Admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get total visitor count with optional filtering.
    
    This endpoint returns the total count of visitors, useful for statistics
    and dashboard displays without fetching all visitor data.
    
    Args:
        bot_id: Optional bot filter
        min_score: Optional minimum lead score filter
        current_user: Authenticated admin user
        db: Database session
        
    Returns:
        JSON with total count
    """
    visitor_service = VisitorService(db)
    total_count = await visitor_service.count_visitors(
        bot_id=bot_id,
        min_score=min_score
    )
    
    return {"total": total_count, "bot_id": bot_id}


@router.get("/visitors/{visitor_id}", response_model=VisitorResponse)
async def get_visitor_details(
    visitor_id: str,
    current_user: CurrentUser = Depends(Admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get visitor details including lead score and grading insights.
    Automatically marks visitor as viewed (is_new=false) when accessed.
    
    Returns complete visitor information:
    - Basic info (name, email, phone, address)
    - Lead scoring (score, category, assessment)
    - Timestamps
    
    Args:
        visitor_id: Visitor UUID
        current_user: Authenticated admin user
        db: Database session
        
    Returns:
        VisitorResponse with all visitor data
        
    Raises:
        404: If visitor not found
    """
    visitor_service = VisitorService(db)
    visitor = await visitor_service.get_visitor(visitor_id)
    
    if not visitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Visitor not found: {visitor_id}"
        )
    
    if visitor.is_new:
        visitor.is_new = False
        await db.commit()
        logger.info(f"Marked visitor {visitor_id} as viewed by admin {current_user.user_id}")
    
    return visitor


@router.get("/visitors", response_model=list[VisitorResponse])
async def list_visitors(
    bot_id: Optional[str] = Query(None, description="Filter by bot ID"),
    min_score: Optional[int] = Query(None, ge=0, le=100, description="Minimum lead score"),
    limit: int = Query(20, ge=1, le=100, description="Results limit"),
    offset: int = Query(0, ge=0, description="Results offset"),
    sort_by: Optional[str] = Query("assessed_at", description="Sort by: assessed_at, lead_score, created_at"),
    current_user: CurrentUser = Depends(Admin),
    db: AsyncSession = Depends(get_db)
):
    """
    List visitors with optional filtering.
    
    Supports filtering by:
    - bot_id: Show visitors for specific bot
    - min_score: Show only high-quality leads (hot/warm)
    
    Sorting options:
    - assessed_at (default): Recently assessed first
    - lead_score: Highest score first
    - created_at: Most recent visitors first
    
    Args:
        bot_id: Optional bot filter
        min_score: Optional minimum lead score filter
        limit: Max results to return
        offset: Pagination offset
        sort_by: Sort column (assessed_at, lead_score, created_at)
        current_user: Authenticated admin user
        db: Database session
        
    Returns:
        List of visitors matching criteria
    """
    visitor_service = VisitorService(db)
    return await visitor_service.list_visitors(
        bot_id=bot_id,
        min_score=min_score,
        limit=limit,
        offset=offset,
        sort_by=sort_by
    )


@router.post("/visitors/{visitor_id}/trigger-grading")
async def trigger_visitor_grading(
    visitor_id: str,
    force: bool = Query(False, description="Force re-grading even if already in progress"),
    current_user: CurrentUser = Depends(Admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Manually trigger visitor lead grading.
    
    Admin can manually trigger grading for any visitor to:
    - Re-evaluate lead quality after new conversations
    - Review and update lead scores
    - Debug grading algorithm
    
    Args:
        visitor_id: Visitor UUID to grade
        force: Skip anti-spam lock (default: false)
        current_user: Authenticated admin user
        db: Database session
        
    Returns:
        task_id: Grading task UUID for tracking
        
    Raises:
        404: If visitor not found or has no sessions
        400: If grading already in progress (unless force=true)
    """
    visitor_service = VisitorService(db)
    
    visitor = await visitor_service.get_visitor(visitor_id)
    if not visitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Visitor not found: {visitor_id}"
        )
    
    latest_session = await visitor_service.get_latest_session_for_visitor(visitor_id)
    if not latest_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No chat sessions found for visitor: {visitor_id}"
        )
    
    try:
        task_id = await visitor_service.trigger_lead_grading(
            visitor_id=visitor_id,
            bot_id=str(latest_session.bot_id),
            session_id=str(latest_session.id),
            force=force
        )
        
        logger.info(
            "Admin manually triggered visitor grading",
            extra={
                "admin_id": str(current_user.user_id),
                "visitor_id": visitor_id,
                "session_id": str(latest_session.id),
                "task_id": task_id,
                "forced": force
            }
        )
        
        return {
            "success": True,
            "task_id": task_id,
            "visitor_id": visitor_id,
            "session_id": str(latest_session.id),
            "message": "Visitor grading task created successfully"
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            "Failed to trigger visitor grading",
            extra={
                "admin_id": str(current_user.user_id),
                "visitor_id": visitor_id,
                "error": str(e)
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger grading: {str(e)}"
        )


@router.get("/grading/{task_id}/progress", status_code=status.HTTP_200_OK)
async def get_grading_progress(
    task_id: str,
    current_user: CurrentUser = Depends(Admin)
):
    """
    Subscribe to real-time grading progress updates via SSE.
    
    Returns a stream of JSON events with progress updates.
    """
    async def event_generator():
        pubsub = None
        try:
            channel = CacheKeys.task_progress_channel(task_id)
            redis_client = redis_manager.get_redis()
            pubsub = redis_client.pubsub()
            await pubsub.subscribe(channel)
            
            logger.info(f"SSE client connected for grading progress: {task_id}")
            
            yield f"data: {json.dumps({'status': 'connected', 'task_id': task_id})}\n\n"
            
            last_heartbeat = asyncio.get_event_loop().time()
            heartbeat_interval = 15
            
            while True:
                try:
                    message = await asyncio.wait_for(
                        pubsub.get_message(ignore_subscribe_messages=True),
                        timeout=1.0
                    )
                    
                    if message and message['type'] == 'message':
                        try:
                            data_str = message['data']
                            if isinstance(data_str, bytes):
                                data_str = data_str.decode()
                            
                            data = json.loads(data_str)
                            yield f"data: {json.dumps(data)}\n\n"
                            
                            if data.get('status') in ['COMPLETED', 'FAILED']:
                                logger.info(f"Grading progress stream ended for task {task_id}: {data.get('status')}")
                                break
                            
                            last_heartbeat = asyncio.get_event_loop().time()
                                
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to decode progress message: {e}")
                            continue
                
                except asyncio.TimeoutError:
                    current_time = asyncio.get_event_loop().time()
                    if current_time - last_heartbeat >= heartbeat_interval:
                        yield f": heartbeat\n\n"
                        last_heartbeat = current_time
                
        except asyncio.CancelledError:
            logger.info(f"SSE stream cancelled for grading task {task_id}")
            raise
        except Exception as e:
            logger.error(f"Error in grading progress stream for {task_id}: {e}", exc_info=True)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            if pubsub:
                await pubsub.unsubscribe(channel)
                await pubsub.close()
            logger.info(f"SSE connection closed for grading progress: {task_id}")
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.post("/visitors/{visitor_id}/assess")
async def assess_visitor(
    visitor_id: str,
    force: bool = Query(False, description="Force re-assessment even if already in progress"),
    current_user: CurrentUser = Depends(Admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Manually assess visitor using bot's assessment questions.
    
    Creates temporary Milvus collection from chat history,
    retrieves relevant context for each assessment question,
    and uses LLM to answer each question.
    
    Args:
        visitor_id: Visitor UUID to assess
        current_user: Authenticated admin user
        db: Database session
        
    Returns:
        task_id: Assessment task UUID for tracking
        
    Raises:
        404: If visitor not found or no sessions/bot
        400: If bot has no assessment questions
    """
    visitor_service = VisitorService(db)
    
    visitor = await visitor_service.get_visitor(visitor_id)
    if not visitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Visitor not found: {visitor_id}"
        )
    
    latest_session = await visitor_service.get_latest_session_for_visitor(visitor_id)
    if not latest_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No chat sessions found for visitor: {visitor_id}"
        )
    
    try:
        task_id = await visitor_service.trigger_visitor_assessment(
            visitor_id=visitor_id,
            bot_id=str(latest_session.bot_id),
            session_id=str(latest_session.id),
            force=force
        )
        
        logger.info(
            "Admin manually triggered visitor assessment",
            extra={
                "admin_id": str(current_user.user_id),
                "visitor_id": visitor_id,
                "session_id": str(latest_session.id),
                "task_id": task_id
            }
        )
        
        return {
            "success": True,
            "task_id": task_id,
            "visitor_id": visitor_id,
            "session_id": str(latest_session.id),
            "message": "Visitor assessment task created successfully"
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            "Failed to trigger visitor assessment",
            extra={
                "admin_id": str(current_user.user_id),
                "visitor_id": visitor_id,
                "error": str(e)
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger assessment: {str(e)}"
        )


@router.get("/visitors/{visitor_id}/active-assessment")
async def get_active_assessment(
    visitor_id: str,
    current_user: CurrentUser = Depends(Admin),
    redis: Redis = Depends(get_redis)
):
    """
    Check if visitor has an active assessment task.
    
    Returns task_id if assessment is in progress, null otherwise.
    Used by frontend to reconnect SSE after page refresh.
    
    Args:
        visitor_id: Visitor UUID
        current_user: Authenticated admin user
        redis: Redis client
        
    Returns:
        task_id if active, null if no active assessment
    """
    
    active_key = CacheKeys.assessment_active(visitor_id)
    task_id = await redis.get(active_key)
    
    if task_id:
        return {
            "active": True,
            "task_id": task_id.decode() if isinstance(task_id, bytes) else task_id
        }
    
    return {
        "active": False,
        "task_id": None
    }


@router.get("/visitors/active-assessments/bulk")
async def get_all_active_assessments(
    bot_id: Optional[str] = Query(None, description="Filter by bot ID"),
    current_user: CurrentUser = Depends(Admin),
    redis: Redis = Depends(get_redis)
):
    """
    Get all active assessments in one call (bulk operation).
    
    Returns a map of visitor_id -> task_id for all visitors with active assessments.
    This reduces N individual requests to 1 request.
    
    Args:
        bot_id: Optional filter by bot (not implemented yet, returns all)
        current_user: Authenticated admin user
        redis: Redis client
        
    Returns:
        Dictionary mapping visitor_id to task_id for all active assessments
    """
    
    pattern = "assessment_active:*"
    active_assessments = {}
    
    async for key in redis.scan_iter(match=pattern):
        key_str = key.decode() if isinstance(key, bytes) else key
        visitor_id = key_str.replace("assessment_active:", "")
        
        task_id = await redis.get(key)
        if task_id:
            active_assessments[visitor_id] = task_id.decode() if isinstance(task_id, bytes) else task_id
    
    logger.info(
        f"Fetched {len(active_assessments)} active assessments",
        extra={
            "admin_id": str(current_user.user_id),
            "count": len(active_assessments)
        }
    )
    
    return active_assessments




@router.get("/assessment/{task_id}/progress", status_code=status.HTTP_200_OK)
async def get_assessment_progress(
    task_id: str,
    token: str = Query(..., description="Access token for SSE authentication"),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """
    Subscribe to real-time assessment progress updates via SSE.
    
    SSE doesn't support custom headers, so token is passed via query string.
    
    Returns a stream of JSON events with progress updates.
    """

    await verify_admin_token(token, db)
    
    async def event_generator():
        pubsub = None
        try:
            channel = CacheKeys.task_progress_channel(task_id)
            redis_client = redis_manager.get_redis()
            pubsub = redis_client.pubsub()
            await pubsub.subscribe(channel)
            
            logger.info(f"SSE client connected for assessment progress: {task_id}")
            
            yield f"data: {json.dumps({'status': 'connected', 'task_id': task_id})}\n\n"
            
            last_heartbeat = asyncio.get_event_loop().time()
            heartbeat_interval = 15
            
            while True:
                try:
                    message = await asyncio.wait_for(
                        pubsub.get_message(ignore_subscribe_messages=True),
                        timeout=1.0
                    )
                    
                    if message and message['type'] == 'message':
                        try:
                            data_str = message['data']
                            if isinstance(data_str, bytes):
                                data_str = data_str.decode()
                            
                            data = json.loads(data_str)
                            yield f"data: {json.dumps(data)}\n\n"
                            
                            if data.get('status') in ['COMPLETED', 'FAILED']:
                                logger.info(f"Assessment progress stream ended for task {task_id}: {data.get('status')}")
                                break
                            
                            last_heartbeat = asyncio.get_event_loop().time()
                                
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to decode progress message: {e}")
                            continue
                
                except asyncio.TimeoutError:
                    current_time = asyncio.get_event_loop().time()
                    if current_time - last_heartbeat >= heartbeat_interval:
                        yield f": heartbeat\n\n"
                        last_heartbeat = current_time
                
        except asyncio.CancelledError:
            logger.info(f"SSE stream cancelled for assessment task {task_id}")
            raise
        except Exception as e:
            logger.error(f"Error in assessment progress stream for {task_id}: {e}", exc_info=True)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            if pubsub:
                await pubsub.unsubscribe(channel)
                await pubsub.close()
            logger.info(f"SSE connection closed for assessment progress: {task_id}")
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/visitors/{visitor_id}/chat-history")
async def get_visitor_chat_history(
    visitor_id: str,
    current_user: CurrentUser = Depends(Admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get chat history for a visitor including all sessions and messages.
    
    Returns list of chat sessions with their messages.
    
    Args:
        visitor_id: Visitor UUID
        current_user: Authenticated admin user
        db: Database session
        
    Returns:
        List of chat sessions with messages
        
    Raises:
        404: If visitor not found
    """
    visitor_service = VisitorService(db)
    visitor = await visitor_service.get_visitor(visitor_id)
    
    if not visitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Visitor not found: {visitor_id}"
        )
    
    chat_history = await visitor_service.get_chat_history(visitor_id)
    
    logger.info(
        "Admin fetched visitor chat history",
        extra={
            "admin_id": str(current_user.user_id),
            "visitor_id": visitor_id,
            "sessions_count": len(chat_history)
        }
    )
    
    return chat_history
