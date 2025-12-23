"""Chat task schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from app.utils.datetime_utils import now
from app.common.enums import TaskStatus


class ChatAskRequest(BaseModel):
    """Request body for POST /chat/ask."""

    query: str = Field(..., min_length=1, max_length=2000, description="User question")
    bot_id: str = Field(..., description="Bot ID")
    session_token: str = Field(..., description="Session token (UUID from frontend)")
    conversation_history: List[Dict[str, str]] = Field(
        default_factory=list,
        max_items=20,
        description="Previous conversation turns",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "query": "RAG là gì?",
                "bot_id": "bot_123",
                "session_token": "550e8400-e29b-41d4-a716-446655440000",
                "conversation_history": [
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Xin chào! Tôi có thể giúp gì?"},
                ],
            }
        }
    }


class ChatAskResponse(BaseModel):
    """Response body for POST /chat/ask."""

    task_id: str = Field(..., description="Unique task identifier")
    status: TaskStatus = Field(default=TaskStatus.QUEUED, description="Initial task status")
    created_at: datetime = Field(default_factory=now, description="Creation timestamp")
    stream_url: str = Field(..., description="SSE stream endpoint")

    model_config = {
        "json_schema_extra": {
            "example": {
                "task_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "queued",
                "created_at": "2024-01-01T10:00:00Z",
                "stream_url": "/api/v1/chat/stream/550e8400-e29b-41d4-a716-446655440000",
            }
        }
    }


class TaskState(BaseModel):
    """Task state stored in Redis."""

    task_id: str
    status: TaskStatus
    query: str
    bot_id: str
    session_token: str
    conversation_history: List[Dict] = Field(default_factory=list)
    visitor_profile: Dict = Field(default_factory=dict)
    long_term_memory: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    result: Optional[Dict] = None


class CreateSessionRequest(BaseModel):
    """Request to create a new chat session."""
    
    bot_id: str = Field(..., description="Bot ID")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "bot_id": "bot_123"
            }
        }
    }


class CreateSessionResponse(BaseModel):
    """Response after creating a new session."""
    
    session_token: str = Field(..., description="Unique session token (UUID)")
    visitor_id: str = Field(..., description="Visitor ID")
    bot_id: str = Field(..., description="Bot ID")
    created_at: datetime = Field(..., description="Session creation timestamp")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "session_token": "550e8400-e29b-41d4-a716-446655440000",
                "visitor_id": "visitor_789",
                "bot_id": "bot_123",
                "created_at": "2024-01-01T10:00:00Z"
            }
        }
    }


class CloseSessionRequest(BaseModel):
    """Request body for closing a session."""
    
    reason: Optional[str] = Field(None, description="Reason for closing (user_closed, timeout, etc.)")
    duration_seconds: Optional[int] = Field(None, description="Total session duration in seconds")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "reason": "user_closed",
                "duration_seconds": 300
            }
        }
    }


class CloseSessionResponse(BaseModel):
    """Response for session close."""
    
    session_id: str = Field(..., description="Session ID")
    status: str = Field(..., description="Session status")
    ended_at: str = Field(..., description="Session end timestamp")
    message: str = Field(default="Session closed successfully", description="Response message")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "session_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "closed",
                "ended_at": "2024-01-01T10:05:00Z",
                "message": "Session closed successfully"
            }
        }
    }


class SessionStatusResponse(BaseModel):
    """Response for getting session status."""
    
    session_id: str = Field(..., description="Session ID")
    session_token: str = Field(..., description="Session token")
    status: str = Field(..., description="Session status")
    started_at: str = Field(..., description="Session start timestamp")
    ended_at: Optional[str] = Field(None, description="Session end timestamp")
    visitor_id: str = Field(..., description="Visitor ID")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "session_id": "550e8400-e29b-41d4-a716-446655440000",
                "session_token": "550e8400-e29b-41d4-a716-446655440000",
                "status": "active",
                "started_at": "2024-01-01T10:00:00Z",
                "ended_at": None,
                "visitor_id": "visitor_789"
            }
        }
    }
