"""Entry point for the chat worker service with FastAPI."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
import uvicorn

from app.api.health import router as health_router
from app.core.service_manager import service_manager
from app.services.queue_consumer import chat_queue_consumer
from app.utils.logging import get_logger
from app.config.settings import settings

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI."""
    # Startup
    logger.info("Starting Chat Worker service...")
    try:
        await service_manager.initialize()
        logger.info("Service manager initialized")
        
        try:
            from app.services.chat.reranker import warmup as reranker_warmup
            from app.services.embedding import warmup as embedding_warmup
            
            logger.info("Starting model warmup...")
            results = await asyncio.gather(
                reranker_warmup(),
                embedding_warmup(),
                return_exceptions=True
            )
            
            errors = [r for r in results if isinstance(r, Exception)]
            if errors:
                for err in errors:
                    logger.error(f"Model warmup error: {err}")
            else:
                logger.info("All models warmed up successfully (reranker + embedding)")
        except Exception as e:
            logger.warning(f"Failed to warmup models: {e}", exc_info=True)
        
        asyncio.create_task(chat_queue_consumer.start_consuming())
        logger.info("Queue consumer started")
        
        yield
        
    except Exception as e:
        logger.error("Failed to start chat worker", exc_info=e)
        raise
        
    finally:
        # Shutdown
        logger.info("Shutting down Chat Worker service...")
        try:
            await chat_queue_consumer.stop_consuming()
            await service_manager.cleanup()
        except Exception as e:
            logger.error("Error during cleanup", exc_info=e)
        logger.info("Chat Worker service stopped")


# Create FastAPI app
app = FastAPI(
    title="Chat Worker Service",
    description="AI-powered chat processing service with LangGraph",
    version="1.0.0",
    lifespan=lifespan,
)

# Register routers
app.include_router(health_router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "chat-worker",
        "status": "running",
        "version": "1.0.0",
    }


def main() -> None:
    """Run the FastAPI application."""
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.PORT if hasattr(settings, 'PORT') else 8001,
        log_level="info",
    )


if __name__ == "__main__":
    main()

