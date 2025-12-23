"""
RabbitMQ service for pushing tasks to file-server
"""
import json
import uuid
import asyncio
import time
from typing import Dict, Any, Optional
import pika
from pika.exceptions import AMQPConnectionError, StreamLostError, ChannelWrongStateError

from app.config.settings import settings
from app.common.enums import TaskType
from app.utils.logging import get_logger

logger = get_logger(__name__)


class RabbitMQPublisher:
    """
    RabbitMQ publisher for sending tasks to file-server queue.
    
    This service pushes file processing tasks to the file-server's internal queue.
    The file-server will consume these tasks asynchronously.
    """
    
    def __init__(self):
        """Initialize RabbitMQ publisher"""
        self.rabbitmq_url = settings.RABBITMQ_URL
        self.queue_name = settings.RABBITMQ_QUEUE_NAME
        self.connection = None
        self.channel = None
        self.max_retries = 3
        self.retry_delay = 1
    
    def connect(self):
        """Connect to RabbitMQ with retry logic"""
        for attempt in range(self.max_retries):
            try:
                parameters = pika.URLParameters(self.rabbitmq_url)
                parameters.socket_timeout = 5
                parameters.connection_attempts = 3
                parameters.retry_delay = 2
                
                self.connection = pika.BlockingConnection(parameters)
                self.channel = self.connection.channel()
                
                dlq_name = f"{self.queue_name}_dlq"
                self.channel.queue_declare(
                    queue=dlq_name,
                    durable=True
                )

                self.channel.queue_declare(
                    queue=self.queue_name,
                    durable=True,
                    arguments={
                        'x-dead-letter-exchange': '',
                        'x-dead-letter-routing-key': dlq_name,
                        'x-max-priority': 10
                    }
                )
                
                logger.info(
                    f"Connected to RabbitMQ: {self.rabbitmq_url}",
                    extra={"queue": self.queue_name}
                )
                return  
                
            except AMQPConnectionError as e:
                logger.warning(f"Failed to connect to RabbitMQ (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f"Failed to connect to RabbitMQ after {self.max_retries} attempts: {e}", exc_info=True)
                    raise
            except Exception as e:
                logger.error(f"Unexpected error connecting to RabbitMQ: {e}", exc_info=True)
                raise
    
    def disconnect(self):
        """Disconnect from RabbitMQ"""
        try:
            if self.connection and not self.connection.is_closed:
                self.connection.close()
                logger.info("Disconnected from RabbitMQ")
        except Exception as e:
            logger.error(f"Error disconnecting from RabbitMQ: {e}")
    
    def _ensure_connection(self):
        """Ensure we have a valid connection to RabbitMQ"""
        try:
            if not self.connection or self.connection.is_closed:
                logger.info("RabbitMQ connection is closed, reconnecting...")
                self.connect()
            elif not self.channel or self.channel.is_closed:
                logger.info("RabbitMQ channel is closed, recreating...")
                self.channel = self.connection.channel()
        except Exception as e:
            logger.error(f"Error ensuring RabbitMQ connection: {e}", exc_info=True)
            self.disconnect()
            self.connect()
    
    def publish_task(
        self,
        task_type: TaskType,
        bot_id: str,
        data: Dict[str, Any],
        task_id: Optional[str] = None,
        priority: int = 5
    ) -> str:
        """
        Publish a task to file-server queue (BLOCKING - must be wrapped in to_thread)
        
        Args:
            task_type: Type of task (TaskType.FILE_UPLOAD or TaskType.CRAWL)
            bot_id: Bot ID
            data: Task data
            task_id: Optional task ID (will generate if not provided)
            priority: Task priority (0-10, higher = more priority)
            
        Returns:
            task_id: Generated or provided task ID
            
        Note:
            This method uses blocking I/O (pika.BlockingConnection).
            Always call via asyncio.to_thread() from async context.
            
        Example task data for file_upload:
            {
                "files": [
                    {
                        "path": "/tmp/uploads/doc_123.pdf",
                        "document_id": "doc_123",
                        "metadata": {"source": "upload", "filename": "doc.pdf"}
                    }
                ]
            }
        
        Example task data for crawl:
            {
                "crawl_files": [
                    {
                        "path": "/tmp/crawl/crawl_123.json",
                        "crawl_id": "crawl_123"
                    }
                ]
            }
        """
        if not task_id:
            task_id = str(uuid.uuid4())
        
        task_payload = {
            "task_id": task_id,
            "task_type": task_type,
            "bot_id": bot_id,
            "data": data
        }
        
        for attempt in range(self.max_retries):
            try:
                self._ensure_connection()
                
                self.channel.basic_publish(
                    exchange='',
                    routing_key=self.queue_name,
                    body=json.dumps(task_payload),
                    properties=pika.BasicProperties(
                        delivery_mode=2, 
                        priority=priority,
                        content_type='application/json'
                    )
                )
                
                logger.info(
                    f"Published task to queue: task_id={task_id}, type={task_type}",
                    extra={
                        "task_id": task_id,
                        "task_type": task_type,
                        "bot_id": bot_id,
                        "priority": priority
                    }
                )
                
                return task_id
                
            except (StreamLostError, ChannelWrongStateError, AMQPConnectionError) as e:
                logger.warning(f"RabbitMQ connection error (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    self.disconnect()
                    time.sleep(self.retry_delay)
                else:
                    logger.error(
                        f"Failed to publish task after {self.max_retries} attempts: {e}",
                        extra={
                            "task_id": task_id,
                            "task_type": task_type,
                            "bot_id": bot_id
                        },
                        exc_info=True
                    )
                    raise
            except Exception as e:
                logger.error(
                    f"Failed to publish task: {e}",
                    extra={
                        "task_id": task_id,
                        "task_type": task_type,
                        "bot_id": bot_id
                    },
                    exc_info=True
                )
                raise
    
    async def publish_file_upload_task(
        self,
        task_id: str,
        document_id: str,
        bot_id: str,
        file_path: str,
        collection_name: str
    ) -> str:
        """
        Publish file upload task to file-server (async wrapper)
        
        Args:
            task_id: Task ID
            document_id: Document ID in database
            bot_id: Bot ID
            file_path: Local file path in shared volume (/tmp/uploads/...)
            collection_name: Milvus collection name
            
        Returns:
            task_id
        """
        return await asyncio.to_thread(
            self.publish_task,
            task_type=TaskType.FILE_UPLOAD,
            bot_id=bot_id,
            data={
                "files": [
                    {
                        "path": file_path,
                        "document_id": document_id,
                        "collection_name": collection_name,
                        "metadata": {
                            "source": "upload"
                        }
                    }
                ]
            },
            task_id=task_id,
            priority=7
        )
    
    async def publish_crawl_task(
        self,
        task_id: str,
        bot_id: str,
        origin: str,
        sitemap_urls: list[str],
        collection_name: str
    ) -> str:
        """
        Publish crawl task to file-server (async wrapper)
        
        Args:
            task_id: Task ID
            bot_id: Bot ID
            origin: Origin domain to crawl
            sitemap_urls: List of specific URLs (empty = full domain crawl)
            collection_name: Milvus collection name
            
        Returns:
            task_id
        """
        return await asyncio.to_thread(
            self.publish_task,
            task_type=TaskType.CRAWL,
            bot_id=bot_id,
            data={
                "origin": origin,
                "sitemap_urls": sitemap_urls,
                "collection_name": collection_name
            },
            task_id=task_id,
            priority=5
        )

    async def publish_delete_document_task(
        self,
        task_id: str,
        bot_id: str,
        document_id: str,
        collection_name: str
    ) -> str:
        """
        Publish delete document task to file-server (async wrapper)

        Args:
            task_id: Task ID
            bot_id: Bot ID
            document_id: Document UUID to delete
            collection_name: Milvus collection name

        Returns:
            task_id
        """
        return await asyncio.to_thread(
            self.publish_task,
            task_type=TaskType.DELETE_DOCUMENT,
            bot_id=bot_id,
            data={
                "document_id": document_id,
                "collection_name": collection_name
            },
            task_id=task_id,
            priority=8
        )

    async def publish_recrawl_task(
        self,
        task_id: str,
        bot_id: str,
        document_ids: list[str],
        collection_name: str
    ) -> str:
        """
        Publish recrawl task to file-server (async wrapper)

        Args:
            task_id: Task ID
            bot_id: Bot ID
            document_ids: List of document IDs to delete from Milvus
            collection_name: Milvus collection name

        Returns:
            task_id
        """
        return await asyncio.to_thread(
            self.publish_task,
            task_type=TaskType.RECRAWL,
            bot_id=bot_id,
            data={
                "document_ids": document_ids,
                "collection_name": collection_name
            },
            task_id=task_id,
            priority=7
        )


    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()


# Singleton instance
rabbitmq_publisher = RabbitMQPublisher()


class EmailQueuePublisher:
    """
    RabbitMQ publisher for email tasks.
    Publishes email sending tasks to a dedicated queue for async processing.
    """
    
    def __init__(self):
        """Initialize email queue publisher"""
        self.rabbitmq_url = settings.RABBITMQ_URL
        self.queue_name = "email_queue"
        self.connection = None
        self.channel = None
        self.max_retries = 3
        self.retry_delay = 1
    
    def connect(self):
        """Connect to RabbitMQ with retry logic"""
        for attempt in range(self.max_retries):
            try:
                parameters = pika.URLParameters(self.rabbitmq_url)
                parameters.socket_timeout = 5
                parameters.connection_attempts = 3
                parameters.retry_delay = 2
                
                self.connection = pika.BlockingConnection(parameters)
                self.channel = self.connection.channel()
                
                self.channel.queue_declare(
                    queue=self.queue_name,
                    durable=True,
                    arguments={'x-max-priority': 10}
                )
                
                logger.info(f"Connected to RabbitMQ email queue: {self.queue_name}")
                return
                
            except AMQPConnectionError as e:
                logger.warning(f"Failed to connect to RabbitMQ (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f"Failed to connect to RabbitMQ after {self.max_retries} attempts", exc_info=True)
                    raise
            except Exception as e:
                logger.error(f"Unexpected error connecting to RabbitMQ: {e}", exc_info=True)
                raise
    
    def disconnect(self):
        """Disconnect from RabbitMQ"""
        try:
            if self.connection and not self.connection.is_closed:
                self.connection.close()
                logger.info("Disconnected from RabbitMQ email queue")
        except Exception as e:
            logger.error(f"Error disconnecting from RabbitMQ: {e}")
    
    def _ensure_connection(self):
        """Ensure we have a valid connection to RabbitMQ"""
        try:
            if not self.connection or self.connection.is_closed:
                logger.info("RabbitMQ connection is closed, reconnecting...")
                self.connect()
            elif not self.channel or self.channel.is_closed:
                logger.info("RabbitMQ channel is closed, recreating...")
                self.channel = self.connection.channel()
        except Exception as e:
            logger.error(f"Error ensuring RabbitMQ connection: {e}", exc_info=True)
            self.disconnect()
            self.connect()
    
    def publish_email_task(
        self,
        template_name: str,
        recipient_email: str,
        subject: str,
        context: Dict[str, Any],
        priority: int = 5
    ) -> str:
        """
        Publish email task to queue (BLOCKING - must be wrapped in to_thread).
        
        Args:
            template_name: Email template filename
            recipient_email: Recipient email address
            subject: Email subject
            context: Template context data
            priority: Task priority (0-10, higher = more priority)
            
        Returns:
            task_id: Generated task ID
        """
        task_id = str(uuid.uuid4())
        
        self._ensure_connection()
        
        task_data = {
            "task_id": task_id,
            "template_name": template_name,
            "recipient_email": recipient_email,
            "subject": subject,
            "context": context,
            "created_at": time.time()
        }
        
        try:
            self.channel.basic_publish(
                exchange='',
                routing_key=self.queue_name,
                body=json.dumps(task_data),
                properties=pika.BasicProperties(
                    delivery_mode=2, 
                    priority=priority,
                    content_type='application/json'
                )
            )
            
            logger.info(
                f"Published email task to queue",
                extra={
                    "task_id": task_id,
                    "recipient": recipient_email,
                    "template": template_name
                }
            )
            
            return task_id
            
        except Exception as e:
            logger.error(f"Failed to publish email task: {e}", exc_info=True)
            raise


email_queue_publisher = EmailQueuePublisher()