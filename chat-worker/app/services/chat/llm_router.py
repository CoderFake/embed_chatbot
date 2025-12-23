"""LLM Router - Smart routing based on bot config."""
from __future__ import annotations

from typing import Any, AsyncGenerator, Dict, Optional

from app.services.llm import llm_service
from app.utils.logging import get_logger

logger = get_logger(__name__)


class LLMRouter:
    """Route LLM requests based on bot configuration."""

    async def complete(
        self,
        bot_config: Dict[str, Any],
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        provider = bot_config.get("provider", "openai")
        model = bot_config.get("model", "gpt-3.5-turbo")

        temp = temperature if temperature is not None else bot_config.get("temperature", 0.7)
        max_tok = max_tokens if max_tokens is not None else bot_config.get("max_tokens", 2000)

        logger.info(
            "LLM completion request",
            extra={"provider": provider, "model": model, "temperature": temp, "max_tokens": max_tok},
        )

        return await llm_service.complete(
            bot_config=bot_config,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temp,
            max_tokens=max_tok,
        )

    async def stream(
        self,
        bot_config: Dict[str, Any],
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        provider = bot_config.get("provider", "openai")
        model = bot_config.get("model", "gpt-3.5-turbo")

        temp = temperature if temperature is not None else bot_config.get("temperature", 0.7)
        max_tok = max_tokens if max_tokens is not None else bot_config.get("max_tokens", 2000)

        logger.info(
            "LLM streaming request",
            extra={"provider": provider, "model": model, "temperature": temp, "max_tokens": max_tok},
        )

        async for token in llm_service.stream(
            bot_config=bot_config,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temp,
            max_tokens=max_tok,
        ):
            yield token


llm_router = LLMRouter()
