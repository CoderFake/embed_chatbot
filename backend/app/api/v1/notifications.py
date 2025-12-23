"""
Notification API endpoints.

Provides endpoints for:
- Getting user notifications
- Getting unread notification count
- Marking notifications as read
- Marking all notifications as read
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
from typing import List

from app.core.database import get_db, get_redis
from app.core.dependencies import get_current_user
from app.common.types import CurrentUser
from app.services.notification import NotificationService
from app.schemas.notification import NotificationResponse
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("", response_model=List[NotificationResponse])
async def get_notifications(
    unread_only: bool = Query(False, description="Only return unread notifications"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of records to return"),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Get notifications for the current user.
    
    **Query Parameters:**
    - **unread_only**: If true, only return unread notifications
    - **skip**: Number of records to skip (pagination)
    - **limit**: Maximum number of records to return (max 100)
    
    **Returns:**
    List of notifications ordered by creation date (newest first)
    """
    notification_service = NotificationService(db, redis)
    
    notifications = await notification_service.get_user_notifications(
        user_id=current_user.user_id,
        unread_only=unread_only,
        skip=skip,
        limit=limit
    )
    
    return notifications


@router.get("/count", response_model=dict)
async def get_unread_count(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Get count of unread notifications for the current user.
    
    **Returns:**
    ```json
    {
        "unread_count": 5
    }
    ```
    """
    notification_service = NotificationService(db, redis)
    
    count = await notification_service.get_unread_count(current_user.user_id)
    
    return {"unread_count": count}


@router.get("/active-tasks", response_model=List[dict])
async def get_active_tasks(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Get all active task processing notifications for the current user.

    Returns list of in-progress tasks (create_bot, recrawl, upload_document)
    that can be used to restore SSE connections after page reload.

    **Returns:**
    ```json
    [
        {
            "notification_id": "uuid",
            "task_id": "uuid",
            "task_type": "upload_document",
            "bot_id": "uuid",
            "progress": 50,
            "status": "processing",
            "title": "Uploading document",
            "message": "Processing file...",
            "created_at": "2025-11-16T10:00:00Z"
        }
    ]
    ```
    """
    notification_service = NotificationService(db, redis)

    active_tasks = await notification_service.get_active_tasks(current_user.user_id)

    return active_tasks


@router.put("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_notification_as_read(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Mark a specific notification as read.
    
    **Path Parameters:**
    - **notification_id**: UUID of the notification to mark as read
    
    **Returns:**
    204 No Content on success
    """
    notification_service = NotificationService(db, redis)
    
    success = await notification_service.mark_as_read(
        notification_id=notification_id,
        user_id=current_user.user_id
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    await db.commit()
    

@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Delete a specific notification.
    
    **Path Parameters:**
    - **notification_id**: UUID of the notification to delete
    
    **Returns:**
    204 No Content on success
    """
    notification_service = NotificationService(db, redis)
    
    success = await notification_service.delete_notification(
        notification_id=notification_id,
        user_id=current_user.user_id
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    await db.commit()


@router.put("/read-all", status_code=status.HTTP_200_OK)
async def mark_all_as_read(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Mark all notifications as read for the current user.
    
    **Returns:**
    ```json
    {
        "marked_count": 10
    }
    ```
    """
    notification_service = NotificationService(db, redis)
    
    count = await notification_service.mark_all_as_read(current_user.user_id)
    
    await db.commit()
    
    return {"marked_count": count}


@router.post("/cleanup-stale-tasks", status_code=status.HTTP_200_OK)
async def cleanup_stale_tasks(
    hours: int = Query(24, ge=1, le=168, description="Age threshold in hours"),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(get_current_user)
):
    """Clean up old stuck task notifications."""
    notification_service = NotificationService(db, redis)
    count = await notification_service.cleanup_stale_tasks(current_user.user_id, hours)
    await db.commit()
    return {"cleaned_count": count}
