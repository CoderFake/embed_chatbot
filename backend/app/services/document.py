"""
Document service for managing knowledge base documents.
"""
import hashlib
import uuid
import os
import asyncio
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from redis.asyncio import Redis
from fastapi import HTTPException, status, UploadFile

from app.models.document import Document
from app.common.enums import DocumentStatus, DocumentSource
from app.cache.service import CacheService
from app.cache.keys import CacheKeys
from app.cache.invalidation import CacheInvalidation
from app.services.storage import minio_service
from app.services.rabbitmq import rabbitmq_publisher
from app.config.settings import settings
from app.common.constants import SUPPORTED_FILE_EXTENSIONS, MAX_FILE_SIZE_BYTES
from app.utils.logging import get_logger
from app.utils.datetime_utils import now
from app.utils.file_path import (
    build_document_file_path, 
    extract_object_name, 
    build_local_filename
)

logger = get_logger(__name__)


class DocumentService:
    """
    Document service with cache integration.
    """
    
    def __init__(self, db: AsyncSession, redis: Redis):
        self.db = db
        self.redis = redis
        self.cache = CacheService(redis)
        self.cache_invalidation = CacheInvalidation(redis)
    
    @staticmethod
    def _save_file_sync(file_path: str, content: bytes) -> None:
        """
        Save file to disk (blocking I/O - called via to_thread)
        
        Args:
            file_path: Full path to save file
            content: File content bytes
        """
        with open(file_path, "wb") as f:
            f.write(content)
    
    async def get_by_id(self, document_id: str) -> Optional[Document]:
        """
        Get document by ID with cache-aside pattern.
        
        Args:
            document_id: Document UUID
            
        Returns:
            Document instance or None
        """
        cache_key = CacheKeys.document(document_id)
        cached_data = await self.cache.get(cache_key)
        
        if cached_data:
            logger.debug(f"Cache hit for document: {document_id}")
            doc_data = cached_data.copy()
            if 'status' in doc_data and isinstance(doc_data['status'], str):
                doc_data['status'] = DocumentStatus(doc_data['status'])
            return Document(**doc_data)
        
        logger.debug(f"Cache miss for document: {document_id}")
        result = await self.db.execute(
            select(Document).where(Document.id == document_id)
        )
        doc = result.scalar_one_or_none()
        
        if doc:
            doc_dict = {
                "id": str(doc.id),
                "bot_id": str(doc.bot_id),
                "user_id": str(doc.user_id),
                "url": doc.url,
                "title": doc.title,
                "content_hash": doc.content_hash,
                "status": doc.status.value,
                "file_path": doc.file_path,
                "extra_data": doc.extra_data,
                "error_message": doc.error_message,
                "processed_at": doc.processed_at.isoformat() if doc.processed_at else None,
                "created_at": doc.created_at.isoformat(),
                "updated_at": doc.updated_at.isoformat(),
            }
            await self.cache.set(cache_key, doc_dict, ttl=settings.CACHE_DOCUMENT_TTL)
        
        return doc
    
    async def create_from_url(
        self,
        bot_id: str,
        user_id: str,
        url: str,
        title: str,
        raw_content: str,
        status: DocumentStatus = DocumentStatus.PENDING
    ) -> Document:
        """
        Create document from crawled URL.
        
        Args:
            bot_id: Bot UUID
            user_id: User UUID
            url: Source URL
            title: Document title
            raw_content: Extracted markdown content
            status: Initial status
            
        Returns:
            Created document instance
        """
        content_hash = hashlib.sha256(raw_content.encode('utf-8')).hexdigest()
        
        result = await self.db.execute(
            select(Document).where(
                Document.bot_id == bot_id,
                Document.content_hash == content_hash
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            logger.warning(f"Duplicate document for bot {bot_id}, hash: {content_hash[:8]}...")
            return existing
        
        doc = Document(
            bot_id=bot_id,
            user_id=user_id,
            url=url,
            title=title,
            content_hash=content_hash,
            status=status,
            raw_content=raw_content,
            extra_data={}
        )
        
        self.db.add(doc)
        await self.db.flush()
        await self.db.refresh(doc)
        
        logger.info(f"Created document from URL: {url} for bot {bot_id}")
        
        return doc
    
    async def create_from_file(
        self,
        bot_id: str,
        user_id: str,
        file: UploadFile,
        title: Optional[str] = None
    ) -> tuple[Document, str, str]:
        """
        Create document from uploaded file and save to shared volume.
        
        Args:
            bot_id: Bot UUID
            user_id: User UUID
            file: Uploaded file
            title: Optional custom title (defaults to filename)
            
        Returns:
            Tuple of (Document instance, task_id, local_file_path)
        """
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Filename is required"
            )

        file_extension = '.' + file.filename.split('.')[-1].lower()
        if file_extension not in SUPPORTED_FILE_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type: {file_extension}. Supported: {', '.join(sorted(SUPPORTED_FILE_EXTENSIONS))}"
            )
        
        file_content = await file.read()
        await file.seek(0)
        
        if len(file_content) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Maximum size: {MAX_FILE_SIZE_BYTES // (1024*1024)}MB"
            )
        
        content_hash = hashlib.sha256(file_content).hexdigest()
        
        result = await self.db.execute(
            select(Document).where(
                Document.bot_id == bot_id,
                Document.content_hash == content_hash
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This file has already been uploaded for this bot"
            )
        
        from app.models.bot import Bot
        result = await self.db.execute(
            select(Bot).where(Bot.id == bot_id).where(Bot.is_deleted.is_(False))
        )
        bot = result.scalar_one_or_none()
        
        if not bot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bot not found"
            )
        
        doc_id = str(uuid.uuid4())
        task_id = str(uuid.uuid4())
        
        await asyncio.to_thread(os.makedirs, settings.UPLOAD_DIR, exist_ok=True)
        
        local_filename = build_local_filename(doc_id, file.filename)
        local_file_path = os.path.join(settings.UPLOAD_DIR, local_filename)
        
        try:
            await asyncio.to_thread(self._save_file_sync, local_file_path, file_content)
            logger.info(f"Saved file to shared volume: {local_file_path}")
        except Exception as e:
            logger.error(f"Failed to save file to shared volume: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save file: {str(e)}"
            )
        
        file_path = build_document_file_path(bot.bot_key, doc_id, file.filename)
        
        doc = Document(
            id=doc_id,
            bot_id=bot_id,
            user_id=user_id,
            file_path=file_path,
            title=title or file.filename,
            content_hash=content_hash,
            status=DocumentStatus.PROCESSING,
            extra_data={
                "filename": file.filename,
                "file_size": len(file_content),
                "content_type": file.content_type,
                "task_id": task_id
            }
        )
        
        doc.bot = bot
        
        self.db.add(doc)
        await self.db.flush()
        await self.db.refresh(doc)
        
        logger.info(f"Created document from file: {file.filename} for bot {bot_id}, task: {task_id}")
        
        return doc, task_id, local_file_path
    
    async def update_status(
        self,
        document: Document,
        status: DocumentStatus,
        error_message: Optional[str] = None,
        extra_data: Optional[dict] = None
    ) -> Document:
        """
        Update document status and invalidate cache.
        
        Args:
            document: Document instance
            status: New status
            error_message: Optional error message
            extra_data: Optional additional data
            
        Returns:
            Updated document
        """
        document.status = status
        
        if error_message:
            document.error_message = error_message
        
        if extra_data:
            document.extra_data.update(extra_data)
        
        if status == DocumentStatus.COMPLETED:
            from app.utils.datetime_utils import now
            document.processed_at = now()
        
        await self.db.flush()
        await self.db.refresh(document)
        
        await self.cache_invalidation.invalidate_document(str(document.id), str(document.bot_id))
        
        logger.info(f"Updated document {document.id} status to {status}")
        
        return document
    
    async def update_processing_result(
        self,
        document_id: str,
        success: bool,
        chunks_count: Optional[int] = None,
        error_message: Optional[str] = None
    ) -> Document:
        """
        Update document with processing results from file-server.
        
        Called by webhook handler when file-server completes processing.
        
        Args:
            document_id: Document UUID
            success: Whether processing succeeded
            chunks_count: Number of chunks created
            error_message: Error message if failed
            
        Returns:
            Updated document
        """
        document = await self.get_by_id(document_id)
        if not document:
            logger.error(f"Document not found: {document_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document {document_id} not found"
            )
        
        new_status = DocumentStatus.COMPLETED if success else DocumentStatus.FAILED
        
        extra_data = document.extra_data or {}
        if chunks_count is not None:
            extra_data["chunks_count"] = chunks_count
        
        await self.update_status(
            document=document,
            status=new_status,
            error_message=error_message,
            extra_data=extra_data
        )
        
        logger.info(
            f"Updated document {document_id} processing result: "
            f"success={success}, chunks={chunks_count}",
            extra={
                "document_id": document_id,
                "success": success,
                "chunks_count": chunks_count
            }
        )
        
        return document
    
    async def create_crawled_document(
        self,
        bot_id: str,
        url: str,
        title: Optional[str] = None,
        chunks_count: int = 0,
        task_id: Optional[str] = None
    ) -> Document:
        """
        Create document record for crawled web page.
        
        Called by webhook handler when file-server completes crawling.
        
        Args:
            bot_id: Bot UUID
            url: Crawled URL
            title: Page title
            chunks_count: Number of chunks created
            task_id: Crawl task ID
            
        Returns:
            Created document
        """

        file_name = url
        display_name = title if title else url
        
        document = Document(
            bot_id=bot_id,
            file_name=file_name,
            original_name=display_name,
            source=DocumentSource.WEB,
            status=DocumentStatus.COMPLETED,
            extra_data={
                "url": url,
                "title": title,
                "chunks_count": chunks_count,
                "task_id": task_id,
                "crawled_at": now().isoformat()
            }
        )
        
        self.db.add(document)
        await self.db.flush()
        await self.db.refresh(document)
        
        logger.info(
            f"Created crawled document: {document.id} for URL: {url}",
            extra={
                "document_id": str(document.id),
                "bot_id": bot_id,
                "url": url,
                "chunks_count": chunks_count
            }
        )
        
        return document
    
    async def validate_batch_import(
        self,
        task_id: str,
        bot_id: str,
        document_id: str,
        batch_index: int,
        total_batches: int,
        chunks_in_batch: int,
        batch_data: List[dict],
        source_type: str = "file"
    ) -> dict:
        """
        Validate batch import data consistency.
        
        Backend only validates and tracks progress for SSE.
        Does NOT process documents - that's handled by file-server and webhook.
        
        Args:
            task_id: Task ID for tracking
            bot_id: Bot ID
            document_id: Document ID (for files) or crawl_{task_id} (for crawl)
            batch_index: Current batch index (0-based)
            total_batches: Total number of batches
            chunks_in_batch: Number of chunks in this batch
            batch_data: List of chunk data for validation
            source_type: 'file' or 'crawl'
            
        Returns:
            Validation result dictionary
        """
        if len(batch_data) != chunks_in_batch:
            logger.warning(
                f"Batch chunk count mismatch: expected {chunks_in_batch}, got {len(batch_data)}",
                extra={
                    "task_id": task_id,
                    "document_id": document_id,
                    "batch_index": batch_index,
                    "expected": chunks_in_batch,
                    "actual": len(batch_data)
                }
            )
        
        progress_percentage = ((batch_index + 1) / total_batches) * 100
        completed = (batch_index + 1) >= total_batches
        
        logger.info(
            f"Batch validated: batch {batch_index + 1}/{total_batches} for task {task_id} ({source_type})",
            extra={
                "task_id": task_id,
                "document_id": document_id,
                "bot_id": bot_id,
                "batch_index": batch_index,
                "chunks_in_batch": chunks_in_batch,
                "progress": progress_percentage,
                "source_type": source_type
            }
        )
        
        return {
            "success": True,
            "document_id": document_id,
            "batch_index": batch_index,
            "validated_chunks": len(batch_data),
            "progress": progress_percentage,
            "completed": completed
        }
    
    async def list_by_bot(
        self,
        bot_id: str,
        page: int = 1,
        size: int = 20,
        status_filter: Optional[DocumentStatus] = None,
        sort_by: str = "created_at"
    ) -> tuple[List[Document], int]:
        """
        List documents for bot with pagination and sorting.
        
        Args:
            bot_id: Bot UUID
            page: Page number (1-indexed)
            size: Page size
            status_filter: Optional status filter
            sort_by: Sort column (created_at, title)
            
        Returns:
            Tuple of (documents list, total count)
        """
        query = select(Document).where(Document.bot_id == bot_id)
        
        if status_filter:
            query = query.where(Document.status == status_filter)
        
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()
        
        # Dynamic sorting
        if sort_by == "title":
            query = query.order_by(Document.title.asc())
        else:  # created_at (default)
            query = query.order_by(Document.created_at.desc())
            
        query = query.offset((page - 1) * size).limit(size)
        
        result = await self.db.execute(query)
        documents = result.scalars().all()
        
        return list(documents), total
    
    async def delete(self, document: Document) -> None:
        """
        Delete document and invalidate cache.
        Also deletes file from MinIO and vectors from Milvus.
        
        Args:
            document: Document instance to delete
        """
        doc_id = str(document.id)
        bot_id = str(document.bot_id)
        file_path = document.file_path

        from app.models.bot import Bot
        if document.status == DocumentStatus.COMPLETED:
            try:
                result = await self.db.execute(
                    select(Bot).where(Bot.id == bot_id).where(Bot.is_deleted.is_(False))
                )
                bot = result.scalar_one_or_none()

                if bot:
                    delete_task_id = str(uuid.uuid4())
                    await rabbitmq_publisher.publish_delete_document_task(
                        task_id=delete_task_id,
                        bot_id=bot_id,
                        document_id=doc_id,
                        collection_name=bot.collection_name
                    )
                    logger.info(f"Published delete document task {delete_task_id} to file-server for document {doc_id}")
            except Exception as e:
                logger.error(f"Failed to publish delete document task: {e}")

        if file_path:
            try:
                
                result = await self.db.execute(
                    select(Bot).where(Bot.id == bot_id).where(Bot.is_deleted.is_(False))
                )
                bot = result.scalar_one_or_none()
                
                if bot:
                    await asyncio.to_thread(
                        minio_service.delete_file,
                        bot.bucket_name,
                        extract_object_name(file_path)
                    )
                    logger.info(f"Deleted file from MinIO: {file_path}")
            except Exception as e:
                logger.error(f"Failed to delete file from MinIO: {e}")
        
        await self.db.delete(document)
        await self.db.flush()
        
        await self.cache_invalidation.invalidate_document(doc_id, bot_id)
        
        logger.info(f"Deleted document: {doc_id}")

