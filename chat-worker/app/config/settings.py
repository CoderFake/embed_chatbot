"""Settings for chat worker service."""
from functools import lru_cache
from typing import List, Optional

from pydantic import AnyUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the chat worker."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "Chatbot Worker"
    APP_VERSION: str = "1.0.0"
    ENV: str = "dev"  
    DEBUG: bool = False
    TIMEZONE: str = "UTC"
    SECRET_KEY: str
    ENCRYPTION_SALT: str = "chatbot_salt_key"

    DEFAULT_LANGUAGE: str = "vi"
    SUPPORTED_LANGUAGES: str = "vi,en,ja,kr"
    STREAMING_CHUNK_SIZE: int = 5

    EMBEDDING_MODEL_NAME: str = "intfloat/multilingual-e5-base"

    RETRIEVAL_STAGE1_TOP_K: int = 20 
    RERANKER_STAGE1_TOP_N: int = 10    
    
    RETRIEVAL_STAGE2_TOP_K: int = 30 
    RERANKER_STAGE2_TOP_N: int = 15 
    
    RETRIEVAL_CONFIDENCE_THRESHOLD: float = 0.7

    RETRIEVAL_TOP_K: int = 20
    LANGUAGE_DETECTION_THRESHOLD: float = 0.7 
    
    # Reranker settings
    RERANK_MODEL: str = "BAAI/bge-reranker-base"
    RERANKER_MODEL: Optional[str] = None
    RERANKER_BATCH_SIZE: int = 16
    RERANKER_TOP_N: int = 5
    
    # Rerank Mode: True = 2-stage (accurate), False = 1-stage (faster)
    RERANK_MODE: bool = False

    EMBEDDING_DEVICE: str = "cpu"
    
    # === Milvus Configuration ===
    MILVUS_HOST: str = "milvus"
    MILVUS_PORT: int = 19530
    MILVUS_USER: str = ""
    MILVUS_PASSWORD: str = ""
    MILVUS_VECTOR_DIM: int = 768
    
    # === Visitor information fields ===
    VISITOR_INFO_FIELDS: str = "name,email,phone,address"
    
    # === Reflection & Quality Control ===
    ENABLE_CONTEXT_RELEVANCE_CHECK: bool = False 
    CONTEXT_RELEVANCE_THRESHOLD: int = 1
    ENABLE_GROUNDEDNESS_CHECK: bool = False 
    GROUNDEDNESS_THRESHOLD: int = 1  
    GROUNDEDNESS_MAX_LOOPS: int = 2 
    
    # === LLM Capabilities ===
    JSON_MODE_SUPPORTED_MODELS: str = "gpt-4,gpt-3.5-turbo,gpt-4o" 
    
    # === Server configuration ===
    PORT: int = 8001

    # === External services ===
    BACKEND_API_URL: str = "http://backend:8000"
    BACKEND_WEBHOOK_SECRET: str = "change-this-webhook-secret"
    DATABASE_URL: Optional[str] = None
    REDIS_URL: Optional[str] = None
    RABBITMQ_URL: str = "amqp://guest:guest@rabbitmq:5672/"
    CHAT_QUEUE_NAME: str = "chat_processing_queue"
    CHAT_QUEUE_MAX_LENGTH: int = 1000
    MAX_CONCURRENT_CHAT_TASKS: int = 10

    POSTGRES_HOST: str = Field(default="postgres")
    POSTGRES_PORT: int = Field(default=5432)
    POSTGRES_USER: str = Field(default="postgres")
    POSTGRES_PASSWORD: str = Field(default="postgres")
    POSTGRES_DB: str = Field(default="chatbot_db")

    def supported_languages_list(self) -> List[str]:
        """Return supported languages as a list."""
        return [lang.strip() for lang in self.SUPPORTED_LANGUAGES.split(",") if lang.strip()]
    
    def visitor_info_fields_list(self) -> List[str]:
        """Return visitor info fields as a list."""
        return [field.strip() for field in self.VISITOR_INFO_FIELDS.split(",") if field.strip()]
    
    def json_mode_supported_models_list(self) -> List[str]:
        """Return list of models that support JSON mode."""
        return [model.strip() for model in self.JSON_MODE_SUPPORTED_MODELS.split(",") if model.strip()]
    
    def __init__(self, **kwargs):
        """Initialize settings and auto-configure DEBUG based on ENV if not explicitly set."""
        super().__init__(**kwargs)
        
        if "DEBUG" not in kwargs:
            self.DEBUG = self.ENV == "dev"


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()


settings = get_settings()
