"""Grading schemas."""
from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from app.common.enums import LeadCategory


class GradingTaskPayload(BaseModel):
    """Payload received from backend via RabbitMQ."""
    task_id: str = Field(..., description="Unique task ID")
    task_type: str = Field(default="grading", description="Task type: 'grading' or 'assessment'")
    visitor_id: str = Field(..., description="Visitor ID")
    bot_id: str = Field(..., description="Bot ID")
    session_id: str = Field(..., description="Session ID that triggered grading")
    assessment_questions: Optional[List[str]] = Field(None, description="Assessment questions (only for task_type='assessment')")
    
    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "task_123",
                "task_type": "grading",
                "visitor_id": "visitor_456",
                "bot_id": "bot_789",
                "session_id": "session_abc"
            }
        }


class ScoringResult(BaseModel):
    """Result from LLM scoring."""
    score: int = Field(..., ge=0, le=100, description="Lead score 0-100")
    category: LeadCategory = Field(..., description="Lead quality category")
    intent_signals: List[str] = Field(default_factory=list, description="Detected purchase intent signals")
    engagement_level: str = Field(..., description="high/medium/low")
    key_interests: List[str] = Field(default_factory=list, description="Topics visitor is interested in")
    recommended_actions: List[str] = Field(default_factory=list, description="Next steps for sales team")
    reasoning: str = Field(..., description="Explanation of score")
    
    class Config:
        json_schema_extra = {
            "example": {
                "score": 85,
                "category": "hot",
                "intent_signals": ["asked about pricing", "requested demo", "inquired about enterprise plan"],
                "engagement_level": "high",
                "key_interests": ["enterprise features", "API integration", "custom deployment"],
                "recommended_actions": [
                    "Schedule demo call within 24 hours",
                    "Send case studies",
                    "Assign to senior sales rep"
                ],
                "reasoning": "Strong purchase intent with specific pricing questions and enterprise interest"
            }
        }


class AssessmentQuestionResult(BaseModel):
    """Result for single assessment question."""
    question: str = Field(..., description="Assessment question")
    answer: str = Field(..., description="LLM's answer based on chat history")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    relevant_messages: List[str] = Field(default_factory=list, description="Relevant chat messages")


class AssessmentWebhookPayload(BaseModel):
    """Payload sent to backend webhook for assessment results."""
    task_id: str
    task_type: str = Field(default="assessment", description="Task type")
    visitor_id: str
    bot_id: str
    session_id: str
    
    # Assessment results
    results: List[AssessmentQuestionResult] = Field(..., description="Results per question")
    summary: str = Field(..., description="Overall assessment summary")
    lead_score: int = Field(default=0, ge=0, le=100, description="Lead score 0-100")
    
    # Metadata
    assessed_at: datetime
    model_used: str
    total_messages: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "task_123",
                "visitor_id": "visitor_456",
                "bot_id": "bot_789",
                "session_id": "session_abc",
                "results": [
                    {
                        "question": "Khách hàng có hỏi về giá không?",
                        "answer": "Có, khách hàng đã hỏi về giá gói enterprise",
                        "confidence": 0.95,
                        "relevant_messages": ["Gói enterprise giá bao nhiêu?"]
                    }
                ],
                "summary": "Khách hàng quan tâm đến pricing và features",
                "assessed_at": "2024-01-01T10:00:00Z",
                "model_used": "gpt-4o-mini",
                "total_messages": 15
            }
        }


class GradingWebhookPayload(BaseModel):
    """Payload sent to backend webhook."""
    task_id: str
    task_type: str = Field(default="grading", description="Task type")
    visitor_id: str
    bot_id: str
    session_id: str
    
    # Scoring results
    lead_score: int = Field(..., ge=0, le=100)
    lead_category: LeadCategory
    intent_signals: List[str]
    engagement_level: str
    key_interests: List[str]
    recommended_actions: List[str]
    reasoning: str
    
    # Metadata
    graded_at: datetime
    model_used: str
    conversation_count: int
    
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
                "key_interests": ["enterprise", "API"],
                "recommended_actions": ["Schedule call", "Send case studies"],
                "reasoning": "High purchase intent detected",
                "graded_at": "2024-01-01T10:00:00Z",
                "model_used": "gpt-4o-mini",
                "conversation_count": 15
            }
        }
