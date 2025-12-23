"""
Cache key generators for visitor-grader service.
Centralized key management for Redis cache and Pub/Sub channels.
"""


class CacheKeys:
    """
    Cache key generators following consistent naming patterns.
    Shared with backend for Pub/Sub communication.
    """
    
    @staticmethod
    def bot_config(bot_id: str) -> str:
        """
        Cache key for worker's bot configuration (full metadata + encrypted keys).
        
        SHARED between chat-worker and visitor-grader (same format).
        Different from backend's bot:{id}:config (ProviderConfig model).
        """
        return f"bot:{bot_id}:worker_config"
    
    # ===== SHARED KEYS (must match backend) =====
    @staticmethod
    def task_progress_channel(task_id: str) -> str:
        """
        Pub/Sub channel for task progress updates (grading/assessment) via SSE.
        
        CRITICAL: Must match backend/app/cache/keys.py
        """
        return f"progress:{task_id}"
    
    @staticmethod
    def task_state(task_id: str) -> str:
        """
        Cache key for task state tracking.
        
        CRITICAL: Must match backend/app/cache/keys.py
        """
        return f"task:state:{task_id}"
    
    @staticmethod
    def bot_pattern(bot_id: str = "") -> str:
        """Pattern for bot-related cache keys."""
        if bot_id:
            return f"bot:{bot_id}:*"
        return "bot:*"
    
    # ===== GRADER-SPECIFIC KEYS =====
    
    @staticmethod
    def prompt_cache(prompt_name: str, language: str) -> str:
        """Cache key for loaded prompt with language. Grader-specific only."""
        return f"grader:prompt:{prompt_name}:{language}"
