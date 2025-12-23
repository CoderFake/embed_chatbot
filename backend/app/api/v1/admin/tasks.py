"""
Admin API for task progress tracking.

SSE endpoints for monitoring long-running tasks:
- Document uploads
- Bot creation
- Sitemap crawling
"""
from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import json
import asyncio

from app.core.dependencies import Admin, get_db, verify_admin_token
from app.core.database import redis_manager
from app.common.types import CurrentUser
from app.cache.keys import CacheKeys
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/tasks/{task_id}/progress", status_code=status.HTTP_200_OK)
async def get_task_progress(
    task_id: str,
    token: str = Query(..., description="Access token for SSE authentication"),
    db: AsyncSession = Depends(get_db)
):
    """
    Subscribe to real-time task progress updates via SSE.
    
    Generic endpoint for all task types (upload, crawl, bot creation).
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
            
            yield f"data: {json.dumps({'status': 'connected', 'task_id': task_id})}\\n\\n"
            
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
                            yield f"data: {json.dumps(data)}\\n\\n"
                            
                            if data.get('status') in ['completed', 'failed', 'COMPLETED', 'FAILED']:
                                logger.info(f"Task progress stream ended for {task_id}: {data.get('status')}")
                                break
                            
                            last_heartbeat = asyncio.get_event_loop().time()
                                
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to decode progress message: {e}")
                            continue
                
                except asyncio.TimeoutError:
                    current_time = asyncio.get_event_loop().time()
                    if current_time - last_heartbeat >= heartbeat_interval:
                        yield f": heartbeat\\n\\n"
                        last_heartbeat = current_time
                
        except asyncio.CancelledError:
            logger.info(f"SSE stream cancelled for task {task_id}")
            raise
        except Exception as e:
            logger.error(f"Error in task progress stream for {task_id}: {e}", exc_info=True)
            yield f"data: {json.dumps({'error': str(e)})}\\n\\n"
        finally:
            if pubsub:
                await pubsub.unsubscribe(channel)
                await pubsub.close()
            logger.info(f"SSE connection closed for task progress: {task_id}")
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
