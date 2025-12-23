"""
Statistics API endpoints for dashboard analytics.
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.common.enums import TimePeriod
from app.schemas.stats import StatsSummary, VisitorActivityResponse
from app.services.stats import StatsService

router = APIRouter()


@router.get("/stats/summary", response_model=StatsSummary)
async def get_stats_summary(
    db: AsyncSession = Depends(get_db)
):
    """
    Get dashboard summary statistics.
    
    Returns:
        - total_bots: Count of active bots
        - total_users: Count of all users
        - total_visitors: Count of unique visitors
    """
    service = StatsService(db)
    return await service.get_summary()


@router.get("/stats/visitor-activity", response_model=VisitorActivityResponse)
async def get_visitor_activity(
    bot_id: Optional[str] = Query(None, description="Bot ID to filter by"),
    period: TimePeriod = Query(TimePeriod.DAY, description="Time grouping period"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get visitor activity time-series data.
    
    Args:
        bot_id: Filter by specific bot (optional, defaults to first bot)
        period: Time grouping - 'day' (hourly), 'month' (daily), 'year' (monthly)
        
    Returns:
        Array of visitor activity data points with timestamp and count
    """
    service = StatsService(db)
    data = await service.get_visitor_activity(bot_id=bot_id, period=period)
    return VisitorActivityResponse(data=data)
