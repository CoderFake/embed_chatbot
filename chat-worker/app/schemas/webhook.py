"""Pydantic schemas for webhook payloads."""
from __future__ import annotations
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ChatCompletionPayload(BaseModel):
    """
    Payload sent from chat-worker to backend after a chat task is completed.
    """
    session_token: str
    bot_id: str
    visitor_id: str
    query: str
    response: str
    tokens_input: int
    tokens_output: int
    cost_usd: float = 0.0
    model_id: Optional[str] = None
    visitor_info: Dict[str, Any] = Field(default_factory=dict)
    long_term_memory: str | None = None 
    session_summary: Dict[str, Any] = Field(default_factory=dict)
    extra_data: Dict[str, Any] = Field(default_factory=dict)
    is_contact: bool = False
