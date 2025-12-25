from datetime import time as Time
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID

from app.common.enums import ScheduleType, Frequency


# ============================================================================
# Bot Worker Schemas
# ============================================================================

class BotWorkerBase(BaseModel):
    """Base bot worker schema."""
    schedule_type: ScheduleType = Field(..., description="Type of worker schedule")
    auto: bool = Field(default=False, description="Enable/disable automatic execution")
    schedule_time: Time = Field(..., description="Time to run the worker (HH:MM:SS)")
    frequency: Frequency = Field(Frequency.DAILY, description="Frequency of worker execution")


class BotWorkerCreate(BotWorkerBase):
    """
    Schema for creating a bot worker.
    Creates or updates based on (bot_id, schedule_type) unique constraint.
    """
    pass


class BotWorkerUpdate(BaseModel):
    """Schema for updating bot worker."""
    auto: Optional[bool] = Field(None, description="Enable/disable worker")
    schedule_time: Optional[Time] = Field(None, description="Update schedule time")
    frequency: Optional[Frequency] = Field(None, description="Update execution frequency")


class BotWorkerResponse(BotWorkerBase):
    """Schema for bot worker response."""
    id: UUID
    bot_id: UUID
    
    model_config = ConfigDict(from_attributes=True)


class BotWorkerListResponse(BaseModel):
    """Schema for listing all workers for a bot."""
    workers: list[BotWorkerResponse] = Field(default_factory=list)
