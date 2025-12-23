"""
Pydantic schemas for Document.
"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID

from app.common.enums import DocumentStatus, JobStatus
from app.utils.datetime_utils import now


class DocumentBase(BaseModel):
    """Base document schema"""
    title: str = Field(..., min_length=1, max_length=500)
    url: Optional[str] = Field(None, max_length=1000)
    file_path: Optional[str] = Field(None, max_length=500)


class DocumentCreate(DocumentBase):
    """
    Schema for creating document.
    Either url or file_path must be provided.
    """
    pass


class DocumentUpdate(BaseModel):
    """Schema for updating document"""
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    status: Optional[DocumentStatus] = None
    raw_content: Optional[str] = None
    error_message: Optional[str] = None


class DocumentResponse(DocumentBase):
    """Schema for document response"""
    id: UUID
    bot_id: UUID
    user_id: Optional[UUID] = None
    uploaded_by: Optional[str] = None 
    content_hash: str
    status: DocumentStatus
    raw_content: Optional[str] = None
    extra_data: dict = Field(default_factory=dict)
    error_message: Optional[str] = None
    processed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    task_id: Optional[str] = None
    source_type: str = "file"
    chunk_count: int = 0
    file_size: Optional[int] = None
    web_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @classmethod
    def from_orm_with_computed(cls, document):
        """Create response with computed fields from extra_data"""
        uploaded_by = None
        if document.user:
            uploaded_by = document.user.full_name or document.user.email
        
        data = {
            "id": document.id,
            "bot_id": document.bot_id,
            "user_id": document.user_id,
            "uploaded_by": uploaded_by,
            "title": document.title,
            "url": document.url,
            "file_path": document.file_path,
            "content_hash": document.content_hash,
            "status": document.status,
            "raw_content": document.raw_content,
            "extra_data": document.extra_data or {},
            "error_message": document.error_message,
            "processed_at": document.processed_at,
            "created_at": document.created_at,
            "updated_at": document.updated_at,
            "task_id": (document.extra_data or {}).get("task_id"),
            "source_type": "crawl" if document.url else "file",
            "chunk_count": (document.extra_data or {}).get("chunks_count", 0),
            "file_size": (document.extra_data or {}).get("file_size"),
            "web_url": document.url,
        }
        return cls(**data)


class DocumentListResponse(BaseModel):
    """Schema for paginated document list"""
    items: list[DocumentResponse]
    total: int
    page: int
    size: int
    pages: int


class JobResponse(BaseModel):
    """Schema for background job response"""
    job_id: str
    job_type: str
    status: str
    message: str
    sse_endpoint: Optional[str] = None


class CrawlJobResponse(JobResponse):
    """Schema for crawl job response"""
    bot_id: UUID
    domain: str


class DocumentJobResponse(JobResponse):
    """Schema for document processing job response"""
    document_id: UUID
    bot_id: UUID


# Progress update schemas (for SSE)
class ProgressUpdate(BaseModel):
    """Schema for SSE progress updates"""
    status: str
    progress: int = Field(..., ge=0, le=100)
    message: str
    current_url: Optional[str] = None
    total_pages: Optional[int] = None
    processed_pages: Optional[int] = None
    successful_pages: Optional[int] = None
    failed_pages: Optional[int] = None
    timestamp: datetime = Field(default_factory=now)


# Batch import schemas
class BatchChunkData(BaseModel):
    """Schema for a single chunk in batch import"""
    text: str
    chunk_index: int
    metadata: dict = Field(default_factory=dict)


class BatchImportRequest(BaseModel):
    """Schema for batch import request from file-server"""
    task_id: str = Field(..., description="Task ID for tracking")
    bot_id: str = Field(..., description="Bot ID")
    document_id: str = Field(..., description="Document ID")
    batch_index: int = Field(..., description="Current batch index (0-based)")
    total_batches: int = Field(..., description="Total number of batches")
    chunks_in_batch: int = Field(..., description="Number of chunks in this batch")
    batch_data: list[BatchChunkData] = Field(..., description="Chunk data for validation")
    
    # Source type indicators
    source_type: str = Field(..., description="Source type: 'file' or 'crawl'")
    file_path: Optional[str] = Field(None, description="File path (for file uploads)")
    web_url: Optional[str] = Field(None, description="Web URL (for crawled pages)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "550e8400-e29b-41d4-a716-446655440000",
                "bot_id": "bot_123",
                "document_id": "doc_456",
                "batch_index": 0,
                "total_batches": 5,
                "chunks_in_batch": 100,
                "source_type": "file",
                "file_path": "uploads/doc_456_document.pdf",
                "web_url": None,
                "batch_data": [
                    {
                        "text": "Sample chunk text...",
                        "chunk_index": 0,
                        "metadata": {"file_name": "document.pdf"}
                    }
                ]
            }
        }


class BatchImportResponse(BaseModel):
    """Schema for batch import response"""
    success: bool
    task_id: str
    document_id: str
    batch_index: int
    message: str
    validated_chunks: int = Field(..., description="Number of chunks validated")
    timestamp: datetime = Field(default_factory=now)


class ActiveTaskResponse(BaseModel):
    """Schema for active task response"""
    task_id: str
    task_type: str
    bot_id: Optional[str] = None
    status: str
    progress: int = Field(0, ge=0, le=100)
    message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ActiveTasksListResponse(BaseModel):
    """Schema for active tasks list response"""
    tasks: list[ActiveTaskResponse]
    total: int
