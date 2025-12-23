from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, field_validator
from uuid import UUID

from app.models.provider import AuthType, ProviderStatus, ModelType


class ModelPricingConfig(BaseModel):
    """Pricing configuration for a model."""
    cost_per_1k_input: float = Field(
        default=0.0,
        ge=0.0,
        description="Cost per 1,000 input tokens in USD"
    )
    cost_per_1k_output: float = Field(
        default=0.0,
        ge=0.0,
        description="Cost per 1,000 output tokens in USD"
    )
    currency: str = Field(
        default="USD",
        description="Currency code (ISO 4217)"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "cost_per_1k_input": 0.0015,
                "cost_per_1k_output": 0.002,
                "currency": "USD"
            }
        }
    )


class ModelExtraData(BaseModel):
    """Extra data structure for Model."""
    cost_per_1k_input: Optional[float] = Field(
        None,
        ge=0.0,
        description="Cost per 1,000 input tokens in USD"
    )
    cost_per_1k_output: Optional[float] = Field(
        None,
        ge=0.0,
        description="Cost per 1,000 output tokens in USD"
    )
    currency: Optional[str] = Field(
        None,
        description="Currency code (default: USD)"
    )
    
    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={
            "example": {
                "cost_per_1k_input": 0.0015,
                "cost_per_1k_output": 0.002,
                "currency": "USD"
            }
        }
    )


class ProviderBase(BaseModel):
    """Base provider schema."""
    name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., min_length=1, max_length=50, pattern="^[a-z0-9-]+$")
    api_base_url: str = Field(..., min_length=1, max_length=255)
    auth_type: AuthType = AuthType.API_KEY


class ProviderCreate(ProviderBase):
    """Schema for creating a new provider."""
    extra_data: Dict[str, Any] = Field(default_factory=dict)


class ProviderUpdate(BaseModel):
    """Schema for updating provider."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    api_base_url: Optional[str] = Field(None, min_length=1, max_length=255)
    auth_type: Optional[AuthType] = None
    status: Optional[ProviderStatus] = None
    extra_data: Optional[Dict[str, Any]] = None


class ProviderResponse(ProviderBase):
    """Schema for provider response."""
    id: UUID
    status: ProviderStatus
    extra_data: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class ModelBase(BaseModel):
    """Base model schema."""
    name: str = Field(..., min_length=1, max_length=100)
    model_type: ModelType = ModelType.CHAT
    context_window: int = Field(..., gt=0)
    pricing: float = Field(default=0.0, ge=0.0)


class ModelCreate(ModelBase):
    """Schema for creating a new model."""
    extra_data: ModelExtraData = Field(
        default_factory=ModelExtraData,
        description="Additional model configuration including pricing details"
    )
    
    @field_validator('extra_data', mode='before')
    @classmethod
    def validate_extra_data(cls, v):
        """Convert dict to ModelExtraData if needed."""
        if isinstance(v, dict):
            return ModelExtraData(**v)
        return v


class ModelUpdate(BaseModel):
    """Schema for updating model."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    model_type: Optional[ModelType] = None
    context_window: Optional[int] = Field(None, gt=0)
    pricing: Optional[float] = Field(None, ge=0.0)
    is_active: Optional[bool] = None
    extra_data: Optional[ModelExtraData] = Field(
        None,
        description="Additional model configuration including pricing details"
    )
    
    @field_validator('extra_data', mode='before')
    @classmethod
    def validate_extra_data(cls, v):
        """Convert dict to ModelExtraData if needed."""
        if v is None:
            return None
        if isinstance(v, dict):
            return ModelExtraData(**v)
        return v


class ModelResponse(ModelBase):
    """Schema for model response."""
    id: UUID
    provider_id: UUID
    is_active: bool
    extra_data: ModelExtraData
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    
    @field_validator('extra_data', mode='before')
    @classmethod
    def validate_extra_data(cls, v):
        """Convert dict to ModelExtraData if needed."""
        if isinstance(v, dict):
            return ModelExtraData(**v)
        return v
    
    model_config = ConfigDict(from_attributes=True)

