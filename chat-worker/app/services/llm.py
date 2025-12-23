"""LLM service abstraction used by the chat worker."""
from __future__ import annotations

from typing import Any, AsyncGenerator, Dict, Optional

from app.utils.logging import get_logger

logger = get_logger(__name__)


class RateLimitError(Exception):
    """Exception raised when API rate limit (429) is hit."""
    pass


class LLMService:
    """Service for calling different LLM providers based on bot configuration."""

    async def complete(
        self,
        bot_config: Dict[str, Any],
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Call LLM provider based on bot configuration.

        Args:
            bot_config: Bot configuration
            system_prompt: System prompt
            user_prompt: User prompt
            temperature: Temperature override
            max_tokens: Max tokens override
            response_format: Response format (e.g., {"type": "json_object"} for JSON mode)

        Returns:
            Dict with keys:
                - text: str - The generated text
                - tokens_input: int - Input tokens used
                - tokens_output: int - Output tokens used
                - cost_usd: float - Estimated cost in USD
        """
        provider = bot_config.get("provider", "openai")
        model = bot_config.get("model", "gpt-3.5-turbo")
        api_key = bot_config.get("api_key", "")
        api_base_url = bot_config.get("api_base_url", "")

        if not api_key:
            raise ValueError(f"No API key configured for provider: {provider}")

        temp = temperature if temperature is not None else bot_config.get("temperature", 0.7)
        max_tok = max_tokens if max_tokens is not None else bot_config.get("max_tokens", 2000)
        top_p = bot_config.get("top_p", 0.95)

        logger.info(
            "Calling LLM provider",
            extra={
                "provider": provider,
                "model": model,
                "temperature": temp,
                "max_tokens": max_tok,
                "response_format": response_format,
            },
        )

        logger.info("=====================SYSTEM PROMPT=====================")
        logger.info(system_prompt)
        logger.info("=======================================================")

        logger.info("=====================USER PROMPT=====================")
        logger.info(user_prompt)
        logger.info("=======================================================")

        if provider == "openai":
            return await self._call_openai(
                api_key=api_key,
                api_base_url=api_base_url,
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temp,
                max_tokens=max_tok,
                top_p=top_p,
                bot_config=bot_config,
                response_format=response_format,
            )
        elif provider == "gemini":
            return await self._call_gemini(
                api_key=api_key,
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temp,
                max_tokens=max_tok,
                top_p=top_p,
                bot_config=bot_config,
                response_format=response_format,
            )
        elif provider == "ollama":
            return await self._call_ollama(
                api_base_url=api_base_url,
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temp,
                max_tokens=max_tok,
                top_p=top_p,
                response_format=response_format,
            )
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    async def stream(
        self,
        bot_config: Dict[str, Any],
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream LLM response based on bot configuration."""
        provider = bot_config.get("provider", "openai")
        model = bot_config.get("model", "gpt-3.5-turbo")
        api_key = bot_config.get("api_key", "")
        api_base_url = bot_config.get("api_base_url", "")

        if not api_key and provider != "ollama":
            raise ValueError(f"No API key configured for provider: {provider}")

        temp = temperature if temperature is not None else bot_config.get("temperature", 0.7)
        max_tok = max_tokens if max_tokens is not None else bot_config.get("max_tokens", 2000)
        top_p = bot_config.get("top_p", 0.95)

        logger.info(
            "Streaming LLM provider",
            extra={
                "provider": provider,
                "model": model,
            },
        )

        if provider == "openai":
            async for token in self._stream_openai(
                api_key=api_key,
                api_base_url=api_base_url,
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temp,
                max_tokens=max_tok,
                top_p=top_p,
            ):
                yield token
        elif provider == "gemini":
            async for token in self._stream_gemini(
                api_key=api_key,
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temp,
                max_tokens=max_tok,
                top_p=top_p,
            ):
                yield token
        elif provider == "ollama":
            async for token in self._stream_ollama(
                api_base_url=api_base_url,
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temp,
                max_tokens=max_tok,
                top_p=top_p,
            ):
                yield token
        else:
            raise ValueError(f"Streaming not supported for provider: {provider}")

    async def _call_openai(
        self,
        api_key: str,
        api_base_url: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
        top_p: float,
        bot_config: Dict[str, Any],
        response_format: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Call OpenAI API."""
        from openai import AsyncOpenAI, RateLimitError as OpenAIRateLimitError

        client = AsyncOpenAI(
            api_key=api_key,
            base_url=api_base_url if api_base_url else None,
        )

        try:
            kwargs = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": temperature,
                "max_completion_tokens": max_tokens,
                "top_p": top_p,
            }

            if response_format:
                kwargs["response_format"] = response_format

            response = await client.chat.completions.create(**kwargs)

            text = response.choices[0].message.content or ""
            usage = response.usage
            
            tokens_input = usage.prompt_tokens if usage else 0
            tokens_output = usage.completion_tokens if usage else 0
            
            extra_data = bot_config.get("extra_data", {})
            cost_per_1k_input = extra_data.get("cost_per_1k_input", 0.001)
            cost_per_1k_output = extra_data.get("cost_per_1k_output", 0.002)
            
            cost_usd = (
                (tokens_input / 1000) * cost_per_1k_input +
                (tokens_output / 1000) * cost_per_1k_output
            )
            
            return {
                "text": text,
                "tokens_input": tokens_input,
                "tokens_output": tokens_output,
                "cost_usd": round(cost_usd, 6),
            }

        except OpenAIRateLimitError as e:
            logger.warning(f"OpenAI rate limit (429) hit: {e}")
            raise RateLimitError(f"Rate limit exceeded: {e}")
        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}", exc_info=True)
            raise

    async def _stream_openai(
        self,
        api_key: str,
        api_base_url: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
        top_p: float,
    ) -> AsyncGenerator[str, None]:
        """Stream OpenAI API."""
        from openai import AsyncOpenAI, RateLimitError as OpenAIRateLimitError

        client = AsyncOpenAI(
            api_key=api_key,
            base_url=api_base_url if api_base_url else None,
        )

        try:
            stream = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_completion_tokens=max_tokens,
                top_p=top_p,
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except OpenAIRateLimitError as e:
            logger.warning(f"OpenAI streaming rate limit (429) hit: {e}")
            raise RateLimitError(f"Rate limit exceeded: {e}")
        except Exception as e:
            logger.error(f"OpenAI streaming failed: {e}", exc_info=True)
            raise

    async def _call_gemini(
        self,
        api_key: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
        top_p: float,
        bot_config: Dict[str, Any],
        response_format: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Call Google Gemini API.

        Note: Gemini doesn't support response_format like OpenAI's JSON mode.
        If response_format is provided, we'll add JSON instruction to the prompt.
        """
        import google.generativeai as genai
        from google.generativeai.types import HarmCategory, HarmBlockThreshold

        genai.configure(api_key=api_key)

        try:
            safety_settings = {
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }

            model_instance = genai.GenerativeModel(
                model,
                safety_settings=safety_settings
            )

            full_prompt = f"{system_prompt}\n\n{user_prompt}"

            if response_format and response_format.get("type") == "json_object":
                full_prompt += "\n\nIMPORTANT: Respond with valid JSON only, no markdown, no explanation."

            response = await model_instance.generate_content_async(
                full_prompt,
                generation_config=genai.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                    top_p=top_p,
                ),
            )

            if not response.candidates or not response.candidates[0].content.parts:
                finish_reason = response.candidates[0].finish_reason if response.candidates else "UNKNOWN"
                finish_reason_name = str(finish_reason).replace("FinishReason.", "")
                
                logger.warning(
                    f"Gemini response blocked or empty. Finish reason: {finish_reason_name}",
                    extra={
                        "finish_reason": finish_reason_name,
                        "prompt_length": len(full_prompt),
                        "prompt_preview": full_prompt[:200],
                        "safety_ratings": [
                            {
                                "category": str(rating.category).replace("HarmCategory.", ""),
                                "probability": str(rating.probability).replace("HarmProbability.", "")
                            }
                            for rating in (response.candidates[0].safety_ratings if response.candidates else [])
                        ] if response.candidates else []
                    }
                )
                
                return {
                    "text": "",
                    "tokens_input": 0,
                    "tokens_output": 0,
                    "cost_usd": 0.0,
                }
            
            text = response.text
            
            text_clean = text.strip()
            if text_clean.startswith("```"):
                lines = text_clean.split('\n')
                if len(lines) > 2:
                    text = '\n'.join(lines[1:-1]).strip()
            
            usage_metadata = response.usage_metadata if hasattr(response, 'usage_metadata') else None
            tokens_input = usage_metadata.prompt_token_count if usage_metadata else 0
            tokens_output = usage_metadata.candidates_token_count if usage_metadata else 0
            
            extra_data = bot_config.get("extra_data", {})
            cost_per_1k_input = extra_data.get("cost_per_1k_input", 0.0005)
            cost_per_1k_output = extra_data.get("cost_per_1k_output", 0.0015)
            
            cost_usd = (
                (tokens_input / 1000) * cost_per_1k_input +
                (tokens_output / 1000) * cost_per_1k_output
            )
            
            return {
                "text": text,
                "tokens_input": tokens_input,
                "tokens_output": tokens_output,
                "cost_usd": round(cost_usd, 6),
            }

        except Exception as e:
            logger.error(f"Gemini API call failed: {e}", exc_info=True)
            raise
    
    async def _stream_gemini(
        self,
        api_key: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
        top_p: float,
    ) -> AsyncGenerator[str, None]:
        """Stream Google Gemini API."""
        import google.generativeai as genai
        from google.generativeai.types import HarmCategory, HarmBlockThreshold

        genai.configure(api_key=api_key)

        try:
            safety_settings = {
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
            
            model_instance = genai.GenerativeModel(
                model,
                safety_settings=safety_settings
            )
            
            full_prompt = f"{system_prompt}\n\n{user_prompt}"
            
            response = await model_instance.generate_content_async(
                full_prompt,
                generation_config=genai.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                    top_p=top_p,
                ),
                stream=True,
            )
            
            has_content = False
            async for chunk in response:
                if chunk.text:
                    has_content = True
                    yield chunk.text
            
            if not has_content:
                logger.warning("Gemini streaming produced no content (possibly blocked by safety filter)")

        except Exception as e:
            logger.error(f"Gemini streaming failed: {e}", exc_info=True)
            raise

    async def _call_ollama(
        self,
        api_base_url: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
        top_p: float,
        response_format: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Call Ollama API.

        Note: Ollama supports JSON mode via format parameter.
        """
        import httpx

        url = f"{api_base_url}/api/chat"

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "top_p": top_p,
            },
            "stream": False,
        }

        if response_format and response_format.get("type") == "json_object":
            payload["format"] = "json"

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                result = response.json()
                
                text = result.get("message", {}).get("content", "")
                
                tokens_input = result.get("prompt_eval_count", 0)
                tokens_output = result.get("eval_count", 0)
                
                return {
                    "text": text,
                    "tokens_input": tokens_input,
                    "tokens_output": tokens_output,
                    "cost_usd": 0.0,
                }

        except Exception as e:
            logger.error(f"Ollama API call failed: {e}", exc_info=True)
            raise

    async def _stream_ollama(
        self,
        api_base_url: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
        top_p: float,
    ) -> AsyncGenerator[str, None]:
        """Stream Ollama API."""
        import httpx
        import json

        url = f"{api_base_url}/api/chat"

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "top_p": top_p,
            },
            "stream": True,
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream("POST", url, json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line.strip():
                            try:
                                chunk = json.loads(line)
                                if "message" in chunk and "content" in chunk["message"]:
                                    yield chunk["message"]["content"]
                            except json.JSONDecodeError:
                                continue

        except Exception as e:
            logger.error(f"Ollama streaming failed: {e}", exc_info=True)
            raise


llm_service = LLMService()
