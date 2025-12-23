"""Embedding service using SentenceTransformers."""
from typing import List, Union
from sentence_transformers import SentenceTransformer

from app.config.settings import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class EmbeddingService:
    """
    Embedding service using SentenceTransformers model.
    
    Supports:
    - Dense retrieval (semantic similarity)
    """
    
    def __init__(self):
        self._model = None
    
    def load_model(self) -> None:
        """Load embedding model."""
        if self._model is not None:
            return
        
        logger.info(
            "Loading embedding model",
            extra={"model": settings.EMBEDDING_MODEL_NAME}
        )
        
        try:
            self._model = SentenceTransformer(
                settings.EMBEDDING_MODEL_NAME,
                device=settings.EMBEDDING_DEVICE
            )
            self._model.max_seq_length = settings.MAX_SEQ_LENGTH
            logger.info("Embedding model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}", exc_info=True)
            raise
    
    def embed(self, texts: Union[str, List[str]]) -> dict:
        """
        Embed text(s) into dense vectors.
        
        Args:
            texts: Single text or list of texts
            
        Returns:
            Dict with 'dense_vecs' key
        """
        if self._model is None:
            self.load_model()
        
        is_single = isinstance(texts, str)
        if is_single:
            texts = [texts]
        
        try:
            dense_vecs = self._model.encode(
                texts,
                batch_size=settings.EMBEDDING_BATCH_SIZE,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True
            )
         
            if is_single:
                return {
                    'dense_vecs': dense_vecs[0]
                }
            else:
                return {
                    'dense_vecs': dense_vecs.tolist()
                }
            
        except Exception as e:
            logger.error(f"Failed to embed texts: {e}", exc_info=True)
            raise
    
    def embed_batch(
        self,
        texts: List[str],
        batch_size: int = None
    ) -> dict:
        """
        Embed a batch of texts with custom batch size.
        
        Args:
            texts: List of texts to embed
            batch_size: Batch size (default from settings)
            
        Returns:
            Dict with 'dense_vecs' key
        """
        if self._model is None:
            self.load_model()
        
        batch_size = batch_size or settings.EMBEDDING_BATCH_SIZE
        
        try:
            dense_vecs = self._model.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True
            )
            
            logger.info(
                f"Embedded {len(texts)} texts in batches",
                extra={"count": len(texts), "batch_size": batch_size}
            )
            
            return {
                'dense_vecs': dense_vecs.tolist()
            }
            
        except Exception as e:
            logger.error(f"Failed to embed batch: {e}", exc_info=True)
            raise


# Global instance
embedding_service = EmbeddingService()
