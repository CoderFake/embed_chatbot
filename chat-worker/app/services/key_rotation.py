"""API Key rotation service for handling rate limits."""
from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

from app.core.service_manager import service_manager
from app.core.keys import ChatKeys
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
    - Uses centralized ChatKeys for key naming
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
        
        redis = service_manager.get_redis()
        current_time = time.time()
        
        # Get current key index (round-robin)
        current_index_key = ChatKeys.current_key_index(bot_id)
        current_index = await redis.get(current_index_key)
        current_index = int(current_index) if current_index else 0
        
        # Try each key starting from current index
        for i in range(len(available_keys)):
            key_index = (current_index + i) % len(available_keys)
            key_data = available_keys[key_index]
            
            # Check if key is in cooldown
            state_key = ChatKeys.key_state(bot_id, key_index)
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
        Mark a key as rate-limited (429 error).
        
        Args:
            bot_id: Bot identifier
            key_index: Index of the key in available_keys list
        """
        redis = service_manager.get_redis()
        state_key = ChatKeys.key_state(bot_id, key_index)
        
        current_time = time.time()
        cooldown_until = current_time + self.cooldown_duration
        
        state = {
            "last_429_at": current_time,
            "cooldown_until": cooldown_until,
            "rate_limited_count": 1
        }
        
        # Check if key was already rate-limited
        existing_state = await redis.get(state_key)
        if existing_state:
            try:
                existing = json.loads(existing_state)
                state["rate_limited_count"] = existing.get("rate_limited_count", 0) + 1
            except json.JSONDecodeError:
                pass
        
        await redis.setex(
            state_key,
            self.cooldown_duration + 10,  # Extra 10s buffer
            json.dumps(state)
        )
        
        logger.warning(
            "API key marked as rate-limited",
            extra={
                "bot_id": bot_id,
                "key_index": key_index,
                "cooldown_seconds": self.cooldown_duration,
                "rate_limited_count": state["rate_limited_count"]
            }
        )
    
    async def increment_key_usage(self, bot_id: str, key_index: int) -> None:
        """
        Increment usage counter for a key.
        
        Args:
            bot_id: Bot identifier
            key_index: Index of the key
        """
        redis = service_manager.get_redis()
        usage_key = ChatKeys.key_usage(bot_id, key_index)
        
        await redis.incr(usage_key)
        await redis.expire(usage_key, 3600)  # 1 hour window
    
    async def get_key_stats(self, bot_id: str, total_keys: int) -> Dict[str, Any]:
        """
        Get statistics for all keys.
        
        Args:
            bot_id: Bot identifier
            total_keys: Total number of keys
        
        Returns:
            Stats dict with usage and cooldown info
        """
        redis = service_manager.get_redis()
        current_time = time.time()
        
        stats = []
        for i in range(total_keys):
            usage_key = ChatKeys.key_usage(bot_id, i)
            state_key = ChatKeys.key_state(bot_id, i)
            
            usage = await redis.get(usage_key)
            usage = int(usage) if usage else 0
            
            state_data = await redis.get(state_key)
            in_cooldown = False
            cooldown_remaining = 0
            
            if state_data:
                try:
                    state = json.loads(state_data)
                    cooldown_until = state.get("cooldown_until", 0)
                    if cooldown_until > current_time:
                        in_cooldown = True
                        cooldown_remaining = int(cooldown_until - current_time)
                except json.JSONDecodeError:
                    pass
            
            stats.append({
                "key_index": i,
                "usage_1h": usage,
                "in_cooldown": in_cooldown,
                "cooldown_remaining": cooldown_remaining
            })
        
        return {
            "bot_id": bot_id,
            "total_keys": total_keys,
            "keys": stats
        }


key_rotation_service = KeyRotationService()

