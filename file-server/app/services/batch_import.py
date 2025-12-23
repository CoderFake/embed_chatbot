"""
Batch Import Service - sends batch completion to backend immediately after Milvus insertion
"""
from typing import List, Dict, Any, Optional
import httpx

from app.config.settings import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class BatchImportService:
    """
    Service to notify backend immediately after each batch is inserted into Milvus.
    
    Features:
    - Immediate batch notification (no waiting for all batches)
    - Data validation payload
    - Retry logic for failed requests
    - Progress tracking integration
    """
    
    def __init__(self):
        """Initialize batch import service"""
        self.backend_url = settings.BACKEND_API_URL
        self.batch_import_endpoint = f"{self.backend_url}/api/v1/documents/batch-import"
        self.timeout = 30.0
        self.max_retries = 3
    
    async def notify_batch_completion(
        self,
        task_id: str,
        bot_id: str,
        document_id: str,
        batch_index: int,
        total_batches: int,
        chunks_in_batch: int,
        batch_data: List[Dict[str, Any]],
        source_type: str,
        file_path: Optional[str] = None,
        web_url: Optional[str] = None
    ) -> bool:
        """
        Notify backend immediately after batch insertion to Milvus.
        
        Args:
            task_id: Task ID for tracking
            bot_id: Bot ID
            document_id: Document ID
            batch_index: Current batch index (0-based)
            total_batches: Total number of batches
            chunks_in_batch: Number of chunks in this batch
            batch_data: List of chunk data for validation
            source_type: 'file' or 'crawl'
            file_path: File path (for file uploads)
            web_url: Web URL (for crawled pages)
            
        Returns:
            True if notification sent successfully, False otherwise
        """
        # Build payload
        payload = {
            "task_id": task_id,
            "bot_id": bot_id,
            "document_id": document_id,
            "batch_index": batch_index,
            "total_batches": total_batches,
            "chunks_in_batch": chunks_in_batch,
            "source_type": source_type,
            "file_path": file_path,
            "web_url": web_url,
            "batch_data": [
                {
                    "text": chunk.get("text", ""),
                    "chunk_index": chunk.get("chunk_index", idx),
                    "metadata": chunk.get("metadata", {})
                }
                for idx, chunk in enumerate(batch_data)
            ]
        }
        
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        self.batch_import_endpoint,
                        json=payload
                    )
                    
                    if response.status_code == 200:
                        response_data = response.json()
                        logger.info(
                            f"Batch import notification sent successfully: "
                            f"batch {batch_index + 1}/{total_batches} for task {task_id}",
                            extra={
                                "task_id": task_id,
                                "document_id": document_id,
                                "bot_id": bot_id,
                                "batch_index": batch_index,
                                "chunks": chunks_in_batch,
                                "attempt": attempt + 1
                            }
                        )
                        return True
                    else:
                        logger.warning(
                            f"Batch import notification failed: status={response.status_code}, "
                            f"batch {batch_index + 1}/{total_batches}",
                            extra={
                                "task_id": task_id,
                                "document_id": document_id,
                                "status_code": response.status_code,
                                "response": response.text,
                                "attempt": attempt + 1
                            }
                        )
                        
                        if 400 <= response.status_code < 500:
                            logger.error(
                                f"Client error in batch import, not retrying: {response.status_code}",
                                extra={
                                    "task_id": task_id,
                                    "response": response.text
                                }
                            )
                            return False
            
            except httpx.TimeoutException:
                logger.warning(
                    f"Batch import notification timeout (attempt {attempt + 1}/{self.max_retries})",
                    extra={
                        "task_id": task_id,
                        "document_id": document_id,
                        "batch_index": batch_index,
                        "timeout": self.timeout
                    }
                )
            
            except Exception as e:
                logger.error(
                    f"Error sending batch import notification (attempt {attempt + 1}/{self.max_retries}): {e}",
                    extra={
                        "task_id": task_id,
                        "document_id": document_id,
                        "batch_index": batch_index,
                        "error": str(e)
                    },
                    exc_info=True
                )
            
            if attempt < self.max_retries - 1:
                import asyncio
                wait_time = (attempt + 1) * 2
                await asyncio.sleep(wait_time)
        
        logger.error(
            f"Failed to send batch import notification after {self.max_retries} attempts",
            extra={
                "task_id": task_id,
                "document_id": document_id,
                "batch_index": batch_index
            }
        )
        return False


# Singleton instance
batch_import_service = BatchImportService()

