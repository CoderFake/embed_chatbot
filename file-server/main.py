"""
File Server - Main entry point with FastAPI
Handles file processing tasks from RabbitMQ queue with health monitoring
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
import uvicorn

from app.api.health import router as health_router
from app.workers.worker_pool import run_worker_pool
from app.config.settings import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

logging.getLogger("pika").setLevel(logging.WARNING)
logging.getLogger("aiormq").setLevel(logging.WARNING)
logging.getLogger("aio_pika").setLevel(logging.WARNING)
logging.getLogger("transformers").setLevel(logging.WARNING)
logging.getLogger("tokenizers").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


def setup_directories():
    """Ensure required directories exist"""
    dirs = [
        settings.TEMP_UPLOAD_DIR,
        settings.TEMP_CRAWL_DIR,
        Path("logs")
    ]
    
    for dir_path in dirs:
        dir_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Ensured directory exists: {dir_path}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI."""
    # Startup
    logger.info("=" * 80)
    logger.info("File Server Starting...")
    logger.info("=" * 80)
    logger.info(f"Worker Pool Size: {settings.WORKER_POOL_SIZE}")
    logger.info(f"RabbitMQ URL: {settings.RABBITMQ_URL}")
    logger.info(f"RabbitMQ Queue: {settings.RABBITMQ_QUEUE_NAME}")
    logger.info(f"Redis: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
    logger.info(f"Milvus Host: {settings.MILVUS_HOST}:{settings.MILVUS_PORT}")
    logger.info(f"MinIO Endpoint: {settings.MINIO_ENDPOINT}")
    logger.info(f"Embedding Model: {settings.EMBEDDING_MODEL_NAME}")
    logger.info(f"Device: {settings.EMBEDDING_DEVICE}")
    logger.info("=" * 80)
    
    try:
        setup_directories()
        asyncio.create_task(run_worker_pool(pool_size=settings.WORKER_POOL_SIZE))
        logger.info("Worker pool started")
        
        yield
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        raise
        
    finally:
        logger.info("File Server stopped")

app = FastAPI(
    title= settings.APP_NAME,
    description="Document processing and embedding service",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.include_router(health_router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": settings.APP_NAME,
        "status": "running",
        "version": settings.APP_VERSION,
        "worker_pool_size": settings.WORKER_POOL_SIZE,
    }


def main():
    """Run the FastAPI application."""
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.PORT if hasattr(settings, 'PORT') else 8003,
        log_level="info",
    )


if __name__ == "__main__":
    main()

