from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, EmailStr, ConfigDict, Field, field_validator
from uuid import UUID
import re

from app.models.visitor import SessionStatus


class VisitorInfoUpdate(BaseModel):
    """Schema for updating visitor information with validation."""
    name: Optional[str] = Field(None, min_length=2, max_length=50, description="Visitor full name")
    email: Optional[EmailStr] = Field(None, description="Visitor email address")
    phone: Optional[str] = Field(None, min_length=8, max_length=20, description="Visitor phone number")
    address: Optional[str] = Field(None, min_length=5, max_length=255, description="Visitor address")
    
    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        """Validate phone number format."""
        if v is None:
            return v
        
        phone_clean = re.sub(r'[\s\-\(\)\.]+', '', v)
        
        if not re.match(r'^\+?\d{8,15}$', phone_clean):
            raise ValueError('Invalid phone number format. Must be 8-15 digits.')
        
        return v 
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        """Validate and sanitize name."""
        if v is None:
            return v
        return v.strip()
    
    @field_validator('address')
    @classmethod
    def validate_address(cls, v: Optional[str]) -> Optional[str]:
        """Validate and sanitize address."""
        if v is None:
            return v
        return v.strip()
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "John Doe",
                "email": "john@example.com",
                "phone": "+1234567890",
                "address": "123 Main St, City, Country"
            }
        }


class VisitorResponse(BaseModel):
    """Schema for visitor response."""
    id: UUID
    bot_id: UUID
    ip_address: Optional[str] = None
    name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    lead_score: int
    lead_assessment: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
    
    @field_validator('ip_address', mode='before')
    @classmethod
    def serialize_ip_address(cls, v):
        """Convert IPv4Address/IPv6Address objects to string."""
        if v is None:
            return None
        return str(v)


class ChatSessionResponse(BaseModel):
    """Schema for chat session response."""
    id: UUID
    bot_id: UUID
    visitor_id: UUID
    status: SessionStatus
    started_at: datetime
    ended_at: Optional[datetime] = None
    extra_data: Dict[str, Any]
    
    model_config = ConfigDict(from_attributes=True)


class ChatMessageCreate(BaseModel):
    """Schema for creating chat message."""
    query: str = Field(..., min_length=1)


class ChatMessageResponse(BaseModel):
    """Schema for chat message response."""
    id: UUID
    session_id: UUID
    query: str
    response: str
    extra_data: Dict[str, Any]
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class AssessmentQuestionResult(BaseModel):
    """Schema for single assessment question result."""
    question: str = Field(..., description="Assessment question")
    answer: str = Field(..., description="LLM's answer based on chat history")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    relevant_messages: list[str] = Field(default_factory=list, description="Relevant chat messages used")


class VisitorAssessmentResponse(BaseModel):
    """Schema for visitor assessment response."""
    visitor_id: str = Field(..., description="Visitor UUID")
    bot_id: str = Field(..., description="Bot UUID")
    assessed_at: datetime = Field(..., description="Assessment timestamp")
    total_messages: int = Field(..., description="Total chat messages analyzed")
    results: list[AssessmentQuestionResult] = Field(..., description="Assessment results per question")
    summary: str = Field(..., description="Overall assessment summary")

