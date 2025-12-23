"""
Redis key generators for file-server.
Centralized key management to maintain consistency with backend.
"""


class RedisKeys:
    """
    Redis key generators for file-server operations.
    
    Must be consistent with backend CacheKeys for shared keys.
    """
    
    @staticmethod
    def task_state(task_id: str) -> str:
        """Cache key for task state persistence (SSE resume support)."""
        return f"task:state:{task_id}"
    
    @staticmethod
    def task_progress_channel(task_id: str) -> str:
        """Pub/Sub channel for task progress updates (SSE)."""
        return f"progress:{task_id}"
    
    @staticmethod
    def processing_lock(document_id: str) -> str:
        """Lock key to prevent duplicate file processing."""
        return f"processing:lock:{document_id}"
    
    @staticmethod
    def crawl_cache(url: str) -> str:
        """Cache key for crawled page content."""
        return f"crawl:cache:{url}"
    
    @staticmethod
    def embedding_cache(text_hash: str) -> str:
        """Cache key for embedding vectors."""
        return f"embedding:cache:{text_hash}"
    
    @staticmethod
    def crawl_stop(bot_id: str) -> str:
        """Key to signal cancellation of crawl tasks for a bot."""
        return f"crawl:stop:{bot_id}"

