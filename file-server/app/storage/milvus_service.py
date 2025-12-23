from typing import Optional, List, Dict, Any
from pymilvus import MilvusClient, DataType, CollectionSchema, FieldSchema
import json
import asyncio

from app.config.settings import settings
from app.utils.logging import get_logger
from app.utils.datetime_utils import now
from pymilvus import AnnSearchRequest, RRFRanker
from app.processors.embedding import embedding_service

logger = get_logger(__name__)


class MilvusService:
    """
    Milvus 2.6+ vector database service for managing bot collections.
    Uses modern MilvusClient API with support for:
    - Dynamic schema
    - JSON metadata
    - Vector similarity search
    - Bulk operations
    - Web URL tracking for crawled data
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
    
    def create_collection(self, collection_name: str) -> bool:
        """
        Create a new collection for bot's knowledge base with hybrid search support.
        
        Schema includes:
        - id: Auto-generated primary key
        - vector: Dense embeddings (configured dim)
        - text: Chunk content
        - document_id: Reference to document
        - web_url: Source URL (for crawled data)
        - chunk_index: Position in document
        - metadata: Flexible JSON metadata
        - created_at: Timestamp
        
        Args:
            collection_name: Name of collection (derived from bot_key)
            
        Returns:
            True if created successfully
        """
        self.connect()
        
        try:
            if self.client.has_collection(collection_name):
                logger.warning(f"Collection {collection_name} already exists")
                self.client.load_collection(collection_name)
                return True
            
            fields = [
                FieldSchema(
                    name="id",
                    dtype=DataType.INT64,
                    is_primary=True,
                    auto_id=True
                ),
                FieldSchema(
                    name="vector",
                    dtype=DataType.FLOAT_VECTOR,
                    dim=self.dimension
                ),

                FieldSchema(
                    name="text",
                    dtype=DataType.VARCHAR,
                    max_length=65535
                ),
                FieldSchema(
                    name="document_id",
                    dtype=DataType.VARCHAR,
                    max_length=255
                ),
                FieldSchema(
                    name="web_url",
                    dtype=DataType.VARCHAR,
                    max_length=1000
                ),
                FieldSchema(
                    name="chunk_index",
                    dtype=DataType.INT64
                ),
                FieldSchema(
                    name="metadata",
                    dtype=DataType.JSON
                ),
                FieldSchema(
                    name="created_at",
                    dtype=DataType.INT64
                )
            ]
            
            schema = CollectionSchema(
                fields=fields,
                description=f"Knowledge base for bot: {collection_name}",
                enable_dynamic_field=True 
            )
            
            self.client.create_collection(
                collection_name=collection_name,
                schema=schema
            )
            
            index_params = self.client.prepare_index_params()
            
            index_params.add_index(
                field_name="vector",
                index_type="HNSW",
                metric_type="COSINE",
                params={"M": 16, "efConstruction": 200}
            )
            

            
            self.client.create_index(
                collection_name=collection_name,
                index_params=index_params,
                sync=True  
            )
            
            self.client.load_collection(collection_name)
            
            logger.info(f"Created Milvus collection: {collection_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create collection {collection_name}: {e}")
            raise
    
    def delete_collection(self, collection_name: str) -> bool:
        """
        Delete a collection and all its data.
        
        Args:
            collection_name: Name of collection to delete
            
        Returns:
            True if deleted successfully
        """
        self.connect()
        
        try:
            if self.client.has_collection(collection_name):
                self.client.drop_collection(collection_name)
                logger.info(f"Deleted Milvus collection: {collection_name}")
                return True
            else:
                logger.warning(f"Collection {collection_name} does not exist")
                return False
                
        except Exception as e:
            logger.error(f"Failed to delete collection {collection_name}: {e}")
            raise
    
    def collection_exists(self, collection_name: str) -> bool:
        """
        Check if collection exists.
        
        Args:
            collection_name: Name of collection
            
        Returns:
            True if exists
        """
        self.connect()
        return self.client.has_collection(collection_name)
    
    def get_collection_stats(self, collection_name: str) -> dict:
        """
        Get collection statistics.
        
        Args:
            collection_name: Name of collection
            
        Returns:
            Dictionary with collection stats
        """
        self.connect()
        
        try:
            if not self.client.has_collection(collection_name):
                return {}
            
            stats = self.client.describe_collection(collection_name)
            
            num_entities = self.client.query(
                collection_name=collection_name,
                filter="",
                output_fields=["count(*)"]
            )
            
            return {
                "name": collection_name,
                "num_entities": len(num_entities) if num_entities else 0,
                "schema": stats,
            }
            
        except Exception as e:
            logger.error(f"Failed to get stats for {collection_name}: {e}")
            return {}
    
    async def insert_documents(
        self,
        collection_name: str,
        documents: List[Dict[str, Any]],
        embeddings: Optional[List[List[float]]] = None
    ) -> bool:
        """
        Insert documents with dense and sparse embeddings into collection (hybrid search).
        Auto-generates embeddings using BGE M3 if not provided.
        Auto-creates collection if it doesn't exist.
        
        Args:
            collection_name: Collection name
            documents: List of document dictionaries with fields:
                - text: Chunk content
                - document_id: Document UUID
                - web_url: Source URL (optional, for crawled data)
                - chunk_index: Position in document
                - metadata: Additional metadata
            embeddings: Optional list of embedding vectors (auto-generated if None)
            
        Returns:
            True if successful
        """
        self.connect()
        
        try:
            if not self.client.has_collection(collection_name):
                logger.info(f"Collection {collection_name} does not exist, creating it...")
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self.create_collection, collection_name)
                logger.info(f"Collection {collection_name} created successfully")
            
            if embeddings is None:
                logger.info(f"Auto-generating embeddings for {len(documents)} documents")
                texts = [doc.get("text", "") for doc in documents]
                
                loop = asyncio.get_event_loop()
                embedding_result = await loop.run_in_executor(
                    None,
                    embedding_service.encode_documents,
                    texts
                )
                dense_embeddings = embedding_result["dense_vectors"].tolist()
                logger.info(f"Generated {len(dense_embeddings)} dense embeddings")
            else:
                dense_embeddings = embeddings
                texts = [doc.get("text", "") for doc in documents]
            
            insert_data = []
            current_time = int(now().timestamp() * 1000)
            
            for i, doc in enumerate(documents):
                insert_data.append({
                    "vector": dense_embeddings[i],
                    "text": str(doc.get("text", "")),
                    "document_id": str(doc.get("document_id", "unknown")),
                    "web_url": str(doc.get("web_url", "")),
                    "chunk_index": int(doc.get("chunk_index", i)),
                    "metadata": self._sanitize_metadata(doc.get("metadata", {})),
                    "created_at": current_time
                })
            
            self.client.insert(
                collection_name=collection_name,
                data=insert_data
            )
            
            logger.info(f"Inserted {len(insert_data)} documents into {collection_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to insert documents into {collection_name}: {e}")
            raise
    
    async def search_documents(
        self,
        collection_name: str,
        query_text: Optional[str] = None,
        query_vector: Optional[List[float]] = None,
        top_k: int = 10,
        filter_expr: Optional[str] = None,
        output_fields: Optional[List[str]] = None,
        hybrid_mode: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Search for similar documents using dense vectors.
        Auto-generates query embeddings using SentenceTransformer if query_text provided.
        
        Args:
            collection_name: Collection name
            query_text: Query text (will auto-generate dense embeddings)
            query_vector: Query dense embedding vector (used if query_text is None)
            top_k: Number of results to return
            filter_expr: Optional filter expression (e.g., 'document_id == "abc"')
            output_fields: Fields to return (default: all)
            hybrid_mode: Deprecated, ignored (always dense only)
            
        Returns:
            List of search results with scores
        """
        self.connect()
        
        try:
            if not self.client.has_collection(collection_name):
                logger.warning(f"Collection {collection_name} does not exist")
                return []
            
            if output_fields is None:
                output_fields = ["text", "document_id", "web_url", "chunk_index", "metadata", "created_at"]
            
            if query_text is not None:
                logger.info("Auto-generating query embedding")
                
                loop = asyncio.get_event_loop()
                embedding_result = await loop.run_in_executor(
                    None,
                    embedding_service.encode_documents,
                    [query_text]
                )
                query_dense = embedding_result["dense_vectors"][0].tolist()
                logger.info("Generated dense query embedding")
            elif query_vector is not None:
                query_dense = query_vector
            else:
                raise ValueError("Either query_text or query_vector must be provided")
            
            search_results = self.client.search(
                collection_name=collection_name,
                data=[query_dense],
                anns_field="vector",
                param={
                    "metric_type": "COSINE",
                    "params": {"ef": 200}
                },
                limit=top_k,
                output_fields=output_fields,
                filter=filter_expr
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
                    
                    results.append({
                        "id": entity.get("document_id", "unknown"),
                        "content": entity.get("text", ""),
                        "score": hit.get("distance", 0.0),
                        "metadata": metadata,
                        "web_url": entity.get("web_url", ""),
                        "chunk_index": entity.get("chunk_index", 0),
                        "created_at": entity.get("created_at")
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to search documents in {collection_name}: {e}")
            return []
    
    def delete_by_document_id(
        self,
        collection_name: str,
        document_id: str
    ) -> bool:
        """
        Delete all chunks for a specific document.
        
        Args:
            collection_name: Collection name
            document_id: Document UUID
            
        Returns:
            True if successful
        """
        self.connect()
        
        try:
            if not self.client.has_collection(collection_name):
                logger.warning(f"Collection {collection_name} does not exist")
                return False
            
            filter_expr = f'document_id == "{document_id}"'
            
            self.client.delete(
                collection_name=collection_name,
                filter=filter_expr
            )
            
            logger.info(f"Deleted document {document_id} from {collection_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete document {document_id}: {e}")
            raise
    
    def flush_collection(self, collection_name: str) -> bool:
        """
        Flush collection to persist all in-memory data and optimize indexes.
        Call after bulk deletions or insertions.
        
        Args:
            collection_name: Collection name
            
        Returns:
            True if successful
        """
        self.connect()
        
        try:
            if not self.client.has_collection(collection_name):
                logger.warning(f"Collection {collection_name} does not exist")
                return False
            
            self.client.flush(collection_name)
            logger.info(f"Flushed collection {collection_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to flush collection {collection_name}: {e}")
            raise
    
    def _sanitize_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert non-JSON serializable objects to strings in metadata.
        
        Args:
            metadata: Raw metadata dictionary
            
        Returns:
            Sanitized metadata dictionary
        """
        sanitized = {}
        for key, value in metadata.items():
            if hasattr(value, '__str__') and not isinstance(value, (str, int, float, bool, list, dict, type(None))):
                sanitized[key] = str(value)
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_metadata(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    str(item) if hasattr(item, '__str__') and not isinstance(item, (str, int, float, bool, dict, type(None))) 
                    else item 
                    for item in value
                ]
            else:
                sanitized[key] = value
        return sanitized


# Global instance
milvus_service = MilvusService()

