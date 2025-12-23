"""Milvus service for chat worker with full vector search capabilities."""
from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional

from pymilvus import MilvusClient

from app.config.settings import settings
from app.core.keys import ChatKeys
from app.core.service_manager import service_manager
from app.utils.logging import get_logger

logger = get_logger(__name__)


class MilvusService:
    """
    Milvus service for vector search operations.
    
    Features:
    - BGE-M3 embeddings (512 dimensions)
    - Hybrid search (dense + sparse vectors)
    - Bot-specific collections
    - Automatic schema management
    """

    def __init__(self):
        self.uri = f"http://{settings.MILVUS_HOST}:{settings.MILVUS_PORT}"
        self.dimension = settings.MILVUS_VECTOR_DIM
        self.client: Optional[MilvusClient] = None
        self._connected = False

    def connect(self):
        """Connect to Milvus server using MilvusClient."""
        if not self._connected:
            try:
                self.client = MilvusClient(uri=self.uri)
                self._connected = True
                logger.info(f"Connected to Milvus at {self.uri}")
            except Exception as e:
                logger.error(f"Failed to connect to Milvus: {e}")
                raise

    def disconnect(self):
        """Disconnect from Milvus server."""
        if self._connected and self.client:
            self.client.close()
            self._connected = False
            logger.info("Disconnected from Milvus")

    def collection_exists(self, collection_name: str) -> bool:
        """Check if collection exists."""
        self.connect()
        return self.client.has_collection(collection_name)

    async def search_documents(
        self,
        collection_name: str,
        query_text: Optional[str] = None,
        query_vector: Optional[List[float]] = None,
        top_k: int = 10,
        filter_expr: Optional[str] = None,
        output_fields: Optional[List[str]] = None,
        hybrid_mode: bool = True,
    ) -> List[Dict[str, Any]]:
        self.connect()

        try:
            if not await asyncio.to_thread(self.client.has_collection, collection_name):
                logger.warning(f"Collection {collection_name} does not exist")
                return []

            if output_fields is None:
                output_fields = ["text", "document_id", "web_url", "chunk_index", "metadata", "created_at"]

            if query_text is not None:
                from app.services.embedding import embedding_service
                
                embedding_result = await embedding_service.encode_queries([query_text])
                query_dense = embedding_result["dense_vectors"][0].tolist()
            elif query_vector is not None:
                query_dense = query_vector
            else:
                raise ValueError("Either query_text or query_vector must be provided")

            search_results = await asyncio.to_thread(
                self.client.search,
                collection_name=collection_name,
                data=[query_dense],
                anns_field="vector",
                limit=top_k,
                search_params={"metric_type": "COSINE", "params": {"ef": 200}},
                output_fields=output_fields,
                filter=filter_expr,
            )

            results = []
            for hits in search_results:
                for hit in hits:
                    entity = hit.get("entity", {})
                    metadata = entity.get("metadata", {})

                    if isinstance(metadata, str):
                        try:
                            metadata = json.loads(metadata)
                        except (json.JSONDecodeError, TypeError):
                            metadata = {}

                    results.append(
                        {
                            "id": entity.get("document_id", "unknown"),
                            "content": entity.get("text", ""),
                            "web_url": entity.get("web_url", ""),
                            "chunk_index": entity.get("chunk_index", 0),
                            "score": float(hit.get("distance", 0.0)),
                            "metadata": metadata,
                        }
                    )

            return results

        except Exception as e:
            logger.error(f"Search failed in {collection_name}: {e}")
            return []

    def _cache_key(
        self, collection_name: str, query_text: str, top_k: int, filter_expr: Optional[str]
    ) -> str:
        """Generate cache key for search results."""
        return ChatKeys.retrieval_cache(collection_name, query_text, top_k, filter_expr)

    async def _get_cache(self, key: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached search results from Redis."""
        redis = service_manager.get_redis()
        data = await redis.get(key)
        if not data:
            return None
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return None

    async def _set_cache(self, key: str, results: List[Dict[str, Any]]) -> None:
        """Cache search results in Redis (5 minutes TTL)."""
        redis = service_manager.get_redis()
        await redis.setex(key, 300, json.dumps(results))

    async def search_for_chat(
        self,
        *,
        collection_name: str,
        query_text: str,
        top_k: int = 20,
        use_cache: bool = True,
        filter_expr: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search with optional caching (optimized for chat workflow).

        Args:
            collection_name: Collection name
            query_text: User query
            top_k: Number of results
            use_cache: Whether to use Redis cache
            filter_expr: Optional Milvus filter expression

        Returns:
            List of search results
        """
        cache_key = self._cache_key(collection_name, query_text, top_k, filter_expr)

        if use_cache:
            cached = await self._get_cache(cache_key)
            if cached is not None:
                logger.debug("Milvus cache hit for query: %s", query_text[:50])
                return cached

        try:
            results = await asyncio.wait_for(
                self.search_documents(
                    collection_name=collection_name,
                    query_text=query_text,
                    top_k=top_k,
                    filter_expr=filter_expr,
                ),
                timeout=5.0,
            )
        except asyncio.TimeoutError:
            logger.error("Milvus search timeout for query: %s", query_text[:50])
            results = []
        except Exception as e:
            logger.error("Milvus search failed: %s", e, exc_info=True)
            results = []

        if use_cache and results:
            await self._set_cache(cache_key, results)

        return results


milvus_service = MilvusService()
