"""Main application entry point with FastAPI."""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
import uvicorn

from app.api.health import router as health_router
from app.core.redis_client import redis_client
from app.services.queue_consumer import queue_consumer
from app.utils.logging import get_logger
from app.config.settings import settings

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI."""
    logger.info("Starting Visitor Grader service...")
    try:
        await redis_client.initialize()
        logger.info("Redis initialized")
        
        asyncio.create_task(queue_consumer.run())
        logger.info("Queue consumer started")
        
        yield
        
    finally:
        logger.info("Shutting down Visitor Grader service...")
        await redis_client.cleanup()
        logger.info("Visitor Grader service stopped")

app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered visitor lead scoring and grading service",
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
    }


def main():
    """Run the FastAPI application."""
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.PORT if hasattr(settings, 'PORT') else 8002,
        log_level="info",
    )


if __name__ == "__main__":
    main()


