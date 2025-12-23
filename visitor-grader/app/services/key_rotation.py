"""API Key rotation service for handling rate limits."""
import json
import time
from typing import Any, Dict, List, Optional

from app.core.redis_client import redis_client
from app.cache.keys import CacheKeys
from app.utils.logging import get_logger

logger = get_logger(__name__)


class KeyRotationService:
    """
    Manages API key rotation and rate limit tracking.
    
    Features:
    - Round-robin key selection
    - Track rate limit (429) errors per key
    - Cooldown period after rate limit
    - Redis-based state management
    """
    
    def __init__(self):
        self.cooldown_duration = 60
    
    async def get_next_available_key(
        self, 
        bot_id: str, 
        available_keys: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Get next available API key that's not in cooldown.
        
        Args:
            bot_id: Bot identifier
            available_keys: List of decrypted keys with metadata
                           [{"key": "sk-xxx", "is_active": true}, ...]
        
        Returns:
            Selected key dict with index, or None if all keys in cooldown
        """
        if not available_keys:
            logger.error("No available keys", extra={"bot_id": bot_id})
            return None
        
        redis = redis_client.get_client()
        current_time = time.time()
        
        # Get current key index (round-robin)
        current_index_key = f"bot:{bot_id}:current_key_index"
        current_index = await redis.get(current_index_key)
        current_index = int(current_index) if current_index else 0
        
        # Try each key starting from current index
        for i in range(len(available_keys)):
            key_index = (current_index + i) % len(available_keys)
            key_data = available_keys[key_index]
            
            # Check if key is in cooldown
            state_key = f"bot:{bot_id}:key:{key_index}:state"
            state_data = await redis.get(state_key)
            
            if state_data:
                try:
                    state = json.loads(state_data)
                    cooldown_until = state.get("cooldown_until", 0)
                    
                    if cooldown_until > current_time:
                        remaining = int(cooldown_until - current_time)
                        logger.info(
                            f"Key {key_index} in cooldown for {remaining}s",
                            extra={"bot_id": bot_id, "key_index": key_index}
                        )
                        continue
                except json.JSONDecodeError:
                    pass
            
            # Key is available, update current index for next time
            next_index = (key_index + 1) % len(available_keys)
            await redis.set(current_index_key, str(next_index), ex=3600)
            
            logger.info(
                "Selected API key",
                extra={
                    "bot_id": bot_id,
                    "key_index": key_index,
                    "total_keys": len(available_keys)
                }
            )
            
            return {
                "key": key_data["key"],
                "index": key_index,
                "is_active": key_data.get("is_active", True)
            }
        
        # All keys in cooldown
        logger.error(
            "All API keys in cooldown",
            extra={"bot_id": bot_id, "total_keys": len(available_keys)}
        )
        return None
    
    async def mark_key_rate_limited(self, bot_id: str, key_index: int) -> None:
        """
        Mark an API key as rate-limited (cooldown).
        
        Args:
            bot_id: Bot identifier
            key_index: Index of the key that hit rate limit
        """
        redis = redis_client.get_client()
        state_key = f"bot:{bot_id}:key:{key_index}:state"
        cooldown_until = time.time() + self.cooldown_duration
        
        state = {
            "cooldown_until": cooldown_until,
            "last_rate_limit": time.time()
        }
        
        await redis.set(state_key, json.dumps(state), ex=self.cooldown_duration + 10)
        
        logger.warning(
            "Marked API key as rate-limited",
            extra={
                "bot_id": bot_id,
                "key_index": key_index,
                "cooldown_seconds": self.cooldown_duration
            }
        )


key_rotation_service = KeyRotationService()

