"""
Embedding service using SentenceTransformers for generating dense vectors
"""
from typing import List, Dict, Any
import numpy as np
from sentence_transformers import SentenceTransformer

from app.config.settings import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class EmbeddingService:
    """
    Embedding Service for generating dense vectors using SentenceTransformers.
    
    Features:
    - Dense vector embeddings (configured dimension)
    - Batch processing for efficiency
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self.model = None
        self.model_name = settings.EMBEDDING_MODEL_NAME
        self.dimension = settings.MILVUS_VECTOR_DIM
        self._initialized = True
    
    def _load_model(self) -> None:
        """Load SentenceTransformer model"""
        if self.model is not None:
            logger.debug("Model already loaded, using cached instance")
            return
            
        try:
            logger.info(f"Loading model: {self.model_name}")
            self.model = SentenceTransformer(
                self.model_name,
                device=settings.EMBEDDING_DEVICE
            )
            logger.info(f"Model {self.model_name} loaded successfully on {settings.EMBEDDING_DEVICE}")
        except Exception as e:
            logger.error(f"Failed to load model {self.model_name}: {e}")
            raise
    
    def ensure_loaded(self) -> None:
        """Ensure model is loaded (for warmup)"""
        self._load_model()
    
    async def encode_queries(self, queries: List[str]) -> Dict[str, Any]:
        """
        Encode queries into dense vectors.
        
        Args:
            queries: List of query texts to encode
        
        Returns:
            Dict with 'dense_vectors' key containing embeddings
        """
        if not queries:
            logger.warning("Empty query list provided for encoding")
            return {"dense_vectors": np.array([])}
        
        self._load_model()
        
        try:
            logger.debug(f"Encoding {len(queries)} queries")
            
            embeddings = self.model.encode(
                queries,
                batch_size=len(queries),
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True
            )
            
            dense_vectors = embeddings
            
            logger.info(f"Successfully encoded {len(queries)} queries, dense shape: {dense_vectors.shape}")
            return {
                "dense_vectors": dense_vectors
            }
            
        except Exception as e:
            logger.error(f"Failed to encode queries: {e}")
            raise
    
    def get_dimension(self) -> int:
        """Get embedding dimension"""
        return self.dimension


# Singleton instance
embedding_service = EmbeddingService()


async def warmup() -> None:
    """Pre-load the embedding model at startup."""
    logger.info("Pre-loading embedding model")
    embedding_service.ensure_loaded()
    logger.info("Embedding model pre-loaded and cached")
