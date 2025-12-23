"""Provider service for chat worker with API key decryption and rotation."""
from __future__ import annotations

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
from app.core.service_manager import service_manager
from app.core.keys import ChatKeys
from app.services.key_rotation import key_rotation_service
from app.utils.encryption import decrypt_api_key
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ChatProviderService:
    """Provider service for chat worker with encrypted API key handling."""

    def __init__(self):
        pass

    async def get_bot_config(self, bot_id: str, db: AsyncSession) -> Dict[str, Any]:
        """
        Get bot configuration with decrypted API keys.
        
        Security Strategy:
        1. Cache full metadata + ENCRYPTED keys
        2. Decrypt keys only when needed (on method call)
        3. Never cache decrypted keys

        Args:
            bot_id: Bot ID
            db: Database session

        Returns:
            Bot configuration with DECRYPTED API keys (keys decrypted at runtime)
        """
        redis = service_manager.get_redis()
        cache_key = ChatKeys.bot_config(bot_id)
        
        cached_data = await redis.get(cache_key)
        if cached_data:
            try:
                cached_config = json.loads(cached_data)
                logger.debug("Bot config cache hit (encrypted keys)", extra={"bot_id": bot_id})
                
                encrypted_keys = cached_config.get("encrypted_keys", [])
                decrypted_keys = self._decrypt_keys(encrypted_keys, bot_id)
                
                active_keys = [k for k in decrypted_keys if k.get("is_active", True)]
                
                return {
                    "name": cached_config.get("name", "AI Assistant"),
                    "desc": cached_config.get("desc", ""),
                    "provider": cached_config["provider"],
                    "model": cached_config["model"],
                    "model_id": cached_config.get("model_id"),
                    "api_base_url": cached_config["api_base_url"],
                    "api_key": active_keys[0]["key"] if active_keys else "",
                    "temperature": cached_config["temperature"],
                    "max_tokens": cached_config["max_tokens"],
                    "top_p": cached_config["top_p"],
                    "available_keys_count": len(active_keys),
                    "available_keys": active_keys,
                    "extra_data": cached_config.get("extra_data", {}),
                }
            except Exception as e:
                logger.warning(f"Cache read error: {e}", extra={"bot_id": bot_id})

        config = await self._load_bot_config_from_db(bot_id, db)
        
        return config

    async def _load_bot_config_from_db(self, bot_id: str, db: AsyncSession) -> Dict[str, Any]:
        """Load bot configuration from database and decrypt API keys."""

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
            logger.warning("Bot has no provider config, using defaults", extra={"bot_id": bot_id})
            return self._default_config()

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
            return self._default_config()

        encrypted_keys = provider_config.get("api_keys", [])
        if isinstance(encrypted_keys, str):
            encrypted_keys = json.loads(encrypted_keys)

        decrypted_keys = self._decrypt_keys(encrypted_keys, bot_id)
        active_keys = [k for k in decrypted_keys if k.get("is_active", True)]

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
            "model_id": str(provider_config["model_id"]),
            "api_base_url": provider.get("api_base_url", "https://api.openai.com/v1"),
            "api_key": active_keys[0]["key"] if active_keys else "",
            "temperature": config_data.get("temperature", 0.7),
            "max_tokens": config_data.get("max_tokens", 2000),
            "top_p": config_data.get("top_p", 0.95),
            "available_keys_count": len(active_keys),
            "available_keys": active_keys,
            "extra_data": {
                "cost_per_1k_input": model_extra_data.get("cost_per_1k_input", 0.0),
                "cost_per_1k_output": model_extra_data.get("cost_per_1k_output", 0.0),
                "pricing_per_1m": model.get("pricing", 0.0),
            }
        }
        
        redis = service_manager.get_redis()
        cache_data = {
            "name": result["name"],
            "desc": result["desc"],
            "provider": result["provider"],
            "model": result["model"],
            "model_id": result["model_id"],
            "api_base_url": result["api_base_url"],
            "temperature": result["temperature"],
            "max_tokens": result["max_tokens"],
            "top_p": result["top_p"],
            "extra_data": result["extra_data"],
            "encrypted_keys": encrypted_keys,
        }
        await redis.setex(ChatKeys.bot_config(bot_id), 3600, json.dumps(cache_data))

        logger.info("Loaded bot config with decrypted keys", extra={
            "bot_id": bot_id,
            "provider": result["provider"],
            "model": result["model"],
            "available_keys": result["available_keys"]
        })

        return result

    async def get_bot_config_with_key_selection(self, bot_id: str) -> Optional[Dict[str, Any]]:
        """
        Get bot configuration with automatic key rotation.
        
        This method:
        1. Loads bot config with all available keys
        2. Uses key rotation service to select next available key
        3. Returns config with selected key and key index for tracking
        
        Args:
            bot_id: Bot identifier
            
        Returns:
            Bot config with selected api_key and key_index, or None if no keys available
        """
        db_session = await service_manager.get_db_session()
        
        async with db_session as db:
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

    def _default_config(self) -> Dict[str, Any]:
        """Return default configuration."""
        return {
            "name": "AI Assistant",
            "desc": "",
            "provider": "openai",
            "model": "gpt-3.5-turbo",
            "api_base_url": "https://api.openai.com/v1",
            "api_key": "",
            "temperature": 0.7,
            "max_tokens": 2000,
            "top_p": 0.95,
            "available_keys_count": 0,
            "available_keys": [],
        }


chat_provider_service = ChatProviderService()
