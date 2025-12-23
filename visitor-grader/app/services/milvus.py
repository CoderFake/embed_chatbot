"""Milvus service for temporary conversation collections."""
from typing import List, Dict
from pymilvus import (
    connections,
    Collection,
    CollectionSchema,
    FieldSchema,
    DataType,
    utility
)

from app.config.settings import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class MilvusService:
    """
    Milvus service for creating temporary collections for visitor grading.
    
    Each grading task creates a temporary collection to store conversation embeddings,
    performs retrieval, then deletes the collection.
    """
    
    def __init__(self):
        self._connected = False
    
    def connect(self) -> None:
        """Connect to Milvus."""
        if self._connected:
            return
        
        try:
            connections.connect(
                alias="default",
                host=settings.MILVUS_HOST,
                port=settings.MILVUS_PORT,
                user=settings.MILVUS_USER,
                password=settings.MILVUS_PASSWORD,
            )
            self._connected = True
            logger.info("Connected to Milvus", extra={
                "host": settings.MILVUS_HOST,
                "port": settings.MILVUS_PORT
            })
        except Exception as e:
            logger.error(f"Failed to connect to Milvus: {e}", exc_info=True)
            raise
    
    def disconnect(self) -> None:
        """Disconnect from Milvus."""
        if self._connected:
            connections.disconnect(alias="default")
            self._connected = False
            logger.info("Disconnected from Milvus")
    
    def create_collection(self, collection_name: str) -> Collection:
        if not self._connected:
            self.connect()
        
        if utility.has_collection(collection_name):
            logger.warning(f"Collection {collection_name} already exists, dropping")
            utility.drop_collection(collection_name)
        
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="message_id", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="role", dtype=DataType.VARCHAR, max_length=20),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=5000),
            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=settings.MILVUS_VECTOR_DIM),
            FieldSchema(name="timestamp", dtype=DataType.VARCHAR, max_length=50),
        ]
        
        schema = CollectionSchema(
            fields=fields,
            description=f"Temporary collection for visitor grading: {collection_name}"
        )
        
        collection = Collection(name=collection_name, schema=schema)
        
        index_params = {
            "metric_type": "IP",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 128}
        }
        collection.create_index(field_name="vector", index_params=index_params)
        

        
        logger.info(f"Created Milvus collection: {collection_name}")
        
        return collection
    
    def insert_messages(
        self,
        collection_name: str,
        messages: List[Dict],
        dense_embeddings: List[List[float]]
    ) -> None:
        if not self._connected:
            self.connect()
        
        collection = Collection(collection_name)
        
        data = [
            [msg["id"] for msg in messages],
            [msg["role"] for msg in messages],
            [msg["content"] for msg in messages],
            dense_embeddings,
            [msg["timestamp"] for msg in messages],
        ]
        
        collection.insert(data)
        collection.flush()
        
        logger.info(
            f"Inserted {len(messages)} messages into {collection_name}",
            extra={"collection": collection_name, "count": len(messages)}
        )
    
    def search(
        self,
        collection_name: str,
        query_dense: List[float],
        query_sparse: Dict = None, # Deprecated
        top_k: int = 20,
        output_fields: List[str] = None,
        hybrid_mode: bool = False # Deprecated
    ) -> List[Dict]:
        if not self._connected:
            self.connect()
        
        collection = Collection(collection_name)
        collection.load()
        
        if output_fields is None:
            output_fields = ["message_id", "role", "content", "timestamp"]
        
        search_params = {
            "metric_type": "IP",
            "params": {"nprobe": 10}
        }
        
        results = collection.search(
            data=[query_dense],
            anns_field="vector",
            param=search_params,
            limit=top_k,
            output_fields=output_fields
        )
        
        formatted_results = []
        for hits in results:
            for hit in hits:
                formatted_results.append({
                    "id": hit.id,
                    "score": hit.score,
                    "message_id": hit.entity.get("message_id"),
                    "role": hit.entity.get("role"),
                    "content": hit.entity.get("content"),
                    "timestamp": hit.entity.get("timestamp"),
                })
        
        logger.debug(
            f"Search in {collection_name} returned {len(formatted_results)} results",
            extra={"collection": collection_name, "top_k": top_k}
        )
        
        return formatted_results
    
    def delete_collection(self, collection_name: str) -> None:
        """
        Delete a collection.
        
        Args:
            collection_name: Collection name to delete
        """
        if not self._connected:
            self.connect()
        
        if utility.has_collection(collection_name):
            utility.drop_collection(collection_name)
            logger.info(f"Deleted Milvus collection: {collection_name}")
        else:
            logger.warning(f"Collection {collection_name} does not exist")


# Global instance
milvus_service = MilvusService()
