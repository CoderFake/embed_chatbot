import uuid
from datetime import time
from sqlalchemy import Column, Time, Boolean, Enum as SQLEnum, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base, TimestampMixin
from app.common.enums import ScheduleType, Frequency


class BotWorker(Base, TimestampMixin):
    """
    Bot worker automation configuration.
    Manages scheduled tasks for bots: auto-crawl, visitor grading, email notifications.
    """
    __tablename__ = "bot_workers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bot_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("bots.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    schedule_type = Column(
        SQLEnum(ScheduleType), 
        nullable=False, 
        index=True
    )
    auto = Column(Boolean, default=False, nullable=False)
    schedule_time = Column(Time, nullable=False)
    frequency = Column(SQLEnum(Frequency), default=Frequency.DAILY, nullable=False)
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('bot_id', 'schedule_type', name='uq_bot_schedule_type'),
    )
    
    def __repr__(self) -> str:
        return f"<BotWorker(id={self.id}, bot_id={self.bot_id}, schedule_type={self.schedule_type})>"
