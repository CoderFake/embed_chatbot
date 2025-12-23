"""
Task processor - routes and processes tasks from RabbitMQ queue
"""
from typing import Dict, Any
from app.processors.file_processor import FileProcessor
from app.processors.crawl_processor import CrawlProcessor
from app.storage.milvus_service import MilvusService
from app.storage.minio_service import MinIOService
from app.progress.publisher import ProgressPublisher
from app.webhooks.notifier import WebhookNotifier
from app.core.redis_client import RedisClient
from app.common.enums import TaskType
from app.utils.logging import get_logger

logger = get_logger(__name__)


class TaskProcessor:
    """
    Routes and processes tasks from RabbitMQ.
    
    Supported task types:
    - FILE_UPLOAD: Process files from /tmp/uploads
    - CRAWL: Process crawl data from /tmp/crawl
    - DELETE_DOCUMENT: Delete single document vectors from Milvus
    - RECRAWL: Delete multiple document vectors from Milvus (for recrawl)
    
    Features:
    - Task routing by type
    - Progress tracking
    - Webhook notifications
    - Error handling
    """
    
    def __init__(self):
        """Initialize task processor with all dependencies"""
        # Initialize services
        self.milvus_service = MilvusService()
        self.minio_service = MinIOService()
        self.redis_client = RedisClient()
        
        try:
            self.redis_client.connect()
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}", exc_info=True)
            raise
        
        self.progress_publisher = ProgressPublisher(self.redis_client)
        self.webhook_notifier = WebhookNotifier()
        
        self.file_processor = FileProcessor(
            milvus_service=self.milvus_service,
            minio_service=self.minio_service,
            progress_publisher=self.progress_publisher
        )
        
        self.crawl_processor = CrawlProcessor(
            milvus_service=self.milvus_service,
            progress_publisher=self.progress_publisher,
            redis_client=self.redis_client
        )
    
    async def process_task(self, task_data: Dict[str, Any]) -> bool:
        """
        Process a task from RabbitMQ
        
        Args:
            task_data: Task data from RabbitMQ message
            
        Expected task_data format:
        {
            "task_id": "uuid",
            "task_type": TaskType.FILE_UPLOAD | TaskType.CRAWL | TaskType.DELETE_DOCUMENT | TaskType.RECRAWL,
            "bot_id": "bot_123",
            "data": {
                # For file_upload:
                "files": [
                    {
                        "path": "/tmp/uploads/file1.pdf",
                        "document_id": "doc_123",
                        "metadata": {...}
                    }
                ]

                # For crawl:
                "crawl_files": [
                    {
                        "path": "/tmp/crawl/crawl_123.json",
                        "crawl_id": "crawl_123"
                    }
                ]

                # For delete_document:
                "document_id": "doc_123",
                "collection_name": "bot_123"

                # For recrawl:
                "document_ids": ["doc_123", "doc_456"],
                "collection_name": "bot_123"
            }
        }
        
        Returns:
            True if task processed successfully, False otherwise
        """
        task_id = task_data.get("task_id")
        task_type = task_data.get("task_type")
        bot_id = task_data.get("bot_id")
        data = task_data.get("data", {})
        
        if not all([task_id, task_type, bot_id]):
            logger.error(f"Invalid task data: missing required fields: {task_data}")
            return False
        
        logger.info(
            f"Processing task: task_id={task_id}, type={task_type}, bot_id={bot_id}",
            extra={
                "task_id": task_id,
                "task_type": task_type,
                "bot_id": bot_id
            }
        )
        
        try:
            result = None
            
            if task_type == TaskType.FILE_UPLOAD.value:
                files = data.get("files", [])
                if not files:
                    raise ValueError("No files provided for file_upload task")
                
                result = await self.file_processor.process_files_batch(
                    files=files,
                    bot_id=bot_id,
                    task_id=task_id
                )
            
            elif task_type == TaskType.CRAWL.value:
                if "origin" in data:
                    origin = data.get("origin")
                    sitemap_urls = data.get("sitemap_urls", [])
                    collection_name = data.get("collection_name")
                    
                    if not origin or not collection_name:
                        raise ValueError("origin and collection_name required for crawl task")
                    
                    result = await self.crawl_processor.process_crawl_direct(
                        origin=origin,
                        sitemap_urls=sitemap_urls,
                        collection_name=collection_name,
                        bot_id=bot_id,
                        task_id=task_id
                    )
                    
                elif "crawl_files" in data:
                    crawl_files = data.get("crawl_files", [])
                    if not crawl_files:
                        raise ValueError("No crawl files provided for crawl task")
                    
                    result = await self.crawl_processor.process_crawl_batch(
                        crawl_files=crawl_files,
                        bot_id=bot_id,
                        task_id=task_id
                    )
                else:
                    raise ValueError("Crawl task must contain either 'origin' or 'crawl_files'")

            elif task_type == TaskType.DELETE_DOCUMENT.value:
                document_id = data.get("document_id")
                collection_name = data.get("collection_name")

                if not document_id or not collection_name:
                    raise ValueError("document_id and collection_name required for delete_document task")

                try:
                    deleted = self.milvus_service.delete_by_document_id(
                        collection_name=collection_name,
                        document_id=document_id
                    )

                    if deleted:
                        logger.info(f"Deleted document {document_id} from Milvus collection {collection_name}")
                        result = {"deleted": True, "document_id": document_id}
                    else:
                        logger.warning(f"Document {document_id} not found in collection {collection_name}")
                        result = {"deleted": False, "document_id": document_id}

                except Exception as e:
                    logger.error(f"Failed to delete document {document_id}: {e}")
                    result = {"deleted": False, "document_id": document_id, "error": str(e)}

            elif task_type == TaskType.RECRAWL.value:
                document_ids = data.get("document_ids", [])
                collection_name = data.get("collection_name")

                if not document_ids or not collection_name:
                    raise ValueError("document_ids and collection_name required for recrawl task")

                deleted_count = 0
                failed_deletions = []

                for document_id in document_ids:
                    try:
                        deleted = self.milvus_service.delete_by_document_id(
                            collection_name=collection_name,
                            document_id=document_id
                        )
                        if deleted:
                            deleted_count += 1
                            logger.info(f"Deleted document {document_id} from Milvus collection {collection_name} (recrawl)")
                        else:
                            logger.warning(f"Document {document_id} not found in collection {collection_name} (recrawl)")
                            failed_deletions.append(document_id)
                    except Exception as e:
                        logger.error(f"Failed to delete document {document_id} during recrawl: {e}")
                        failed_deletions.append(document_id)

                result = {
                    "deleted_count": deleted_count,
                    "total_requested": len(document_ids),
                    "failed_deletions": failed_deletions
                }

                logger.info(f"Recrawl completed: deleted {deleted_count}/{len(document_ids)} documents from {collection_name}")

            else:
                raise ValueError(f"Unknown task type: {task_type}")
            
            if task_type == TaskType.DELETE_DOCUMENT.value:
                success = result and result.get("deleted", False)
            elif task_type == TaskType.RECRAWL.value:
                success = result and result.get("deleted_count", 0) > 0
            else:
                success = result and result.get("failed_files", 0) == 0
            await self.webhook_notifier.notify_completion(
                task_id=task_id,
                bot_id=bot_id,
                success=success,
                task_type=task_type,
                metadata=result
            )
            
            logger.info(
                f"Task completed: task_id={task_id}, success={success}",
                extra={
                    "task_id": task_id,
                    "task_type": task_type,
                    "bot_id": bot_id,
                    "success": success
                }
            )
            
            return success
        
        except Exception as e:
            logger.error(
                f"Task processing failed: task_id={task_id}, error={e}",
                extra={
                    "task_id": task_id,
                    "task_type": task_type,
                    "bot_id": bot_id,
                    "error": str(e)
                },
                exc_info=True
            )
            
            await self.progress_publisher.publish_completion(
                task_id=task_id,
                bot_id=bot_id,
                success=False,
                message=f"Processing failed: {str(e)}"
            )
            
            await self.webhook_notifier.notify_completion(
                task_id=task_id,
                bot_id=bot_id,
                success=False,
                task_type=task_type,
                error=str(e)
            )
            
            return False
    
    async def cleanup(self):
        """Cleanup resources"""
        try:
            await self.redis_client.close()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
