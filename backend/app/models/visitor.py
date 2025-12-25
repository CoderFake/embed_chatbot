import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, Enum as SQLEnum, ForeignKey, Text, CheckConstraint, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin
from app.common.enums import SessionStatus
from app.utils.datetime_utils import now


class Visitor(Base, TimestampMixin):
    """
    Widget visitor model.
    Tracks anonymous visitors using the chatbot widget.
    """
    __tablename__ = "visitors"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bot_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("bots.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    ip_address = Column(INET, nullable=True)
    name = Column(String(50), nullable=True)
    address = Column(String(255), nullable=True)
    phone = Column(String(255), nullable=True)
    email = Column(String(100), nullable=True)
    lead_score = Column(Integer, default=0, nullable=False)  # 0-100
    lead_assessment = Column(JSONB, default=dict, nullable=False)  # Scoring details
    assessed_at = Column(DateTime(timezone=True), nullable=True, index=True)
    is_new = Column(Boolean, default=False, nullable=False)  # Marks visitor as new after grading
    
    # Relationships
    sessions = relationship("ChatSession", back_populates="visitor", cascade="all, delete-orphan")
    
    # Constraints
    __table_args__ = (
        CheckConstraint('lead_score >= 0 AND lead_score <= 100', name='check_lead_score_range'),
    )
    
    def __repr__(self) -> str:
        return f"<Visitor(id={self.id}, name={self.name}, lead_score={self.lead_score})>"


class ChatSession(Base):
    """
    Chat session for tracking visitor conversations.
    Each visitor can have multiple sessions.
    """
    __tablename__ = "chat_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bot_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("bots.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    visitor_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("visitors.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    session_token = Column(String(255), unique=True, nullable=False, index=True)
    status = Column(
        SQLEnum(SessionStatus), 
        default=SessionStatus.ACTIVE, 
        nullable=False, 
        index=True
    )
    started_at = Column(DateTime(timezone=True), default=now, nullable=False)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    is_contact = Column(Boolean, default=False, nullable=False)
    extra_data = Column(JSONB, default=dict, nullable=False)  
    # Relationships
    visitor = relationship("Visitor", back_populates="sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<ChatSession(id={self.id}, visitor_id={self.visitor_id}, status={self.status})>"


class ChatMessage(Base):
    """
    Individual chat message in a session.
    Stores both query and response.
    """
    __tablename__ = "chat_messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("chat_sessions.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    query = Column(Text, nullable=True)
    response = Column(Text, nullable=True)
    extra_data = Column(JSONB, default=dict, nullable=False)
    created_at = Column(DateTime(timezone=True), default=now, nullable=False)
    
    # Relationships
    session = relationship("ChatSession", back_populates="messages")
    
    def __repr__(self) -> str:
        return f"<ChatMessage(id={self.id}, session_id={self.session_id})>"

