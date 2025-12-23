"""Statistics service for dashboard analytics."""
from datetime import timedelta
from typing import Optional, List
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bot import Bot
from app.models.user import User
from app.models.visitor import Visitor, ChatSession
from app.common.enums import TimePeriod
from app.schemas.stats import StatsSummary, VisitorActivity
from app.utils.datetime_utils import now
from app.utils.logging import get_logger

logger = get_logger(__name__)


class StatsService:
    """Service for statistics and analytics."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_summary(self) -> StatsSummary:
        """
        Get dashboard summary statistics.
        
        Returns:
            StatsSummary with total bots, users, and visitors
        """
        bots_result = await self.db.execute(
            select(func.count(Bot.id)).where(Bot.status == "active")
        )
        total_bots = bots_result.scalar() or 0
        
        users_result = await self.db.execute(
            select(func.count(User.id)).where(User.is_deleted == False)
        )
        total_users = users_result.scalar() or 0
        
        visitors_result = await self.db.execute(
            select(func.count(Visitor.id))
        )
        total_visitors = visitors_result.scalar() or 0
        
        return StatsSummary(
            total_bots=total_bots,
            total_users=total_users,
            total_visitors=total_visitors
        )

    async def get_visitor_activity(
        self,
        bot_id: Optional[str] = None,
        period: TimePeriod = TimePeriod.DAY
    ) -> List[VisitorActivity]:
        """
        Get visitor activity time-series data.
        
        Args:
            bot_id: Filter by specific bot (optional, defaults to first bot)
            period: Time grouping period
            
        Returns:
            List of visitor activity data points
        """
        if not bot_id:
            first_bot_result = await self.db.execute(
                select(Bot.id).where(Bot.status == "active").order_by(Bot.created_at).limit(1)
            )
            first_bot = first_bot_result.scalar_one_or_none()
            if not first_bot:
                return []
            bot_id = str(first_bot)
        
        current_time = now()
        if period == TimePeriod.DAY:
            start_time = current_time - timedelta(days=1)
            date_trunc = func.date_trunc('hour', ChatSession.started_at)
        elif period == TimePeriod.MONTH:
            start_time = current_time - timedelta(days=30)
            date_trunc = func.date_trunc('day', ChatSession.started_at)
        else:
            start_time = current_time - timedelta(days=365)
            date_trunc = func.date_trunc('month', ChatSession.started_at)
        
        stmt = (
            select(
                date_trunc.label('timestamp'),
                func.count(func.distinct(ChatSession.visitor_id)).label('visitor_count')
            )
            .where(
                ChatSession.bot_id == bot_id,
                ChatSession.started_at >= start_time
            )
            .group_by('timestamp')
            .order_by('timestamp')
        )
        
        result = await self.db.execute(stmt)
        rows = result.all()
        
        data = [
            VisitorActivity(
                timestamp=row.timestamp.isoformat(),
                visitor_count=row.visitor_count
            )
            for row in rows
        ]
        
        logger.info(
            "Fetched visitor activity stats",
            extra={
                "bot_id": bot_id,
                "period": period.value,
                "data_points": len(data)
            }
        )
        
        return data
