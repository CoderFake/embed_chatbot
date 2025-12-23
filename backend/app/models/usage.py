import uuid
from datetime import datetime
from sqlalchemy import Column, Integer, Numeric, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.models.base import Base
from app.utils.datetime_utils import now


class UsageLog(Base):
    """
    Usage logging for tracking LLM API consumption.
    Records token usage and costs per message.
    """
    __tablename__ = "usage_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bot_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("bots.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    model_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("models.id"), 
        nullable=True,  # Allow NULL for backward compatibility
        index=True
    )
    session_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("chat_sessions.id"), 
        nullable=True, 
        index=True
    )
    message_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("chat_messages.id"), 
        nullable=True
    )
    tokens_input = Column(Integer, default=0, nullable=False)
    tokens_output = Column(Integer, default=0, nullable=False)
    cost_usd = Column(Numeric(10, 6), default=0, nullable=False)  # Cost in USD
    extra_data = Column(JSONB, default=dict, nullable=False)  # Provider response, etc.
    created_at = Column(DateTime(timezone=True), default=now, nullable=False, index=True)
    
    def __repr__(self) -> str:
        return f"<UsageLog(id={self.id}, bot_id={self.bot_id}, tokens={self.tokens_input + self.tokens_output})>"

