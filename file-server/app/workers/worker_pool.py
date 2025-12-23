"""
Worker pool manager - manages concurrent task processing workers
"""
import asyncio
from typing import Optional
import signal

from app.workers.task_processor import TaskProcessor
from app.core.rabbitmq import RabbitMQClient
from app.config.settings import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class WorkerPool:
    """
    Manages a pool of concurrent workers for processing tasks.
    
    Features:
    - Configurable worker pool size
    - Graceful shutdown
    - Error handling and recovery
    - Signal handling (SIGTERM, SIGINT)
    """
    
    def __init__(self, pool_size: Optional[int] = None):
        """
        Initialize worker pool
        
        Args:
            pool_size: Number of concurrent workers (default from settings)
        """
        self.pool_size = pool_size or settings.WORKER_POOL_SIZE
        self.task_processor = TaskProcessor()
        
        self.workers = []
        self.shutdown_event = asyncio.Event()
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(sig, frame):
            logger.info(f"Received signal {sig}, initiating shutdown...")
            self.shutdown_event.set()
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
    
    async def worker_loop(self, worker_id: int):
        """
        Worker loop - consumes and processes tasks
        Each worker has its own RabbitMQ connection to avoid race conditions
        
        Args:
            worker_id: Worker identifier
        """
        logger.info(f"Worker {worker_id} started")
        
        rabbitmq_client = RabbitMQClient()
        logger.info(f"Worker {worker_id} connecting to RabbitMQ...")
        
        try:
            await asyncio.to_thread(rabbitmq_client.connect)
            logger.info(f"Worker {worker_id} connected to RabbitMQ successfully")
        except Exception as e:
            logger.error(f"Worker {worker_id} failed to connect to RabbitMQ: {e}", exc_info=True)
            return
        
        try:
            logger.info(f"Worker {worker_id} entering main loop")
            while not self.shutdown_event.is_set():
                try:
                    task_data = await asyncio.wait_for(
                        asyncio.to_thread(
                            rabbitmq_client.consume_message,
                            timeout=5.0 
                        ),
                        timeout=10.0
                    )
                    
                    if task_data is None:
                        await asyncio.sleep(0.1)
                        continue
                    
                    logger.info(
                        f"Worker {worker_id} processing task {task_data.get('task_id')}",
                        extra={
                            "worker_id": worker_id,
                            "task_id": task_data.get("task_id"),
                            "task_type": task_data.get("task_type")
                        }
                    )
                    
                    success = await self.task_processor.process_task(task_data)
                    
                    if success:
                        await asyncio.to_thread(
                            rabbitmq_client.ack_message,
                            task_data.get("_delivery_tag")
                        )
                    else:
                        await asyncio.to_thread(
                            rabbitmq_client.nack_message,
                            task_data.get("_delivery_tag"),
                            requeue=False  
                        )
                
                except asyncio.TimeoutError:
                    # Timeout is normal when no messages available
                    continue
                
                except Exception as e:
                    logger.error(
                        f"Worker {worker_id} error: {e}",
                        extra={"worker_id": worker_id, "error": str(e)},
                        exc_info=True
                    )
                    await asyncio.sleep(1)  
        
        finally:
            await asyncio.to_thread(rabbitmq_client.close)
            logger.info(f"Worker {worker_id} stopped")
    
    async def start(self):
        """Start worker pool"""
        logger.info(f"Starting worker pool with {self.pool_size} workers")
        
        self.workers = [
            asyncio.create_task(self.worker_loop(i))
            for i in range(self.pool_size)
        ]
        
        logger.info(f"Worker pool started with {self.pool_size} workers")
        
        await self.shutdown_event.wait()
        
        await self.shutdown()
    
    async def shutdown(self):
        """Gracefully shutdown worker pool"""
        logger.info("Shutting down worker pool...")
        
        for worker in self.workers:
            worker.cancel()
        
        await asyncio.gather(*self.workers, return_exceptions=True)
        
        await self.task_processor.cleanup()
        
        logger.info("Worker pool shutdown complete")


async def run_worker_pool(pool_size: Optional[int] = None):
    """
    Run worker pool (main entry point)
    
    Args:
        pool_size: Number of concurrent workers
    """
    pool = WorkerPool(pool_size=pool_size)
    await pool.start()
