"""
Cache key generators and naming conventions for chat worker.
Centralized key management for Redis cache.
"""


class ChatKeys:
    """
    Cache key generators for chat worker operations.
    """

    @staticmethod
    def task_state(task_id: str) -> str:
        """Cache key for chat task state"""
        return f"task:state:{task_id}"

    @staticmethod
    def task_progress_channel(task_id: str) -> str:
        """PubSub channel for task progress updates"""
        return f"progress:{task_id}"
    
    @staticmethod
    def task_cancel_channel(session_id: str) -> str:
        """PubSub channel for task cancellation signals"""
        return f"chat:cancel:{session_id}"

    @staticmethod
    def bot_config(bot_id: str) -> str:
        """
        Cache key for worker's bot configuration.
        """
        return f"bot:{bot_id}:worker_config"

    @staticmethod
    def provider_config(provider_slug: str, bot_id: str) -> str:
        """Cache key for provider configuration."""
        return f"provider:{provider_slug}:bot:{bot_id}"

    @staticmethod
    def key_state(bot_id: str, key_index: int) -> str:
        """Cache key for API key state (rate limit tracking)."""
        return f"key_state:{bot_id}:{key_index}"

    @staticmethod
    def current_key_index(bot_id: str) -> str:
        """Cache key for current key index (round-robin)."""
        return f"current_key_index:{bot_id}"

    @staticmethod
    def key_usage(bot_id: str, key_index: int) -> str:
        """Cache key for API key usage counter."""
        return f"key_usage:{bot_id}:{key_index}"

    @staticmethod
    def retrieval_cache(collection: str, query: str, top_k: int, filter_expr: str | None = None) -> str:
        """Cache key for retrieval results."""
        filter_part = f":filter:{filter_expr}" if filter_expr else ""
        return f"chat:retrieval:{collection}:{query}:{top_k}{filter_part}"

    # Queue keys
    @staticmethod
    def chat_queue() -> str:
        """Chat processing queue name."""
        return "chat_processing_queue"

    # Pattern keys
    @staticmethod
    def task_pattern() -> str:
        """Pattern for all task-related keys"""
        return "task:state:*"

    @staticmethod
    def bot_config_pattern() -> str:
        """Pattern for all bot config keys"""
        return "bot:*:config"

    @staticmethod
    def retrieval_pattern() -> str:
        """Pattern for all retrieval cache keys"""
        return "chat:retrieval:*"

    @staticmethod
    def key_state_pattern(bot_id: str) -> str:
        """Pattern for all key state keys for a bot."""
        return f"key_state:{bot_id}:*"
