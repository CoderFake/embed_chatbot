"""
Webhook schemas for file-server completion notifications
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from app.common.enums import TaskType
from app.schemas.common import BaseRequest, BaseResponse


class FileProcessingResult(BaseModel):
    """Individual file processing result"""
    success: bool
    file_name: str
    document_id: Optional[str] = None
    chunks_count: Optional[int] = None
    inserted_count: Optional[int] = None
    processing_time: Optional[float] = None
    error: Optional[str] = None


class CrawlPageResult(BaseModel):
    """Individual crawled page result"""
    url: str
    title: Optional[str] = None
    chunks_count: int
    success: bool
    error: Optional[str] = None


class WebhookMetadata(BaseModel):
    """Webhook metadata"""
    # File upload metadata
    total_files: Optional[int] = None
    successful_files: Optional[int] = None
    failed_files: Optional[int] = None
    total_chunks: Optional[int] = None
    results: Optional[List[FileProcessingResult]] = None
    
    # Crawl metadata
    origin: Optional[str] = None
    total_pages: Optional[int] = None
    successful_pages: Optional[int] = None
    failed_pages: Optional[int] = None
    crawled_pages: Optional[List[CrawlPageResult]] = None
    duration_seconds: Optional[float] = None


class FileProcessingWebhook(BaseModel):
    """
    File processing completion webhook payload from file-server
    """
    task_id: str = Field(..., description="Unique task identifier")
    bot_id: str = Field(..., description="Bot ID")
    success: bool = Field(..., description="Whether task completed successfully")
    task_type: TaskType = Field(..., description="Type of task: file_upload or crawl")
    timestamp: datetime = Field(..., description="Completion timestamp")
    metadata: Optional[WebhookMetadata] = Field(None, description="Additional metadata")
    error: Optional[str] = Field(None, description="Error message if failed")
    
    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "550e8400-e29b-41d4-a716-446655440000",
                "bot_id": "bot_123",
                "success": True,
                "task_type": "file_upload",
                "timestamp": "2024-01-01T00:00:00Z",
                "metadata": {
                    "total_files": 10,
                    "successful_files": 10,
                    "failed_files": 0,
                    "total_chunks": 523,
                    "results": [
                        {
                            "success": True,
                            "file_name": "document.pdf",
                            "document_id": "doc_123",
                            "chunks_count": 52,
                            "inserted_count": 52,
                            "processing_time": 12.5
                        }
                    ]
                }
            }
        }


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


class WebhookResponse(BaseResponse):
    """
    Standard response for webhook endpoints.
    """
    message: str = "Webhook processed successfully"


class AssessmentQuestionResult(BaseModel):
    """Result for single assessment question."""
    question: str
    answer: str
    confidence: float = Field(ge=0.0, le=1.0)
    relevant_messages: List[str] = Field(default_factory=list)


class VisitorGradingWebhook(BaseModel):
    """
    Visitor grading/assessment webhook payload from visitor-grader service.
    Handles both lead scoring (grading) and custom assessment.
    """
    task_id: str = Field(..., description="Task ID")
    task_type: str = Field(default="grading", description="Task type: grading or assessment")
    visitor_id: str = Field(..., description="Visitor ID")
    bot_id: str = Field(..., description="Bot ID")
    session_id: str = Field(..., description="Session ID")
    
    # Grading results (only for task_type='grading')
    lead_score: Optional[int] = Field(None, ge=0, le=100, description="Lead score 0-100")
    lead_category: Optional[str] = Field(None, description="hot/warm/cold")
    intent_signals: List[str] = Field(default_factory=list, description="Purchase intent signals")
    engagement_level: Optional[str] = Field(None, description="high/medium/low")
    key_interests: List[str] = Field(default_factory=list, description="Topics of interest")
    recommended_actions: List[str] = Field(default_factory=list, description="Next steps")
    reasoning: Optional[str] = Field(None, description="Scoring explanation")
    
    # Assessment results (only for task_type='assessment')
    results: Optional[List[AssessmentQuestionResult]] = Field(None, description="Assessment results per question")
    summary: Optional[str] = Field(None, description="Overall assessment summary")
    
    # Metadata
    graded_at: Optional[datetime] = Field(None, description="Grading timestamp")
    assessed_at: Optional[datetime] = Field(None, description="Assessment timestamp")
    model_used: str = Field(..., description="LLM model used")
    conversation_count: Optional[int] = Field(None, description="Number of messages")
    total_messages: Optional[int] = Field(None, description="Total messages analyzed")
    
    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "task_123",
                "visitor_id": "visitor_456",
                "bot_id": "bot_789",
                "session_id": "session_abc",
                "lead_score": 85,
                "lead_category": "hot",
                "intent_signals": ["pricing inquiry", "demo request"],
                "engagement_level": "high",
                "key_interests": ["enterprise features", "API integration"],
                "recommended_actions": ["Schedule demo call", "Send case studies"],
                "reasoning": "High purchase intent with specific pricing questions",
                "graded_at": "2024-01-01T10:00:00Z",
                "model_used": "gpt-4o-mini",
                "conversation_count": 15
            }
        }

FileProcessingUpdatePayload = FileProcessingWebhook
SitemapCrawlUpdatePayload = FileProcessingWebhook
