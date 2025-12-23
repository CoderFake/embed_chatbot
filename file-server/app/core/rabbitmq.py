"""
RabbitMQ connection and consumer management
"""
import pika
import json
import threading
from typing import Callable, Optional
from pika.adapters.blocking_connection import BlockingChannel

from app.config.settings import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class RabbitMQClient:
    """
    RabbitMQ client for consuming messages from queue.
    Thread-safe with lock to prevent concurrent basic_get() calls.
    """

    def __init__(self):
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[BlockingChannel] = None
        self.callback_function: Optional[Callable] = None
        self._lock = threading.Lock()
        
    def connect(self):
        """Connect to RabbitMQ server"""
        try:
            parameters = pika.URLParameters(settings.RABBITMQ_URL)
            parameters.heartbeat = settings.RABBITMQ_HEARTBEAT
            
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            
            self.channel.queue_declare(
                queue=settings.RABBITMQ_QUEUE_NAME,
                durable=True, 
                arguments={
                    'x-dead-letter-exchange': '',
                    'x-dead-letter-routing-key': f'{settings.RABBITMQ_QUEUE_NAME}_dlq',
                    'x-max-priority': 10  
                }
            )
            
            self.channel.basic_qos(prefetch_count=settings.RABBITMQ_PREFETCH_COUNT)
            
            logger.info(
                f"Connected to RabbitMQ: {settings.RABBITMQ_URL}",
                extra={
                    "queue": settings.RABBITMQ_QUEUE_NAME,
                    "heartbeat": settings.RABBITMQ_HEARTBEAT
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}", exc_info=True)
            raise
    
    def consume_message(self, timeout: float = 1.0) -> Optional[dict]:
        """
        Consume a single message from queue (non-blocking).
        Thread-safe with lock to prevent DuplicateGetOkCallback error.

        Args:
            timeout: Timeout in seconds

        Returns:
            Message dict with _delivery_tag or None if no message
        """
        if not self.channel:
            raise RuntimeError("Not connected to RabbitMQ. Call connect() first.")

        with self._lock:
            try:
                if not self.channel.is_open:
                    logger.warning("Channel is closed, reconnecting...")
                    self.connect()

                if not self.connection or not self.connection.is_open:
                    logger.warning("Connection is closed, reconnecting...")
                    self.connect()

                method, properties, body = self.channel.basic_get(
                    queue=settings.RABBITMQ_QUEUE_NAME,
                    auto_ack=False
                )

                if method is None:
                    return None

                message = json.loads(body.decode('utf-8'))
                message['_delivery_tag'] = method.delivery_tag

                return message

            except pika.exceptions.DuplicateGetOkCallback as e:
                logger.error(f"DuplicateGetOkCallback error - recreating channel: {e}")
                try:
                    if self.channel:
                        self.channel.close()
                    self.channel = self.connection.channel()
                    self.channel.queue_declare(
                        queue=settings.RABBITMQ_QUEUE_NAME,
                        durable=True,
                        arguments={
                            'x-dead-letter-exchange': '',
                            'x-dead-letter-routing-key': f'{settings.RABBITMQ_QUEUE_NAME}_dlq',
                            'x-max-priority': 10
                        }
                    )
                    self.channel.basic_qos(prefetch_count=settings.RABBITMQ_PREFETCH_COUNT)
                    logger.info("Channel recreated successfully")
                except Exception as reconnect_error:
                    logger.error(f"Failed to recreate channel: {reconnect_error}", exc_info=True)
                return None
            except Exception as e:
                logger.error(f"Error consuming message: {e}", exc_info=True)
                return None
    
    def ack_message(self, delivery_tag: int):
        """
        Acknowledge message processing.
        Thread-safe with lock.
        """
        with self._lock:
            if self.channel and self.channel.is_open:
                self.channel.basic_ack(delivery_tag=delivery_tag)

    def nack_message(self, delivery_tag: int, requeue: bool = False):
        """
        Negative acknowledge message.
        Thread-safe with lock.
        """
        with self._lock:
            if self.channel and self.channel.is_open:
                self.channel.basic_nack(delivery_tag=delivery_tag, requeue=requeue)
    
    def close(self):
        """Alias for disconnect()"""
        self.disconnect()
    
    def disconnect(self):
        """Close RabbitMQ connection"""
        try:
            if self.channel and self.channel.is_open:
                self.channel.close()
            if self.connection and self.connection.is_open:
                self.connection.close()
            logger.info("Disconnected from RabbitMQ")
        except Exception as e:
            logger.error(f"Error disconnecting from RabbitMQ: {e}")
    
    def start_consuming(self, callback: Callable):
        """
        Start consuming messages from queue
        
        Args:
            callback: Function to call when message received
                     signature: callback(ch, method, properties, body)
        """
        if not self.channel:
            raise RuntimeError("Not connected to RabbitMQ. Call connect() first.")
        
        self.callback_function = callback
        
        self.channel.basic_consume(
            queue=settings.RABBITMQ_QUEUE_NAME,
            on_message_callback=self._on_message_callback,
            auto_ack=False 
        )
        
        logger.info(
            f"Worker started. Consuming from queue: {settings.RABBITMQ_QUEUE_NAME}",
            extra={"prefetch": settings.RABBITMQ_PREFETCH_COUNT}
        )
        
        try:
            self.channel.start_consuming()
        except KeyboardInterrupt:
            logger.info("Worker stopped by user")
            self.channel.stop_consuming()
        except Exception as e:
            logger.error(f"Error in consumer loop: {e}", exc_info=True)
            raise
    
    def _on_message_callback(self, ch, method, properties, body):
        """
        Internal callback wrapper that handles ACK/NACK
        """
        try:
            message = json.loads(body.decode('utf-8'))
            
            task_id = message.get('task_id', 'unknown')
            logger.info(
                f"Received message",
                extra={
                    "task_id": task_id,
                    "task_type": message.get('type'),
                    "delivery_tag": method.delivery_tag
                }
            )
            
            if self.callback_function:
                self.callback_function(ch, method, properties, message)
            
            ch.basic_ack(delivery_tag=method.delivery_tag)
            
            logger.info(
                f"Message processed successfully",
                extra={"task_id": task_id}
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON message: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            
        except Exception as e:
            logger.error(
                f"Error processing message: {e}",
                extra={
                    "task_id": message.get('task_id') if 'message' in locals() else 'unknown',
                    "delivery_tag": method.delivery_tag
                },
                exc_info=True
            )

            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


rabbitmq_client = RabbitMQClient()
