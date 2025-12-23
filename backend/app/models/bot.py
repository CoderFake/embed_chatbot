import uuid
from sqlalchemy import Column, String, Boolean, Enum as SQLEnum, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin
from app.common.enums import BotStatus


class Bot(Base, TimestampMixin):
    """
    Chatbot configuration.
    Each bot has its own knowledge base (Milvus collection) and settings.
    
    Note: Milvus collection name is derived from bot_key.replace("-", "_")
    Example: bot_key="customer-support" -> collection="customer_support"
    
    Allowed origins are managed through AllowedOrigin model.
    """
    __tablename__ = "bots"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    bot_key = Column(String(50), unique=True, nullable=False, index=True)
    language = Column(String(50), nullable=True)
    status = Column(SQLEnum(BotStatus), default=BotStatus.DRAFT, nullable=False, index=True)
    display_config = Column(JSONB, default=dict, nullable=False)
    desc = Column(Text, nullable=True)
    assessment_questions = Column(JSONB, default=list, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True) 
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    
    # Relationships
    provider_config = relationship(
        "ProviderConfig", 
        back_populates="bot", 
        uselist=False, 
        cascade="all, delete-orphan"
    )
    allowed_origins = relationship(
        "AllowedOrigin", 
        back_populates="bot", 
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Bot(id={self.id}, name={self.name}, bot_key={self.bot_key})>"
    
    @property
    def collection_name(self) -> str:
        """
        Get Milvus collection name from bot ID.
        Format: bot_{bot_id} with hyphens replaced by underscores.
        """
        return f"bot_{str(self.id)}".replace("-", "_")
    
    @property
    def bucket_name(self) -> str:
        """
        Get MinIO/S3 bucket name from bot ID.
        Uses UUID without hyphens (S3-compatible naming).
        
        Example: id=a1b2c3d4-e5f6-g7h8-i9j0-k1l2m3n4o5p6
                 -> bucket_name=a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
        
        S3 naming rules:
        - 3-63 characters
        - Lowercase letters, numbers, hyphens, dots only
        - No underscores allowed
        """
        return str(self.id).replace("-", "")
    
    @property
    def origin(self) -> str | None:
        """
        Get the single allowed origin for this bot.
        Only returns active and non-deleted origin.
        """
        if self.allowed_origins:
            for allowed_origin in self.allowed_origins:
                if allowed_origin.is_active and not allowed_origin.is_deleted:
                    return allowed_origin.origin
        return None


class ProviderConfig(Base, TimestampMixin):
    """
    LLM provider configuration for a specific bot.
    Supports multiple API keys for load balancing (stored in api_keys JSONB).
    """
    __tablename__ = "provider_configs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bot_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("bots.id", ondelete="CASCADE"), 
        unique=True, 
        nullable=False, 
        index=True
    )
    provider_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("providers.id"), 
        nullable=False, 
        index=True
    )
    model_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("models.id"), 
        nullable=True, 
        index=True
    )
    
    api_keys = Column(JSONB, default=list, nullable=False)
    
    is_active = Column(Boolean, default=True, nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    config = Column(JSONB, default=dict, nullable=False)
    
    # Relationships
    bot = relationship("Bot", back_populates="provider_config")
    
    def __repr__(self) -> str:
        return f"<ProviderConfig(id={self.id}, bot_id={self.bot_id})>"


class AllowedOrigin(Base, TimestampMixin):
    """
    Allowed origins (CORS) for widget embedding.
    Each bot can have multiple allowed origins.
    """
    __tablename__ = "allowed_origins"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bot_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("bots.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    origin = Column(String(255), nullable=False)
    sitemap_urls = Column(JSONB, default=list, nullable=False)  
    is_active = Column(Boolean, default=True, nullable=False)  
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    
    # Relationships
    bot = relationship("Bot", back_populates="allowed_origins")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('bot_id', 'origin', name='uq_bot_origin'),
    )
    
    def __repr__(self) -> str:
        return f"<AllowedOrigin(id={self.id}, bot_id={self.bot_id}, origin={self.origin})>"

