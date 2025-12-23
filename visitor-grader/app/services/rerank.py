"""Reranking service using cross-encoder model."""
from typing import List, Dict

try:
    from sentence_transformers import CrossEncoder
except ImportError:
    CrossEncoder = None

from app.config.settings import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class RerankService:
    """
    Reranking service using jina-reranker-v2-base-multilingual.
    
    Cross-encoder reranker for improving retrieval quality by scoring
    query-document pairs directly.
    """
    
    def __init__(self):
        self._model = None
    
    def load_model(self) -> None:
        """Load reranking model."""
        if self._model is not None:
            return
        
        if CrossEncoder is None:
            raise RuntimeError(
                "sentence-transformers is required for reranking. "
                "Install it or provide a custom rerank implementation."
            )
        
        logger.info(
            "Loading reranking model",
            extra={"model": settings.RERANK_MODEL}
        )
        
        try:
            self._model = CrossEncoder(
                settings.RERANK_MODEL,
                max_length=512,
                device=settings.EMBEDDING_DEVICE
            )
            logger.info("Reranking model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load reranking model: {e}", exc_info=True)
            raise
    
    def rerank(
        self,
        query: str,
        documents: List[str],
        top_k: int = None
    ) -> List[Dict]:
        """
        Rerank documents based on relevance to query.
        
        Args:
            query: Query text
            documents: List of document texts
            top_k: Number of top results to return (default: all)
            
        Returns:
            List of dicts with {index, score, text} sorted by score descending
        """
        if self._model is None:
            self.load_model()
        
        if not documents:
            return []
        
        top_k = top_k or len(documents)
        
        try:
            pairs = [(query, doc) for doc in documents]
            scores = self._model.predict(pairs, show_progress_bar=False)
            
            if isinstance(scores, float):
                scores = [scores]
            
            results = [
                {
                    "index": idx,
                    "score": float(score),
                    "text": documents[idx]
                }
                for idx, score in enumerate(scores)
            ]
            
            results.sort(key=lambda x: x["score"], reverse=True)
            results = results[:top_k]
            
            logger.debug(
                f"Reranked {len(documents)} documents, returning top {len(results)}",
                extra={"query_len": len(query), "doc_count": len(documents), "top_k": top_k}
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to rerank documents: {e}", exc_info=True)
            raise
    
    def rerank_results(
        self,
        query: str,
        retrieval_results: List[Dict],
        top_k: int = None,
        content_field: str = "content"
    ) -> List[Dict]:
        """
        Rerank retrieval results (with metadata).
        
        Args:
            query: Query text
            retrieval_results: List of result dicts from retrieval
            top_k: Number of top results to return
            content_field: Field name containing document text
            
        Returns:
            Reranked results with updated scores
        """
        if not retrieval_results:
            return []
        
        documents = [result[content_field] for result in retrieval_results]
        
        reranked = self.rerank(query, documents, top_k)
        reranked_results = []
        for rerank_item in reranked:
            original_result = retrieval_results[rerank_item["index"]].copy()
            original_result["rerank_score"] = rerank_item["score"]
            original_result["original_score"] = original_result.get("score", 0)
            reranked_results.append(original_result)
        
        return reranked_results


rerank_service = RerankService()
