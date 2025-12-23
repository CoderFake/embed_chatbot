from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from uuid import UUID

from app.models.user import UserRole, InviteStatus


class InviteItem(BaseModel):
    """Single invite item in bulk request"""
    email: EmailStr
    role: UserRole = UserRole.MEMBER


class InviteCreate(BaseModel):
    """Schema for creating invites (supports bulk)."""
    invites: List[InviteItem] = Field(..., min_length=1, max_length=50)


class InviteResponse(BaseModel):
    """Schema for invite response."""
    id: UUID
    email: EmailStr
    token: str
    role: UserRole
    invited_by: UUID
    status: InviteStatus
    expires_at: datetime
    accepted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class BulkInviteResponse(BaseModel):
    """Response for bulk invite creation"""
    total: int
    created: int
    failed: int
    results: List[dict] 
