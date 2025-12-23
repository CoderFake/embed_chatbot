"""
File Server Settings
Environment configuration for file processing service
"""
from typing import Optional
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    File Server settings loaded from environment variables
    Shares common environment variables with backend service
    """
    
    APP_NAME: str = "File Processing Service"
    APP_VERSION: str = "1.0.0"
    ENV: str = "dev"
    DEBUG: bool = False
    TIMEZONE: str = "UTC"
    
    RABBITMQ_URL: str = "amqp://guest:guest@rabbitmq:5672/"
    RABBITMQ_QUEUE_NAME: str = "file_processing_queue"
    RABBITMQ_PREFETCH_COUNT: int = 1
    RABBITMQ_HEARTBEAT: int = 600  
    RABBITMQ_ACK_TIMEOUT: int = 1800 
    
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_MAX_CONNECTIONS: int = 50
    REDIS_SOCKET_TIMEOUT: int = 5
    REDIS_SOCKET_CONNECT_TIMEOUT: int = 5
    
    MILVUS_HOST: str = "milvus"
    MILVUS_PORT: int = 19530
    MILVUS_USER: str = ""
    MILVUS_PASSWORD: str = ""
    MILVUS_VECTOR_DIM: int = 768

    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_SECURE: bool = False
    
    BACKEND_API_URL: str = "http://backend:8000"
    BACKEND_WEBHOOK_SECRET: str
    
    # Server
    PORT: int = 8003
    
    WORKER_POOL_SIZE: int = 4 
    WORKER_MAX_RETRIES: int = 3
    WORKER_RETRY_DELAY: int = 5  
    
    MINIO_BATCH_SIZE: int = 100  
    MILVUS_BATCH_SIZE: int = 1000  
    
    PROGRESS_MIN_DELTA: float = 5.0  
    PROGRESS_MIN_INTERVAL: float = 3.0  
    PROGRESS_STATE_TTL: int = 86400 
    
    EMBEDDING_MODEL_NAME: str = "intfloat/multilingual-e5-base"
    EMBEDDING_DEVICE: str = "cpu" 
    EMBEDDING_BATCH_SIZE: int = 32
    CRAWL_EMBEDDING_BATCH_SIZE: int = 32
    
    CHUNK_SIZE: int = 300 
    CHUNK_OVERLAP: int = 128
    
    # Crawling Configuration
    MAX_CRAWL_PAGES: int = 100  
    CRAWL_MAX_DEPTH: int = 3  
    CRAWL_MAX_CONCURRENT: int = 5 
    CRAWL_TIMEOUT: int = 30  
    CRAWL_PROGRESS_INTERVAL: int = 5  
    CRAWL_BATCH_SIZE: int = 10 
    
    CRAWL4AI_URL: str = "http://crawl4ai:11235" 
    CRAWL4AI_API_TOKEN: str = "change-this-api-token" 
    CRAWL4AI_TIMEOUT: int = 60 
    CRAWL4AI_WORD_COUNT_THRESHOLD: int = 10  
    
    TEMP_UPLOAD_DIR: Path = Path("/tmp/uploads")
    TEMP_CRAWL_DIR: Path = Path("/tmp/crawl")
    
    LOG_LEVEL: str = "INFO"

    TIMEZONE: str = "UTC"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode"""
        return self.ENV == "dev"
    
    @property
    def is_staging(self) -> bool:
        """Check if running in staging mode"""
        return self.ENV == "stg"
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode"""
        return self.ENV == "prod"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    def __init__(self, **kwargs):
        """Initialize settings and auto-configure DEBUG based on ENV if not explicitly set."""
        super().__init__(**kwargs)
        
        if "DEBUG" not in kwargs:
            self.DEBUG = self.ENV == "dev"


settings = Settings()