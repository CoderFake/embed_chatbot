from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
import secrets

from app.config.settings import settings
from app.core.database import db_manager, redis_manager
from app.core.middleware import setup_middlewares
from app.utils.logging import setup_logging, get_logger
from app.api.v1.router import api_router
from app.common.enums import Environment
from app.services.chat_queue import chat_queue_service
from app.services.storage import minio_service
from app.services.progress_listener import progress_listener_service


setup_logging()
logger = get_logger(__name__)

security = HTTPBasic()


def verify_docs_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    """
    Verify basic auth credentials for API documentation access.
    Only required in staging/production environments.
    """
    if settings.ENV in ["prod", "stg"]:
        if not settings.DOCS_USERNAME or not settings.DOCS_PASSWORD:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="API documentation is not available"
            )
        
        correct_username = secrets.compare_digest(
            credentials.username.encode("utf8"),
            settings.DOCS_USERNAME.encode("utf8")
        )
        correct_password = secrets.compare_digest(
            credentials.password.encode("utf8"),
            settings.DOCS_PASSWORD.encode("utf8")
        )
        
        if not (correct_username and correct_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect credentials",
                headers={"WWW-Authenticate": "Basic"},
            )
    
    return True


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    logger.info("Starting application...")
    
    try:
        await db_manager.connect()
        logger.info("Database connection established")
        
        await redis_manager.connect()
        logger.info("Redis connection established")

        app.state.redis = redis_manager.get_redis()
        app.state.db_session = db_manager.get_session

        await chat_queue_service.connect()
        logger.info("Chat queue service connected")
        
        # Start progress listener service for real-time notification updates
        await progress_listener_service.start()
        
        try:
            if not minio_service.client.bucket_exists(settings.MINIO_PUBLIC_BUCKET):
                logger.info("Creating public assets bucket...")
                minio_service.create_bucket(settings.MINIO_PUBLIC_BUCKET)
                minio_service.set_bucket_policy_public(settings.MINIO_PUBLIC_BUCKET)
                logger.info("Public bucket created and configured")
        except Exception as e:
            logger.error(f"Failed to initialize public bucket: {e}")
        
        logger.info("Application started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise
    
    yield
    
    logger.info("Shutting down application...")
    
    try:
        # Stop progress listener service
        await progress_listener_service.stop()
        
        await redis_manager.disconnect()
        logger.info("Redis connection closed")

        await db_manager.disconnect()
        logger.info("Database connection closed")

        await chat_queue_service.disconnect()
        logger.info("Chat queue service disconnected")
        
        logger.info("Application shutdown complete")
        
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


DEBUG = settings.ENV == Environment.DEVELOPMENT.value or settings.DEBUG
RELOAD = settings.ENV == Environment.DEVELOPMENT.value

if settings.ENV in [Environment.PRODUCTION.value, Environment.STAGING.value]:
    if settings.DOCS_USERNAME and settings.DOCS_PASSWORD:
        docs_url = None  
        redoc_url = None  
        openapi_url = None 
    else:
        docs_url = None
        redoc_url = None
        openapi_url = None
else:
    docs_url = "/docs"
    redoc_url = "/redoc"
    openapi_url = "/openapi.json"

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Embed chatbot platform",
    lifespan=lifespan,
    debug=DEBUG,
    docs_url=docs_url,
    redoc_url=redoc_url,
    openapi_url=openapi_url
)

setup_middlewares(app)


if settings.ENV in [Environment.PRODUCTION.value, Environment.STAGING.value] and settings.DOCS_USERNAME and settings.DOCS_PASSWORD:
    
    @app.get("/docs", include_in_schema=False)
    async def get_documentation(_: bool = Depends(verify_docs_credentials)):
        """Protected Swagger UI documentation"""
        return get_swagger_ui_html(openapi_url="/openapi.json", title=f"{settings.APP_NAME} - Docs")
    
    @app.get("/redoc", include_in_schema=False)
    async def get_redoc(_: bool = Depends(verify_docs_credentials)):
        """Protected ReDoc documentation"""
        return get_redoc_html(openapi_url="/openapi.json", title=f"{settings.APP_NAME} - ReDoc")
    
    @app.get("/openapi.json", include_in_schema=False)
    async def get_open_api_endpoint(_: bool = Depends(verify_docs_credentials)):
        """Protected OpenAPI schema"""
        return app.openapi()


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint for monitoring and load balancers.
    """
    try:
        redis = redis_manager.get_redis()
        await redis.ping()
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "healthy",
                "service": settings.APP_NAME,
                "version": settings.APP_VERSION,
                "database": "connected",
                "redis": "connected"
            }
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "service": settings.APP_NAME,
                "version": settings.APP_VERSION,
                "error": str(e)
            }
        )


@app.get("/", tags=["Root"])
async def root():
    """
    Root endpoint.
    """
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health"
    }


app.include_router(api_router, prefix=settings.API_V1_PREFIX)


if __name__ == "__main__":
    import uvicorn
    
    uvicorn_config = {
        "app": "main:app",
        "host": "0.0.0.0",
        "port": 8000,
    }
    
    if settings.ENV == Environment.DEVELOPMENT.value:
        uvicorn_config.update({
            "reload": True,
            "log_level": "debug",
        })
        logger.info("Starting in DEVELOPMENT mode (reload=True, debug=True)")
    else:
        uvicorn_config.update({
            "reload": False,
            "log_level": "info",
        })
        logger.info(f"Starting in {settings.ENV.upper()} mode (reload=False)")
    
    uvicorn.run(**uvicorn_config)

