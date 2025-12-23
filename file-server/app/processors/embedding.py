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
    
    def __init__(self):
        self.model = None
        self.model_name = settings.EMBEDDING_MODEL_NAME
        self.dimension = settings.MILVUS_VECTOR_DIM
        self._load_model()
    
    def _load_model(self) -> None:
        """Load SentenceTransformer model"""
        try:
            self.model = SentenceTransformer(
                self.model_name,
                device=settings.EMBEDDING_DEVICE
            )
            logger.info(f"Model {self.model_name} loaded successfully on {settings.EMBEDDING_DEVICE}")
        except Exception as e:
            logger.error(f"Failed to load model {self.model_name}: {e}")
            raise
    
    def encode_documents(self, texts: List[str], batch_size: int = None) -> Dict[str, Any]:
        """
        
        Note: This is a CPU-intensive blocking operation. 
        Use asyncio.to_thread() when calling from async context.
        
        Args:
            texts: List of document texts to encode
            batch_size: Batch size for encoding (default from settings)
        
        Returns:
            Dict with 'dense_vectors' keys containing embeddings
        """
        if not texts:
            logger.warning("Empty text list provided for encoding")
            return {"dense_vectors": np.array([])}
        
        if batch_size is None:
            batch_size = settings.EMBEDDING_BATCH_SIZE
        
        try:
            logger.info(
                f"Starting encoding: {len(texts)} documents (batch_size={batch_size}, device={settings.EMBEDDING_DEVICE})"
            )
            

            embeddings = self.model.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True 
            )
            
            dense_vectors = embeddings
            
            logger.info(f"Successfully encoded {len(texts)} documents, dense shape: {dense_vectors.shape}")
            return {
                "dense_vectors": dense_vectors
            }
        except Exception as e:
            logger.error(f"Encoding failed: {e}")
            raise
            
        except Exception as e:
            logger.error(f"Failed to encode documents: {e}")
            raise
    
    def encode_queries(self, queries: List[str]) -> Dict[str, Any]:
        """
        Encode queries into dense and sparse vectors (BLOCKING operation)
        
        Note: This is a CPU-intensive blocking operation.
        Use asyncio.to_thread() when calling from async context.
        
        Args:
            queries: List of query texts to encode
        
        Returns:
            Dict with 'dense_vectors' and 'sparse_vectors' keys containing embeddings
        """
        if not queries:
            logger.warning("Empty query list provided for encoding")
            return {"dense_vectors": np.array([]), "sparse_vectors": []}
        
        try:
            logger.info(f"Encoding {len(queries)} queries with BGE M3 (hybrid mode)")
            
            embeddings = self.model.encode(
                queries,
                batch_size=len(queries),
                max_length=512,
                return_dense=True,
                return_sparse=True, 
                return_colbert_vecs=False
            )
            
            dense_vectors = embeddings['dense_vecs']
            sparse_vectors = embeddings['lexical_weights']
            
            logger.info(f"Successfully encoded {len(queries)} queries, dense shape: {dense_vectors.shape}, sparse count: {len(sparse_vectors)}")
            return {
                "dense_vectors": dense_vectors,
                "sparse_vectors": sparse_vectors
            }
            
        except Exception as e:
            logger.error(f"Failed to encode queries: {e}")
            raise
    
    def get_dimension(self) -> int:
        """Get embedding dimension"""
        return self.dimension


embedding_service = EmbeddingService()

