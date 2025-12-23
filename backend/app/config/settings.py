from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from app.common.enums import Environment, AuthType


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """
    
    # Application
    APP_NAME: str = "Chatbot Embed Platform"
    APP_VERSION: str = "1.0.0"
    ENV: str = Environment.DEVELOPMENT.value
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    TIMEZONE: str = "UTC"
    
    # API Documentation
    DOCS_USERNAME: Optional[str] = None  
    DOCS_PASSWORD: Optional[str] = None  
    
    # Database Configuration
    DATABASE_URL: str
    DB_ECHO: bool = False
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 40
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 3600
    
    # Redis Configuration
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_MAX_CONNECTIONS: int = 50
    REDIS_SOCKET_TIMEOUT: int = 5
    REDIS_SOCKET_CONNECT_TIMEOUT: int = 5
    REDIS_URL: Optional[str] = None
    
    # Cache TTL Configuration (seconds)
    CACHE_DEFAULT_TTL: int = 3600  # 1 hour
    CACHE_USER_TTL: int = 3600
    CACHE_BOT_TTL: int = 3600
    CACHE_DOCUMENT_TTL: int = 1800  # 30 minutes
    CACHE_VISITOR_TTL: int = 1800
    CACHE_PROVIDER_TTL: int = 7200  # 2 hours
    CACHE_MODEL_TTL: int = 7200
    CACHE_BOT_CONFIG_TTL: int = 3600
    CACHE_ALLOWED_ORIGINS_TTL: int = 3600
    CACHE_ANALYTICS_OVERVIEW_TTL: int = 300  # 5 minutes
    CACHE_ANALYTICS_BOT_TTL: int = 300
    CACHE_LIST_TTL: int = 600  # 10 minutes
    CACHE_BLACKLIST_TTL: int = 86400  # 24 hours
    CACHE_RATE_LIMIT_TTL: int = 60  # 1 minute
    
    # JWT Configuration
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    WIDGET_TOKEN_EXPIRE_HOURS: int = 1
    INVITE_TOKEN_EXPIRE_DAYS: int = 7
    
    # Password & Encryption
    PASSWORD_MIN_LENGTH: int = 8
    PASSWORD_RESET_EXPIRE_HOURS: int = 1
    SECRET_KEY: str
    ENCRYPTION_KEY: Optional[str] = None
    ENCRYPTION_SALT: str = "chatbot_salt_key" 
    
    # Root User (for initial setup)
    ROOT_EMAIL: Optional[str] = None
    ROOT_PASSWORD: Optional[str] = None
    
    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_WIDGET_PER_MINUTE: int = 20
    RATE_LIMIT_IP_PER_MINUTE: int = 100
    
    # RabbitMQ Configuration
    RABBITMQ_URL: str = "amqp://guest:guest@rabbitmq:5672/"
    RABBITMQ_QUEUE_NAME: str = "file_processing_queue"
    RABBITMQ_VISITOR_GRADER_QUEUE: str = "visitor_grading_queue"

    # MinIO Configuration
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_SECURE: bool = False
    MINIO_BUCKET_NAME: str = "chatbot-documents"
    MINIO_PUBLIC_BUCKET: str = "public-assets"
    MINIO_PUBLIC_URL: str = "https://mac-minio.hoangdieuit.io.vn"

    # Chat Queue
    CHAT_QUEUE_NAME: str = "chat_processing_queue"
    CHAT_TASK_TTL: int = 600
    MAX_CONCURRENT_TASKS: int = 1000
    
    # Webhook Secret
    BACKEND_WEBHOOK_SECRET: str = "change-this-webhook-secret"
    
    # Progress State Cache
    PROGRESS_STATE_TTL: int = 600
    
    # CORS Configuration
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",  
        "http://localhost:3001", 
        "http://localhost:18000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:18000",
    ]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list[str] = ["*"]
    CORS_ALLOW_HEADERS: list[str] = ["*"]
    
    # Email Configuration
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_TLS: bool = True
    SMTP_USER: Optional[str] = None
    SMTP_PASS: Optional[str] = None
    EMAIL_FROM: Optional[str] = None
    EMAIL_FROM_NAME: str = "Chatbot Platform"
    EMAIL_TEMPLATES_DIR: str = "app/static/templates"
    FRONTEND_URL: str = "http://gg-frontend.hoangdieuit.io.vn"
    BACKEND_URL: Optional[str] = "https://gg-backend.hoangdieuit.io.vn"

    # Document Upload/Crawl
    UPLOAD_DIR: str = "/tmp/uploads"
    CRAWL_DIR: str = "/tmp/crawl"
    
    # Monitoring
    SENTRY_DSN: Optional[str] = None
    ENABLE_METRICS: bool = False

    
    # Development
    RELOAD: bool = False
    SKIP_ORIGIN_CHECK: bool = True
    
    # =========================================================================
    # DEFAULT PROVIDERS CONFIGURATION
    # =========================================================================
    DEFAULT_PROVIDERS: list[dict] = [
        {
            "name": "OpenAI",
            "slug": "openai",
            "api_base_url": "https://api.openai.com/v1",
            "auth_type": AuthType.API_KEY.value,
            "models": [
                {
                    "name": "gpt-4o",
                    "model_type": "chat",
                    "context_window": 128000,
                    "pricing": 5.0
                },
                {
                    "name": "gpt-4o-mini",
                    "model_type": "chat",
                    "context_window": 128000,
                    "pricing": 0.15
                },
                {
                    "name": "gpt-3.5-turbo",
                    "model_type": "chat",
                    "context_window": 16385,
                    "pricing": 0.5
                }
            ]
        },
        {
            "name": "Google Gemini",
            "slug": "gemini",
            "api_base_url": "https://generativelanguage.googleapis.com/v1beta",
            "auth_type": AuthType.API_KEY.value,
            "models": [
                {
                    "name": "gemini-2.5-pro",
                    "model_type": "chat",
                    "context_window": 1000000,
                    "pricing": 1.25
                },
                {
                    "name": "gemini-2.5-flash",
                    "model_type": "chat",
                    "context_window": 1000000,
                    "pricing": 0.075
                }
            ]
        },
        {
            "name": "Ollama",
            "slug": "ollama",
            "api_base_url": "http://host.docker.internal:11434",
            "auth_type": AuthType.OTP.value,
            "models": [
                {
                    "name": "llama3.1:8b",
                    "model_type": "chat",
                    "context_window": 128000,
                    "pricing": 0.0
                },
                {
                    "name": "qwen2.5:7b",
                    "model_type": "chat",
                    "context_window": 128000,
                    "pricing": 0.0
                }
            ]
        }
    ]
    
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

