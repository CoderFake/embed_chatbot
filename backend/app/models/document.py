import uuid
from sqlalchemy import Column, String, Text, Enum as SQLEnum, ForeignKey, CheckConstraint, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin
from app.common.enums import DocumentStatus


class Document(Base, TimestampMixin):
    """
    Document model for bot knowledge base.
    Can be from URL (web crawling) or file upload.
    """
    __tablename__ = "documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bot_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("bots.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    user_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("users.id"), 
        nullable=True,  
        index=True
    )
    url = Column(String(1000), nullable=True)
    title = Column(String(500), nullable=False)
    content_hash = Column(String(64), nullable=False, index=True)
    status = Column(
        SQLEnum(DocumentStatus), 
        default=DocumentStatus.PENDING, 
        nullable=False, 
        index=True
    )
    file_path = Column(String(500), nullable=True) 
    raw_content = Column(Text, nullable=True)  
    extra_data = Column(JSONB, default=dict, nullable=False) 
    error_message = Column(Text, nullable=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id], lazy="joined")
    
    __table_args__ = (
        CheckConstraint('(url IS NOT NULL) OR (file_path IS NOT NULL)', name='check_url_or_file'),
    )
    
    def __repr__(self) -> str:
        return f"<Document(id={self.id}, title={self.title}, status={self.status})>"

