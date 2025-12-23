"""LangGraph state schema for chat workflow."""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Literal, Optional, TypedDict


class ChatState(TypedDict, total=False):
    """Core state for the chat graph."""
    # Input state
    task_id: str 
    query: str
    bot_id: str
    session_id: str
    conversation_history: List[Dict[str, str]]
    bot_config: Dict
    key_index: Optional[int]
    stream_mode: bool
    
    visitor_profile: Dict
    long_term_memory: Optional[str]

    # Reflection state
    detected_language: Literal["vi", "en", "ja", "kr"]
    language_confidence: float
    intent: Literal["chitchat", "question"]
    needs_retrieval: bool
    rewritten_query: str
    followup_action: str
    is_contact: bool

    # === Retrieval ===
    retrieved_chunks: List[Dict]
    retrieval_count: int

    # === Reranking ===
    reranked_chunks: List[Dict]
    rerank_count: int

    # === Generation ===
    response: str
    response_language: str

    # === Sources/Citations ===
    sources: List[Dict]

    # === Metadata ===
    tokens_input: int
    tokens_output: int
    tokens_used: int
    cost_usd: float
    latency_breakdown: Dict[str, float]
    error: Optional[str]

    # === Memory ===
    memory_summary: str
    memory_written: bool

    # === Timestamps ===
    started_at: datetime
    completed_at: Optional[datetime]
