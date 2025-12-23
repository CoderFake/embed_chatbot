"""
Document API endpoints.
"""
import json
import uuid
import os
import asyncio
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from app.core.dependencies import get_db, get_redis, Admin
from app.core.security import decode_token, verify_token_type
from app.common.types import CurrentUser
from app.common.enums import DocumentStatus, JobStatus, UserRole
from app.schemas.document import (
    DocumentResponse,
    DocumentListResponse,
    DocumentJobResponse,
    BatchImportRequest,
    BatchImportResponse,
    ActiveTaskResponse,
    ActiveTasksListResponse
)
from app.services.document import DocumentService
from app.services.rabbitmq import rabbitmq_publisher
from app.cache.keys import CacheKeys
from app.utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post(
    "/bots/{bot_id}/documents/upload",
    response_model=DocumentJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload document for bot"
)
async def upload_document(
    bot_id: str,
    file: UploadFile = File(...),
    title: Optional[str] = None,
    current_user: CurrentUser = Depends(Admin),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """
    Upload document file for bot knowledge base.
    
    - **file**: Document file (PDF, DOCX, TXT)
    - **title**: Optional custom title (defaults to filename)
    
    Returns task info with SSE endpoint for progress tracking.
    """
    doc_service = DocumentService(db, redis)

    from app.services.notification import NotificationService
    notification_service = NotificationService(db, redis)

    try:
        document, task_id, local_file_path = await doc_service.create_from_file(
            bot_id=bot_id,
            user_id=current_user.user_id,
            file=file,
            title=title
        )

        await notification_service.create_task_notification(
            user_id=current_user.user_id,
            task_id=task_id,
            task_type="upload_document",
            title=f"Uploading {file.filename}",
            message="Processing document...",
            bot_id=bot_id
        )

        await db.commit()
        
        await redis.hset(
            CacheKeys.task_state(task_id),
            mapping={
                "task_id": task_id,
                "bot_id": bot_id,
                "progress": "0",
                "status": "PENDING",
                "message": "Task queued, waiting to start...",
                "timestamp": str(uuid.uuid4()) 
            }
        )
        await redis.expire(CacheKeys.task_state(task_id), 86400)
        
        await rabbitmq_publisher.publish_file_upload_task(
            task_id=task_id,
            document_id=str(document.id),
            bot_id=bot_id,
            file_path=local_file_path,
            collection_name=document.bot.collection_name
        )
        
        logger.info(
            f"Document upload task published",
            extra={
                "task_id": task_id,
                "document_id": str(document.id),
                "bot_id": bot_id,
                "user_id": current_user.user_id,
                "file_name": file.filename
            }
        )
        
        return DocumentJobResponse(
            job_id=task_id,
            job_type="process_document",
            status=JobStatus.PENDING.value,
            message="Document uploaded. Processing will start shortly.",
            sse_endpoint=f"/tasks/{task_id}/progress",
            document_id=document.id,
            bot_id=document.bot_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload document: {str(e)}"
        )


@router.post(
    "/documents/batch-import",
    response_model=BatchImportResponse,
    status_code=status.HTTP_200_OK,
    summary="[INTERNAL] Process batch import from file-server",
    include_in_schema=False
)
async def batch_import(
    request: BatchImportRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """
    **INTERNAL ONLY** - Called by file-server after each batch is inserted into Milvus.
    
    Backend ONLY validates and tracks progress for SSE.
    Does NOT process documents - file-server handles processing, webhook creates/updates records.
    
    This endpoint:
    1. Validates data consistency (chunk count)
    2. Calculates progress percentage
    3. Updates progress state in Redis for SSE streaming
    
    **Architecture:**
    - **Backend**: CRUD operations only
    - **File-server**: Processing (chunk, embed, Milvus insert, crawl)
    - **Webhook**: Document record creation after completion
    
    **Security:**
    - Only accessible from file-server container within Docker network
    - Not exposed in OpenAPI schema
    
    **Flow:**
    1. File-server inserts batch into Milvus
    2. File-server calls this endpoint with batch metadata
    3. Backend validates chunk count
    4. Backend updates progress in Redis
    5. SSE streams progress to client in real-time
    """
    try:
        if request.source_type == "file" and not request.file_path:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="file_path is required for source_type='file'"
            )
        elif request.source_type == "crawl" and not request.web_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="web_url is required for source_type='crawl'"
            )
        
        doc_service = DocumentService(db, redis)
        
        batch_data_list = [chunk.model_dump() for chunk in request.batch_data]
        
        result = await doc_service.validate_batch_import(
            task_id=request.task_id,
            bot_id=request.bot_id,
            document_id=request.document_id,
            batch_index=request.batch_index,
            total_batches=request.total_batches,
            chunks_in_batch=request.chunks_in_batch,
            batch_data=batch_data_list,
            source_type=request.source_type
        )
        
        progress_percentage = result.get("progress", 0)
        status_text = "completed" if result.get("completed", False) else "processing"
        
        progress_data = {
            "task_id": request.task_id,
            "bot_id": request.bot_id,
            "progress": str(progress_percentage),
            "status": status_text,
            "message": f"Batch {request.batch_index + 1}/{request.total_batches} imported ({request.chunks_in_batch} chunks)",
            "timestamp": str(uuid.uuid4()),
            "batch_info": json.dumps({
                "batch_index": request.batch_index,
                "total_batches": request.total_batches,
                "chunks_in_batch": request.chunks_in_batch,
                "source_type": request.source_type,
                "file_path": request.file_path,
                "web_url": request.web_url
            })
        }
        
        await redis.hset(
            CacheKeys.task_state(request.task_id),
            mapping=progress_data
        )
        await redis.expire(CacheKeys.task_state(request.task_id), 86400)
        
        channel = CacheKeys.task_progress_channel(request.task_id)
        await redis.publish(
            channel,
            json.dumps({
                "task_id": request.task_id,
                "bot_id": request.bot_id,
                "progress": progress_percentage,
                "status": status_text,
                "message": progress_data["message"],
                "timestamp": progress_data["timestamp"]
            })
        )
        
        logger.info(
            f"Batch import processed successfully: batch {request.batch_index + 1}/{request.total_batches}",
            extra={
                "task_id": request.task_id,
                "document_id": request.document_id,
                "bot_id": request.bot_id,
                "batch_index": request.batch_index,
                "chunks": request.chunks_in_batch,
                "progress": progress_percentage
            }
        )
        
        return BatchImportResponse(
            success=True,
            task_id=request.task_id,
            document_id=request.document_id,
            batch_index=request.batch_index,
            message=f"Batch {request.batch_index + 1}/{request.total_batches} imported successfully",
            validated_chunks=result["validated_chunks"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error processing batch import: {e}",
            extra={
                "task_id": request.task_id,
                "document_id": request.document_id,
                "batch_index": request.batch_index
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process batch import: {str(e)}"
        )


@router.get(
    "/tasks/{task_id}/progress",
    summary="Stream task processing progress (SSE)"
)
async def stream_task_progress(
    task_id: str,
    token: Optional[str] = None,
    redis: Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db)
):
    """
    Server-Sent Events (SSE) endpoint for real-time task processing progress.

    Streams progress updates from file-server via Redis PubSub.

    Client should open EventSource connection to this endpoint:
    ```javascript
    const eventSource = new EventSource('/api/v1/tasks/{task_id}/progress?token=YOUR_ACCESS_TOKEN');
    eventSource.addEventListener('progress', (event) => {
        const data = JSON.parse(event.data);
        console.log(data.progress, data.message);
    });
    ```

    Progress updates include:
    - task_id: Task identifier
    - bot_id: Bot identifier
    - progress: 0-100
    - status: processing, completed, failed
    - message: Human-readable status message
    - timestamp: ISO timestamp

    Supports reconnection: If client disconnects and reconnects, the last cached
    progress state will be sent first, then real-time updates continue.

    Authentication: Requires access token in query parameter (EventSource doesn't support headers)
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token"
        )

    try:
        payload = decode_token(token)
        verify_token_type(payload, "access")

        jti = payload.get("jti")
        if jti:
            is_blacklisted = await redis.exists(CacheKeys.blacklist(jti))
            if is_blacklisted:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has been revoked"
                )

        role = payload.get("role")
        if role not in [UserRole.ROOT.value, UserRole.ADMIN.value]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )

    channel = CacheKeys.task_progress_channel(task_id)
    
    async def event_generator():
        """Generate SSE events from Redis Pub/Sub"""
        pubsub = redis.pubsub()
        await pubsub.subscribe(channel)
        
        try:
            state_key = CacheKeys.task_state(task_id)
            cached_state = await redis.hgetall(state_key)
            if cached_state:
                state_data = {
                    k.decode() if isinstance(k, bytes) else k: 
                    v.decode() if isinstance(v, bytes) else v
                    for k, v in cached_state.items()
                }
                yield f"event: restore\ndata: {json.dumps(state_data)}\n\n"
            
            yield f"event: connected\ndata: {json.dumps({'message': 'Connected to progress stream', 'task_id': task_id})}\n\n"
            
            last_heartbeat = asyncio.get_event_loop().time()
            heartbeat_interval = 15
            
            while True:
                try:
                    message = await asyncio.wait_for(
                        pubsub.get_message(ignore_subscribe_messages=True),
                        timeout=1.0
                    )
                    
                    if message and message["type"] == "message":
                        data = message["data"]
                        
                        if isinstance(data, bytes):
                            data = data.decode()
                        
                        yield f"event: progress\ndata: {data}\n\n"
                        
                        try:
                            progress_data = json.loads(data)
                            status = progress_data.get("status", "").lower()
                            
                            if status in ["completed", "failed"]:
                                yield f"event: done\ndata: {data}\n\n"
                                logger.info(
                                    f"Task {task_id} completed with status: {status}",
                                    extra={"task_id": task_id, "status": status}
                                )
                                break
                        except json.JSONDecodeError:
                            logger.warning(f"Invalid JSON in progress data: {data}")
                            pass
                        
                        last_heartbeat = asyncio.get_event_loop().time()
                    
                except asyncio.TimeoutError:
                    current_time = asyncio.get_event_loop().time()
                    if current_time - last_heartbeat >= heartbeat_interval:
                        yield f": heartbeat\n\n"
                        last_heartbeat = current_time
                        
        except asyncio.CancelledError:
            logger.info(f"SSE stream cancelled for task {task_id}")
            raise
        except Exception as e:
            logger.error(f"Error in SSE stream: {e}", exc_info=True)
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no" 
        }
    )


@router.get(
    "/documents/{document_id}/stream",
    summary="[DEPRECATED] Stream document processing progress (SSE)",
    deprecated=True,
    include_in_schema=False
)
async def stream_document_progress(
    document_id: str,
    current_user: CurrentUser = Depends(Admin),
    redis: Redis = Depends(get_redis)
):
    """
    **DEPRECATED**: Use `/tasks/{task_id}/progress` instead.
    
    Server-Sent Events (SSE) endpoint for real-time document processing progress.
    
    This endpoint is kept for backward compatibility but will be removed in future versions.
    """
    channel = CacheKeys.document_progress_channel(document_id)
    
    async def event_generator():
        """Generate SSE events from Redis Pub/Sub with heartbeat"""
        pubsub = redis.pubsub()
        await pubsub.subscribe(channel)
        
        try:
            cache_key = f"{channel}:state"
            cached_state = await redis.get(cache_key)
            if cached_state:
                yield f"event: restore\ndata: {cached_state}\n\n"
            
            yield f"event: connected\ndata: {json.dumps({'message': 'Connected to progress stream'})}\n\n"
            
            last_heartbeat = asyncio.get_event_loop().time()
            heartbeat_interval = 15  
            
            while True:
                try:
                    message = await asyncio.wait_for(
                        pubsub.get_message(ignore_subscribe_messages=True),
                        timeout=1.0
                    )
                    
                    if message and message["type"] == "message":
                        data = message["data"]
                        
                        yield f"event: progress\ndata: {data}\n\n"
                        
                        try:
                            progress_data = json.loads(data)
                            if progress_data.get("status") in ["COMPLETED", "FAILED"]:
                                yield f"event: done\ndata: {data}\n\n"
                                break
                        except json.JSONDecodeError:
                            pass
                        
                        last_heartbeat = asyncio.get_event_loop().time()
                    
                except asyncio.TimeoutError:
                    current_time = asyncio.get_event_loop().time()
                    if current_time - last_heartbeat >= heartbeat_interval:
                        yield f": heartbeat\n\n"
                        last_heartbeat = current_time
                        
        except asyncio.CancelledError:
            logger.info(f"SSE stream cancelled for document {document_id}")
            raise
        except Exception as e:
            logger.error(f"Error in SSE stream: {e}", exc_info=True)
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get(
    "/bots/{bot_id}/documents",
    response_model=DocumentListResponse,
    summary="List documents for bot"
)
async def list_documents(
    bot_id: str,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status_filter: Optional[DocumentStatus] = None,
    sort_by: str = Query("created_at", description="Sort by: created_at, title"),
    current_user: CurrentUser = Depends(Admin),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """
    List documents for bot with pagination, sorting, and optional status filter.
    """
    doc_service = DocumentService(db, redis)
    
    documents, total = await doc_service.list_by_bot(
        bot_id=bot_id,
        page=page,
        size=size,
        status_filter=status_filter,
        sort_by=sort_by
    )
    
    pages = (total + size - 1) // size
    
    return DocumentListResponse(
        items=[DocumentResponse.from_orm_with_computed(doc) for doc in documents],
        total=total,
        page=page,
        size=size,
        pages=pages
    )


@router.get(
    "/documents/{document_id}",
    response_model=DocumentResponse,
    summary="Get document by ID"
)
async def get_document(
    document_id: str,
    current_user: CurrentUser = Depends(Admin),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """
    Get document details by ID.
    """
    doc_service = DocumentService(db, redis)
    
    document = await doc_service.get_by_id(document_id)
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    return DocumentResponse.from_orm_with_computed(document)


@router.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete document"
)
async def delete_document(
    document_id: str,
    current_user: CurrentUser = Depends(Admin),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """
    Delete document.
    
    This will:
    - Delete the document record
    - Delete file from MinIO
    - Delete vectors from Milvus
    - Invalidate cache
    """
    doc_service = DocumentService(db, redis)
    
    document = await doc_service.get_by_id(document_id)
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    await doc_service.delete(document)
    await db.commit()

    logger.info(f"Document deleted: {document_id} by user {current_user.user_id}")

