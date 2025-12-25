from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
from uuid import UUID

from app.core.database import get_db, get_redis
from app.core.dependencies import Admin
from app.common.types import CurrentUser
from app.services.worker import WorkerService
from app.schemas.worker import (
    BotWorkerCreate,
    BotWorkerUpdate,
    BotWorkerResponse,
    BotWorkerListResponse
)
from app.common.enums import ScheduleType
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.post("/{bot_id}/workers", response_model=BotWorkerResponse, dependencies=[Depends(Admin)])
async def create_or_update_worker(
    bot_id: UUID,
    worker_data: BotWorkerCreate,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(Admin)
):
    """
    Create or update bot worker configuration.
    
    Uses (bot_id, schedule_type) unique constraint for upsert behavior.
    If worker exists, it will be updated. Otherwise, a new one is created.
    
    **Required role:** admin, root
    """
    worker_service = WorkerService(db, redis)
    
    try:
        worker = await worker_service.create_or_update(
            bot_id=bot_id,
            schedule_type=worker_data.schedule_type,
            auto=worker_data.auto,
            schedule_time=worker_data.schedule_time,
            frequency=worker_data.frequency,
            user_email=current_user.email
        )
        
        await db.commit()
        return worker
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to create/update worker for bot {bot_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create/update worker: {str(e)}"
        )


@router.get("/{bot_id}/workers", response_model=BotWorkerListResponse, dependencies=[Depends(Admin)])
async def list_workers(
    bot_id: UUID,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """
    Get all workers configured for a bot.
    
    **Required role:** admin, root
    """
    worker_service = WorkerService(db, redis)
    
    try:
        workers = await worker_service.get_all(bot_id)
        return BotWorkerListResponse(workers=workers)
    except HTTPException:
        raise


@router.get("/{bot_id}/workers/{schedule_type}", response_model=BotWorkerResponse, dependencies=[Depends(Admin)])
async def get_worker(
    bot_id: UUID,
    schedule_type: ScheduleType,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """
    Get specific worker configuration by schedule type.
    
    **Required role:** admin, root
    """
    worker_service = WorkerService(db, redis)
    
    try:
        worker = await worker_service.get_by_type(bot_id, schedule_type)
        return worker
    except HTTPException:
        raise


@router.patch("/{bot_id}/workers/{schedule_type}", response_model=BotWorkerResponse, dependencies=[Depends(Admin)])
async def update_worker(
    bot_id: UUID,
    schedule_type: ScheduleType,
    worker_data: BotWorkerUpdate,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(Admin)
):
    """
    Partially update worker configuration.
    
    **Required role:** admin, root
    """
    worker_service = WorkerService(db, redis)
    
    try:
        worker = await worker_service.update(
            bot_id=bot_id,
            schedule_type=schedule_type,
            auto=worker_data.auto,
            schedule_time=worker_data.schedule_time,
            frequency=worker_data.frequency,
            user_email=current_user.email
        )
        
        await db.commit()
        return worker
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to update worker {schedule_type} for bot {bot_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update worker: {str(e)}"
        )


@router.delete("/{bot_id}/workers/{schedule_type}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(Admin)])
async def delete_worker(
    bot_id: UUID,
    schedule_type: ScheduleType,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(Admin)
):
    """
    Delete worker configuration.
    
    **Required role:** admin, root
    """
    worker_service = WorkerService(db, redis)
    
    try:
        await worker_service.delete(
            bot_id=bot_id,
            schedule_type=schedule_type,
            user_email=current_user.email
        )
        
        await db.commit()
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to delete worker {schedule_type} for bot {bot_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete worker: {str(e)}"
        )
