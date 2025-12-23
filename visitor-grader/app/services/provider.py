"""Provider service for visitor grader - loads bot provider config from database."""
import json
from typing import Any, Dict, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    bots,
    models,
    provider_configs,
    providers,
)
from app.core.redis_client import redis_client
from app.cache import CacheService, CacheKeys
from app.utils.encryption import decrypt_api_key
from app.services.key_rotation import key_rotation_service
from app.config.settings import settings
from app.utils.logging import get_logger


logger = get_logger(__name__)


class ProviderService:
    """
    Provider service for loading bot configuration with Redis cache.
    
    Uses lazy initialization for CacheService to avoid importing Redis
    at module load time.
    """
    
    def __init__(self):
        self._cache: Optional[CacheService] = None
    
    @property
    def cache(self) -> CacheService:
        """Lazy initialization of CacheService."""
        if self._cache is None:
            self._cache = CacheService(redis_client.get_client())
        return self._cache

    async def get_bot_config(self, bot_id: str, db: AsyncSession) -> Dict[str, Any]:
        """
        Get bot configuration with decrypted API keys.
        Checks Redis cache first (encrypted keys), then loads from database.
        
        Security Strategy:
        1. Cache full metadata + ENCRYPTED keys
        2. Decrypt keys only when needed (at runtime)
        3. Never cache decrypted keys

        Args:
            bot_id: Bot ID
            db: Database session

        Returns:
            Bot configuration with DECRYPTED available_keys (decrypted at runtime)
        """
        cache_key = CacheKeys.bot_config(bot_id)
        cached_data = await self.cache.get(cache_key, as_json=True)
        
        if cached_data:
            encrypted_keys = cached_data.get("encrypted_keys", [])
            decrypted_keys = self._decrypt_keys(encrypted_keys, bot_id)
            active_keys = [k for k in decrypted_keys if k.get("is_active", True)]
            
            return {
                "name": cached_data.get("name", "AI Assistant"),
                "desc": cached_data.get("desc", ""),
                "provider": cached_data["provider"],
                "model": cached_data["model"],
                "api_base_url": cached_data["api_base_url"],
                "api_key": active_keys[0]["key"] if active_keys else "",
                "temperature": cached_data["temperature"],
                "max_tokens": cached_data["max_tokens"],
                "top_p": cached_data["top_p"],
                "available_keys_count": len(active_keys),
                "available_keys": active_keys,
            }
        
        config = await self._load_bot_config_from_db(bot_id, db)
        
        return config
    
    async def get_bot_config_with_key_selection(self, bot_id: str, db: AsyncSession) -> Optional[Dict[str, Any]]:
        """
        Get bot configuration with automatic key rotation.
        
        Args:
            bot_id: Bot identifier
            db: Database session
            
        Returns:
            Bot config with selected api_key and key_index, or None if no keys available
        """
        config = await self.get_bot_config(bot_id, db)
        
        available_keys = config.get("available_keys", [])
        
        if not available_keys:
            logger.error("No available API keys for bot", extra={"bot_id": bot_id})
            return None
        
        selected_key_data = await key_rotation_service.get_next_available_key(
            bot_id=bot_id,
            available_keys=available_keys
        )
        
        if not selected_key_data:
            logger.error("All API keys in cooldown", extra={"bot_id": bot_id})
            return None
        
        config["api_key"] = selected_key_data["key"]
        config["key_index"] = selected_key_data["index"]
        
        logger.info(
            "Selected API key for bot",
            extra={
                "bot_id": bot_id,
                "key_index": selected_key_data["index"],
                "total_keys": len(available_keys)
            }
        )
        
        return config

    async def _load_bot_config_from_db(self, bot_id: str, db: AsyncSession) -> Dict[str, Any]:
        """
        Get bot configuration with decrypted API keys.

        Args:
            bot_id: Bot ID
            db: Database session

        Returns:
            Bot configuration with provider, model, decrypted api_key
        """
        bot_query = await db.execute(
            select(bots.c.id, bots.c.name, bots.c.desc).where(
                and_(
                    bots.c.id == bot_id,
                    bots.c.is_deleted.is_(False),
                )
            )
        )
        bot_row = bot_query.mappings().first()
        if bot_row is None:
            logger.error("Bot not found", extra={"bot_id": bot_id})
            raise ValueError(f"Bot {bot_id} not found")
        
        bot_name = bot_row.get("name", "AI Assistant")
        bot_desc = bot_row.get("desc", "")

        config_query = (
            select(
                provider_configs.c.provider_id,
                provider_configs.c.model_id,
                provider_configs.c.api_keys,
                provider_configs.c.config,
            )
            .where(
                and_(
                    provider_configs.c.bot_id == bot_id,
                    provider_configs.c.is_deleted.is_(False),
                )
            )
            .limit(1)
        )
        config_row = await db.execute(config_query)
        provider_config = config_row.mappings().first()

        if not provider_config:
            logger.warning("Bot has no provider config", extra={"bot_id": bot_id})
            raise ValueError(f"Bot {bot_id} has no provider configuration")

        provider_row = await db.execute(
            select(
                providers.c.slug,
                providers.c.api_base_url,
            ).where(
                and_(
                    providers.c.id == provider_config["provider_id"],
                    providers.c.deleted_at.is_(None),
                )
            )
        )
        provider = provider_row.mappings().first()

        model_row = await db.execute(
            select(
                models.c.name,
                models.c.pricing,
                models.c.extra_data
            ).where(
                and_(
                    models.c.id == provider_config["model_id"],
                    models.c.deleted_at.is_(None),
                )
            )
        )
        model = model_row.mappings().first()

        if not provider or not model:
            logger.error("Incomplete provider configuration", extra={"bot_id": bot_id})
            raise ValueError(f"Bot {bot_id} has incomplete provider configuration")

        encrypted_keys = provider_config.get("api_keys", [])
        if isinstance(encrypted_keys, str):
            encrypted_keys = json.loads(encrypted_keys)

        decrypted_keys = self._decrypt_keys(encrypted_keys, bot_id)
        active_keys = [k for k in decrypted_keys if k.get("is_active", True)]
        
        if not active_keys:
            logger.error("No valid API keys available", extra={"bot_id": bot_id})
            raise ValueError(f"Bot {bot_id} has no valid API keys")

        config_data = provider_config.get("config", {})
        if isinstance(config_data, str):
            config_data = json.loads(config_data)
        
        model_extra_data = model.get("extra_data", {})
        if isinstance(model_extra_data, str):
            model_extra_data = json.loads(model_extra_data)

        result = {
            "name": bot_name,
            "desc": bot_desc,
            "provider": provider.get("slug", "openai"),
            "model": model.get("name", "gpt-3.5-turbo"),
            "api_base_url": provider.get("api_base_url", "https://api.openai.com/v1"),
            "api_key": active_keys[0]["key"],
            "temperature": config_data.get("temperature", 0.7),
            "max_tokens": config_data.get("max_tokens", 1000),
            "top_p": config_data.get("top_p", 0.95),
            "available_keys_count": len(active_keys),
            "available_keys": active_keys,
        }
        
        cache_key = CacheKeys.bot_config(bot_id)
        cache_data = {
            "name": result["name"],
            "desc": result["desc"],
            "provider": result["provider"],
            "model": result["model"],
            "api_base_url": result["api_base_url"],
            "temperature": result["temperature"],
            "max_tokens": result["max_tokens"],
            "top_p": result["top_p"],
            "available_keys_count": result["available_keys_count"],
            "encrypted_keys": encrypted_keys,
        }
        await self.cache.set(cache_key, cache_data, ttl=settings.BOT_CONFIG_TTL, as_json=True)

        logger.info("Loaded bot config", extra={
            "bot_id": bot_id,
            "provider": result["provider"],
            "model": result["model"],
        })

        return result
    
    def _decrypt_keys(self, encrypted_keys: list, bot_id: str) -> list:
        """
        Decrypt API keys at runtime.
        
        Args:
            encrypted_keys: List of encrypted key items
            bot_id: Bot ID for logging
            
        Returns:
            List of decrypted key items with is_active flag
        """
        decrypted_keys = []
        for key_item in encrypted_keys:
            if isinstance(key_item, dict) and "key" in key_item:
                try:
                    decrypted_key = decrypt_api_key(key_item["key"])
                    decrypted_keys.append({
                        "key": decrypted_key,
                        "is_active": key_item.get("is_active", True)
                    })
                except Exception as e:
                    logger.error("Failed to decrypt API key", extra={
                        "bot_id": bot_id,
                        "error": str(e)
                    })
            elif isinstance(key_item, str):
                try:
                    decrypted_key = decrypt_api_key(key_item)
                    decrypted_keys.append({"key": decrypted_key, "is_active": True})
                except Exception as e:
                    logger.error("Failed to decrypt legacy API key", extra={
                        "bot_id": bot_id,
                        "error": str(e)
                    })
        return decrypted_keys
    
    def _decrypt_first_active_key(self, encrypted_keys: list, bot_id: str) -> str:
        """
        Decrypt first active API key.
        
        Args:
            encrypted_keys: List of encrypted key items from DB
            bot_id: Bot ID for logging
            
        Returns:
            First decrypted active key, or empty string if none available
        """
        for key_item in encrypted_keys:
            if isinstance(key_item, dict) and "key" in key_item:
                if not key_item.get("is_active", True):
                    continue
                try:
                    return decrypt_api_key(key_item["key"])
                except Exception as e:
                    logger.error("Failed to decrypt API key", extra={
                        "bot_id": bot_id,
                        "error": str(e)
                    })
            elif isinstance(key_item, str):
                try:
                    return decrypt_api_key(key_item)
                except Exception as e:
                    logger.error("Failed to decrypt legacy API key", extra={
                        "bot_id": bot_id,
                        "error": str(e)
                    })
        return ""


provider_service = ProviderService()
