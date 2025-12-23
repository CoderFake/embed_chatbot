import uuid
from sqlalchemy import Column, String, Enum as SQLEnum, Integer, Float, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin, SoftDeleteMixin
from app.common.enums import AuthType, ProviderStatus, ModelType


class Provider(Base, TimestampMixin, SoftDeleteMixin):
    """
    LLM provider model (OpenAI, Anthropic, Ollama, etc.).
    """
    __tablename__ = "providers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    slug = Column(String(50), unique=True, nullable=False, index=True)
    api_base_url = Column(String(255), nullable=False)
    auth_type = Column(SQLEnum(AuthType), default=AuthType.API_KEY, nullable=False)
    status = Column(SQLEnum(ProviderStatus), default=ProviderStatus.ACTIVE, nullable=False, index=True)
    extra_data = Column(JSONB, default=dict, nullable=False)
    
    # Relationships
    models = relationship("Model", back_populates="provider", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Provider(id={self.id}, name={self.name}, slug={self.slug})>"


class Model(Base, TimestampMixin, SoftDeleteMixin):
    """
    LLM model configuration.
    
    Pricing stored in extra_data:
    {
        "cost_per_1k_input": 0.0015,
        "cost_per_1k_output": 0.002,
        "currency": "USD"
    }
    """
    __tablename__ = "models"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("providers.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    name = Column(String(100), nullable=False)
    model_type = Column(SQLEnum(ModelType), default=ModelType.CHAT, nullable=False, index=True)
    context_window = Column(Integer, nullable=False)
    pricing = Column(Float, default=0.0, nullable=False) 
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    extra_data = Column(JSONB, default=dict, nullable=False) 
    
    # Relationships
    provider = relationship("Provider", back_populates="models")
    
    def __repr__(self) -> str:
        return f"<Model(id={self.id}, name={self.name}, type={self.model_type})>"

