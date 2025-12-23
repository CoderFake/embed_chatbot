"""
Cache key generators and naming conventions.
Centralized key management for Redis cache.
"""


class CacheKeys:
    """
    Cache key generators following consistent naming patterns.
    """
    
    @staticmethod
    def user(user_id: str) -> str:
        """Cache key for single user."""
        return f"user:{user_id}"
    
    @staticmethod
    def bot(bot_id: str) -> str:
        """Cache key for single bot."""
        return f"bot:{bot_id}"
    
    @staticmethod
    def document(document_id: str) -> str:
        """Cache key for single document."""
        return f"document:{document_id}"
    
    @staticmethod
    def visitor(visitor_id: str) -> str:
        """Cache key for single visitor."""
        return f"visitor:{visitor_id}"
    
    @staticmethod
    def session(session_id: str) -> str:
        """Cache key for chat session."""
        return f"session:{session_id}"
    
    @staticmethod
    def provider(provider_id: str) -> str:
        """Cache key for provider."""
        return f"provider:{provider_id}"
    
    @staticmethod
    def model(model_id: str) -> str:
        """Cache key for model."""
        return f"model:{model_id}"
    
    @staticmethod
    def bot_config(bot_id: str) -> str:
        """Cache key for bot provider configuration."""
        return f"bot:{bot_id}:config"

    @staticmethod
    def bot_service_config(bot_id: str) -> str:
        """Cache key for bot settings."""
        return f"bot:{bot_id}:worker_config"
    
    @staticmethod
    def bot_origins(bot_id: str) -> str:
        """Cache key for bot allowed origins."""
        return f"bot:{bot_id}:origins"
    
    @staticmethod
    def allowed_origins(bot_key: str) -> str:
        """Cache key for bot allowed origins by bot_key (used by CORS middleware)."""
        return f"allowed_origins:{bot_key}"
    
    @staticmethod
    def users_list(page: int = 1, size: int = 20, filters: str = "") -> str:
        """Cache key for users list."""
        filter_key = f":filter:{filters}" if filters else ""
        return f"users:list:page:{page}:size:{size}{filter_key}"
    
    @staticmethod
    def bots_list(status: str = "", page: int = 1, size: int = 20) -> str:
        """Cache key for bots list."""
        status_key = f":status:{status}" if status else ""
        return f"bots:list{status_key}:page:{page}:size:{size}"
    
    @staticmethod
    def bot_documents(bot_id: str, page: int = 1, size: int = 20) -> str:
        """Cache key for bot documents list."""
        return f"bot:{bot_id}:documents:page:{page}:size:{size}"
    
    @staticmethod
    def bot_visitors(bot_id: str, page: int = 1, size: int = 20) -> str:
        """Cache key for bot visitors list."""
        return f"bot:{bot_id}:visitors:page:{page}:size:{size}"
    
    @staticmethod
    def providers_list(include_deleted: bool = False) -> str:
        """Cache key for providers list."""
        deleted_key = ":with_deleted" if include_deleted else ""
        return f"providers:list{deleted_key}"
    
    @staticmethod
    def models_list(provider_id: str = "", model_type: str = "") -> str:
        """Cache key for models list."""
        provider_key = f":provider:{provider_id}" if provider_id else ""
        type_key = f":type:{model_type}" if model_type else ""
        return f"models:list{provider_key}{type_key}"
    
    @staticmethod
    def analytics_overview() -> str:
        """Cache key for system-wide analytics."""
        return "analytics:overview"
    
    @staticmethod
    def analytics_bot(bot_id: str) -> str:
        """Cache key for bot-specific analytics."""
        return f"analytics:bot:{bot_id}"
    
    @staticmethod
    def analytics_usage(bot_id: str = "", period: str = "day") -> str:
        """Cache key for usage statistics."""
        bot_key = f":bot:{bot_id}" if bot_id else ""
        return f"analytics:usage{bot_key}:period:{period}"
    
    @staticmethod
    def blacklist(jti: str) -> str:
        """Cache key for blacklisted JWT token."""
        return f"blacklist:{jti}"
    
    @staticmethod
    def rate_limit_visitor(visitor_id: str) -> str:
        """Cache key for visitor rate limit."""
        return f"ratelimit:visitor:{visitor_id}"
    
    @staticmethod
    def rate_limit_ip(ip_address: str) -> str:
        """Cache key for IP rate limit."""
        return f"ratelimit:ip:{ip_address}"
    
    @staticmethod
    def rate_limit_user(user_id: str) -> str:
        """Cache key for user rate limit."""
        return f"ratelimit:user:{user_id}"
    
    @staticmethod
    def jwt_session(jti: str) -> str:
        """Cache key for JWT session tracking."""
        return f"session:jwt:{jti}"
    
    @staticmethod
    def user_notifications(user_id: str, unread_only: bool = False) -> str:
        """Cache key for user notifications."""
        unread_key = ":unread" if unread_only else ""
        return f"notifications:user:{user_id}{unread_key}"
    
    @staticmethod
    def notification_count(user_id: str) -> str:
        """Cache key for unread notification count."""
        return f"notifications:count:{user_id}"
    
    @staticmethod
    def user_pattern() -> str:
        """Pattern for all user cache keys."""
        return "user:*"
    
    @staticmethod
    def bot_pattern(bot_id: str = "") -> str:
        """Pattern for bot-related cache keys."""
        if bot_id:
            return f"bot:{bot_id}:*"
        return "bot:*"
    
    @staticmethod
    def document_pattern() -> str:
        """Pattern for all document cache keys."""
        return "document:*"
    
    @staticmethod
    def visitor_pattern() -> str:
        """Pattern for all visitor cache keys."""
        return "visitor:*"
    
    @staticmethod
    def analytics_pattern() -> str:
        """Pattern for all analytics cache keys."""
        return "analytics:*"
    
    @staticmethod
    def crawl_jobs_queue() -> str:
        """Queue key for domain crawl jobs."""
        return "queue:crawl_jobs"
    
    @staticmethod
    def document_jobs_queue() -> str:
        """Queue key for document processing jobs."""
        return "queue:document_jobs"
    
    @staticmethod
    def crawl_progress_channel(bot_id: str) -> str:
        """Pub/Sub channel for crawl progress updates."""
        return f"crawl:progress:{bot_id}"
    
    @staticmethod
    def document_progress_channel(document_id: str) -> str:
        """Pub/Sub channel for document processing progress."""
        return f"document:progress:{document_id}"
    
    @staticmethod
    def job_status(job_id: str) -> str:
        """Cache key for job status."""
        return f"job:status:{job_id}"
    
    @staticmethod
    def bot_crawl_status(bot_id: str) -> str:
        """Cache key for bot crawl status."""
        return f"bot:{bot_id}:crawl:status"
    
    @staticmethod
    def task_state(task_id: str) -> str:
        """Cache key for task state persistence (SSE resume support)."""
        return f"task:state:{task_id}"

    @staticmethod
    def active_tasks_index() -> str:
        """Sorted set of active task IDs with timestamp as score."""
        return "tasks:active:index"
    
    @staticmethod
    def task_progress_channel(task_id: str) -> str:
        """Pub/Sub channel for task progress updates (chat/grading/assessment/etc) via SSE."""
        return f"progress:{task_id}"
    
    @staticmethod
    def task_cancel_channel(session_id: str) -> str:
        """Pub/Sub channel for task cancellation signals."""
        return f"chat:cancel:{session_id}"
    
    @staticmethod
    def grading_lock(visitor_id: str) -> str:
        """
        Cache key for visitor grading lock (prevents duplicate grading).
        TTL: 300s (5 minutes)
        """
        return f"visitor:grading_lock:{visitor_id}"
    
    @staticmethod
    def assessment_lock(visitor_id: str) -> str:
        """
        Cache key for visitor assessment lock (prevents duplicate assessment).
        TTL: 300s (5 minutes)
        """
        return f"visitor:assessment_lock:{visitor_id}"
    
    @staticmethod
    def assessment_active(visitor_id: str) -> str:
        """
        Cache key for active assessment task ID per visitor.
        TTL: 600s (10 minutes)
        """
        return f"assessment:active:{visitor_id}"
    
    @staticmethod
    def assessment_progress(task_id: str) -> str:
        """
        Cache key for assessment progress data.
        TTL: 600s (10 minutes)
        """
        return f"assessment:progress:{task_id}"
    
    @staticmethod
    def crawl_lock(bot_id: str) -> str:
        """Lock key to prevent duplicate crawl tasks for same bot."""
        return f"crawl:lock:{bot_id}"
    
    @staticmethod
    def crawl_stop(bot_id: str) -> str:
        """Key to signal cancellation of crawl tasks for a bot."""
        return f"crawl:stop:{bot_id}"
    
    @staticmethod
    def invite_password(token: str) -> str:
        """Temporary password storage for invite acceptance (TTL: 7 days)."""
        return f"invite_password:{token}"
