"""Statistics schemas for API responses."""
from pydantic import BaseModel
from app.common.enums import TimePeriod


class StatsSummary(BaseModel):
    """Dashboard summary statistics."""
    total_bots: int
    total_users: int
    total_visitors: int


class VisitorActivity(BaseModel):
    """Single visitor activity data point."""
    timestamp: str
    visitor_count: int


class VisitorActivityResponse(BaseModel):
    """Response for visitor activity endpoint."""
    data: list[VisitorActivity]
