"""Configuration settings for visitor grader."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""
    
    # Service
    APP_NAME: str = "Visitor Grader"
    APP_VERSION: str = "1.0.0"
    ENV: str = "dev"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    TIMEZONE: str = "UTC"
    
    # Database
    DATABASE_URL: str
    
    # Redis
    REDIS_URL: str = "redis://redis:6379/0"
    BOT_CONFIG_TTL: int = 3600
    
    # Security
    SECRET_KEY: str
    ENCRYPTION_SALT: str = "chatbot_salt_key"
    
    # RabbitMQ
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    VISITOR_GRADING_QUEUE: str = "visitor_grading_queue"
    RABBITMQ_PREFETCH_COUNT: int = 1
    RABBITMQ_RECONNECT_DELAY: int = 5
    RABBITMQ_HEARTBEAT: int = 60
    RABBITMQ_CONNECTION_TIMEOUT: int = 30
    
    # Backend Webhook
    BACKEND_API_URL: str = "http://backend:8000"
    BACKEND_WEBHOOK_SECRET: str
    WEBHOOK_TIMEOUT: int = 30
    WEBHOOK_MAX_RETRIES: int = 3
    
    # Scoring Thresholds
    HOT_LEAD_THRESHOLD: int = 70
    WARM_LEAD_THRESHOLD: int = 40
    
    # Output Language
    GRADING_OUTPUT_LANGUAGE: str = "vietnamese"
    
    # Milvus Configuration
    MILVUS_HOST: str = "milvus"
    MILVUS_PORT: int = 19530
    MILVUS_USER: str = ""
    MILVUS_PASSWORD: str = ""
    MILVUS_VECTOR_DIM: int = 768
    
    # Embedding Model
    EMBEDDING_MODEL_NAME: str = "intfloat/multilingual-e5-base"
    EMBEDDING_DEVICE: str = "cpu"
    EMBEDDING_BATCH_SIZE: int = 32
    
    # Retrieval & Rerank
    RETRIEVAL_TOP_K: int = 20
    RERANK_TOP_K: int = 5
    RERANK_MODEL: str = "BAAI/bge-reranker-base"
    
    # Embedding Token Limit
    MAX_SEQ_LENGTH: int = 512
    
    # Progress Tracking
    PROGRESS_UPDATE_INTERVAL: float = 2.0  
    PROGRESS_MIN_DELTA: float = 5.0
    
    # Server
    PORT: int = 8002
    
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


