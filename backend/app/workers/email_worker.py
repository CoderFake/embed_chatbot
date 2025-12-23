"""
Email Worker - Consumes email tasks from RabbitMQ queue and sends emails.
Run this as a separate process: python -m app.workers.email_worker
"""
import asyncio
import json
import signal
import sys
from typing import Dict, Any

import pika
from pika.exceptions import AMQPConnectionError

from app.config.settings import settings
from app.utils.email_utils import send_mail
from app.utils.logging import get_logger

logger = get_logger(__name__)


class EmailWorker:
    """
    Email worker that consumes email tasks from RabbitMQ queue.
    Processes tasks asynchronously and sends emails via SMTP.
    """
    
    def __init__(self):
        """Initialize email worker"""
        self.rabbitmq_url = settings.RABBITMQ_URL
        self.queue_name = "email_queue"
        self.connection = None
        self.channel = None
        self.should_stop = False
        
    def connect(self):
        """Connect to RabbitMQ"""
        try:
            parameters = pika.URLParameters(self.rabbitmq_url)
            parameters.socket_timeout = 10
            parameters.connection_attempts = 5
            parameters.retry_delay = 2
            
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            
            self.channel.queue_declare(
                queue=self.queue_name,
                durable=True,
                arguments={'x-max-priority': 10}
            )
            
            self.channel.basic_qos(prefetch_count=1)
            
            logger.info(f"Email worker connected to queue: {self.queue_name}")
            
        except AMQPConnectionError as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Unexpected error connecting to RabbitMQ: {e}", exc_info=True)
            raise
    
    def disconnect(self):
        """Disconnect from RabbitMQ"""
        try:
            if self.connection and not self.connection.is_closed:
                self.connection.close()
                logger.info("Email worker disconnected from RabbitMQ")
        except Exception as e:
            logger.error(f"Error disconnecting from RabbitMQ: {e}")
    
    def process_email_task(
        self,
        ch,
        method,
        properties,
        body: bytes
    ):
        """
        Process email task from queue.
        
        Args:
            ch: Channel
            method: Delivery method
            properties: Message properties
            body: Message body (JSON)
        """
        try:
            # Parse task data
            task_data = json.loads(body.decode())
            task_id = task_data.get("task_id", "unknown")
            
            logger.info(
                f"Processing email task",
                extra={
                    "task_id": task_id,
                    "recipient": task_data.get("recipient_email"),
                    "template": task_data.get("template_name")
                }
            )
            
            send_mail(
                template_name=task_data["template_name"],
                recipient_email=task_data["recipient_email"],
                subject=task_data["subject"],
                context=task_data["context"],
                request=None
            )
            
            ch.basic_ack(delivery_tag=method.delivery_tag)
            
            logger.info(
                f"Email sent successfully",
                extra={
                    "task_id": task_id,
                    "recipient": task_data.get("recipient_email")
                }
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in email task: {e}", exc_info=True)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            
        except KeyError as e:
            logger.error(f"Missing required field in email task: {e}", exc_info=True)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}", exc_info=True)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
    
    def start_consuming(self):
        """Start consuming email tasks from queue"""
        try:
            self.connect()
            
            self.channel.basic_consume(
                queue=self.queue_name,
                on_message_callback=self.process_email_task,
                auto_ack=False
            )
            
            logger.info("Email worker started. Waiting for email tasks...")
            logger.info("Press Ctrl+C to stop")
            
            self.channel.start_consuming()
            
        except KeyboardInterrupt:
            logger.info("Email worker stopped by user")
            self.stop()
        except Exception as e:
            logger.error(f"Email worker error: {e}", exc_info=True)
            self.stop()
            raise
    
    def stop(self):
        """Stop consuming and disconnect"""
        self.should_stop = True
        try:
            if self.channel:
                self.channel.stop_consuming()
            self.disconnect()
        except Exception as e:
            logger.error(f"Error stopping email worker: {e}")


def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}, shutting down gracefully...")
    sys.exit(0)


def main():
    """Main entry point for email worker"""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("Starting Email Worker...")
    
    worker = EmailWorker()
    
    try:
        worker.start_consuming()
    except Exception as e:
        logger.error(f"Email worker failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

