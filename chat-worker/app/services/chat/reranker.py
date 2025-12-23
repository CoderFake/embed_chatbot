"""Reranker service using cross-encoder."""
from __future__ import annotations

import asyncio
from typing import Dict, List

try:
    from sentence_transformers import CrossEncoder
except ImportError: 
    CrossEncoder = None

from app.config.settings import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class RerankerService:
    """Rerank retrieved chunks using a cross-encoder model."""

    def __init__(self) -> None:
        model_name = getattr(settings, "RERANKER_MODEL", None)
        self.model_name = model_name or settings.RERANK_MODEL
        self.batch_size = settings.RERANKER_BATCH_SIZE
        self.top_n = settings.RERANKER_TOP_N
        self._model: CrossEncoder | None = None

    async def _ensure_model(self) -> CrossEncoder:
        if CrossEncoder is None:
            raise RuntimeError(
                "sentence-transformers is required for reranking. "
                "Install it or provide a custom rerank implementation."
            )

        if self._model is None:
            logger.info("Loading reranker model: %s", self.model_name)
            self._model = await asyncio.to_thread(
                CrossEncoder,
                self.model_name,
                max_length=512,
                device=settings.EMBEDDING_DEVICE,
            )
            logger.info("Reranker model loaded successfully")
        return self._model
    
    async def load_model(self) -> None:
        """Eagerly load the model at startup to avoid first-request delay."""
        logger.info("Pre-loading reranker model")
        await self._ensure_model()
        logger.info("Reranker model pre-loaded and cached")

    async def rerank(self, query: str, chunks: List[Dict], top_n: int | None = None) -> List[Dict]:
        if not chunks:
            return []

        top_n = top_n or self.top_n
        model = await self._ensure_model()

        pairs = [(query, chunk.get("content", "")) for chunk in chunks]
        
        try:
            scores = await asyncio.wait_for(
                asyncio.to_thread(
                    model.predict,
                    pairs,
                    batch_size=self.batch_size,
                    show_progress_bar=False,
                ),
                timeout=15.0 
            )
        except asyncio.TimeoutError:
            logger.error(f"Rerank timeout after 15s for {len(chunks)} chunks")
            sorted_chunks = sorted(chunks, key=lambda x: x.get("score", 0.0), reverse=True)
            return sorted_chunks[:top_n]

        reranked: List[Dict] = []
        for chunk, score in zip(chunks, scores):
            updated = chunk.copy()
            updated["rerank_score"] = float(score)
            updated["original_score"] = float(chunk.get("score", 0.0))
            reranked.append(updated)

        reranked.sort(key=lambda item: item["rerank_score"], reverse=True)
        result = reranked[:top_n]

        if result:
            logger.info(
                "Reranked chunks",
                extra={"count": len(chunks), "top": len(result), "top_score": result[0]["rerank_score"]},
            )
        else:
            logger.info("Reranked chunks", extra={"count": len(chunks), "top": 0})

        return result


reranker_service = RerankerService()


async def warmup() -> None:
    """Pre-load the reranker model at startup."""
    await reranker_service.load_model()
