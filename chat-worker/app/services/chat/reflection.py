"""Reflection service - Language detection, intent classification, query rewriting.

Improved with techniques from NVIDIA RAG-server:
- ReflectionCounter to prevent infinite loops
- Retry mechanism for LLM calls
- Scoring system for relevance and groundedness
- Separate prompts for each task
"""
from __future__ import annotations

import json
from typing import Dict, List, Tuple

from app.services.chat.prompt import prompt_manager
from app.services.llm import llm_service
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ReflectionCounter:
    """Tracks reflection iterations to prevent infinite loops (học từ RAG-server)."""
    
    def __init__(self, max_loops: int = 2):
        self.max_loops = max_loops
        self.current_count = 0

    def increment(self) -> bool:
        """Increment counter and return whether we can continue."""
        if self.current_count >= self.max_loops:
            return False
        self.current_count += 1
        return True

    @property
    def remaining(self) -> int:
        return max(0, self.max_loops - self.current_count)


class ReflectionService:
    """Handles query analysis using the configured LLM provider."""

    def __init__(self) -> None:
        self.prompt_manager = prompt_manager

    async def _retry_llm_call(
        self,
        bot_config: dict,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 512,
        max_retries: int = 3,
    ) -> str:
        """Helper to retry LLM calls with error handling"""
        for retry in range(max_retries):
            try:
                result_dict = await llm_service.complete(
                    bot_config=bot_config,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                response = result_dict.get("text", "").strip()
                if response:
                    return response
            except Exception as e:
                logger.warning(f"LLM call retry {retry + 1}/{max_retries} failed: {e}")
                if retry == max_retries - 1:
                    logger.error("All retries failed for LLM call")
                    raise
        return ""

    async def analyze_query(
        self, 
        query: str, 
        visitor_profile: dict | None = None, 
        long_term_memory: str | None = None, 
        bot_config: dict | None = None,
        conversation_history: List[Dict[str, str]] | None = None,
    ) -> Dict:
        """Analyse query to detect language, intent, retrieval need, and rewrite query if needed."""
        if not bot_config:
            logger.warning("No bot_config provided for reflection, using defaults")
            return {
                "language": "vi",
                "confidence": 0.5,
                "intent": "question",
                "needs_retrieval": True,
                "rewritten_query": query,
            }
        
        system_prompt = self.prompt_manager.get_reflection_analyzer_prompt()
        user_prompt = self.prompt_manager.format_reflection_analyzer(
            query=query,
            visitor_profile=visitor_profile,
            long_term_memory=long_term_memory,
            conversation_history=conversation_history,
        )

        try:
            result_dict = await llm_service.complete(
                bot_config=bot_config,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.0,
                max_tokens=1028,
                response_format={"type": "json_object"},
            )
            response = result_dict.get("text", "")
            
            if not response:
                logger.error("LLM returned empty response for reflection")
                result = {}
            else:
                response = response.strip()
                if response.startswith("```json"):
                    response = response[7:]  # Remove ```json
                if response.startswith("```"):
                    response = response[3:]  # Remove ```
                if response.endswith("```"):
                    response = response[:-3]  # Remove ```
                response = response.strip()
                
                result = json.loads(response)
                
                if "visitor_info" in result:
                    visitor_info = result["visitor_info"]
                    if isinstance(visitor_info, str):
                        logger.warning(f"visitor_info is string, auto-fixing: {visitor_info}")
                        result["visitor_info"] = {
                            "name": visitor_info,
                            "email": None,
                            "phone": None,
                            "address": None
                        }
                    elif visitor_info is not None and not isinstance(visitor_info, dict):
                        logger.error(f"visitor_info has invalid type {type(visitor_info)}, setting to null")
                        result["visitor_info"] = None
                    
        except json.JSONDecodeError as e:
            logger.error("Failed to parse reflection response: %s. Raw: %s", e, response[:200])
            result = {}
        except Exception as e:
            logger.error(f"Reflection failed: {e}", exc_info=True)
            return {
                "language": "vi",
                "confidence": 0.5,
                "intent": "question",
                "needs_retrieval": True,  
                "rewritten_query": query,
            }

        if not result:
            logger.error(
                "Reflection failed completely, using neutral defaults",
                extra={"query": query[:50]}
            )
            result = {
                "language": "vi",
                "confidence": 0.0,
                "intent": "unknown",
                "needs_retrieval": True,  
                "rewritten_query": query,
            }
        
        if "rewritten_query" not in result:
            result["rewritten_query"] = query

        logger.info(
            f"Reflection result: intent={result.get('intent')}, needs_retrieval={result.get('needs_retrieval')}, confidence={result.get('confidence', 0):.2f}",
            extra={
                "language": result.get("language"),
                "rewritten_query": result.get("rewritten_query"),
            },
        )
        return result

    async def check_context_relevance(
        self,
        query: str,
        context: str,
        bot_config: dict,
        threshold: int = 1,
    ) -> Tuple[int, bool]:
        """Check relevance of context to query using scoring.
        
        Returns: (score, meets_threshold)
        Score: 0 (not relevant), 1 (partially relevant), 2 (fully relevant)
        """
        if not context or len(context.strip()) < 10:
            logger.warning("Context too short for relevance check")
            return 0, False

        prompts = self.prompt_manager.get_reflection_relevance_prompt()
        system_prompt = prompts["system"]
        template = prompts["template"]
        user_prompt = template.format(query=query, context=context)

        try:
            response = await self._retry_llm_call(
                bot_config=bot_config,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.0,
                max_tokens=10,
                max_retries=3,
            )
            
            score = 0
            for s in [2, 1, 0]:
                if str(s) in response:
                    score = s
                    break
            
            meets_threshold = score >= threshold
            logger.info(f"Context relevance: score={score}, threshold={threshold}, meets={meets_threshold}")
            return score, meets_threshold
            
        except Exception as e:
            logger.error(f"Context relevance check failed: {e}")
            return 0, False

    async def check_response_groundedness(
        self,
        response: str,
        context: str,
        bot_config: dict,
        reflection_counter: ReflectionCounter,
        threshold: int = 1,
    ) -> Tuple[str, bool, int]:
        """Check if response is grounded in context.
        
        Returns: (final_response, is_grounded, score)
        """
        prompts = self.prompt_manager.get_reflection_groundedness_prompt()
        system_prompt = prompts["system"]
        template = prompts["template"]
        
        current_response = response

        while reflection_counter.remaining > 0:
            user_prompt = template.format(context=context, response=current_response)

            try:
                score_response = await self._retry_llm_call(
                    bot_config=bot_config,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=0.0,
                    max_tokens=10,
                )
                
                score = 0
                for s in [2, 1, 0]:
                    if str(s) in score_response:
                        score = s
                        break
                
                logger.info(f"Response groundedness: score={score}, threshold={threshold}")
                reflection_counter.increment()

                if score >= threshold:
                    return current_response, True, score

                if reflection_counter.remaining > 0:
                    regen_system = "You are a helpful AI assistant. Generate a response that is grounded in the provided context. Use only information explicitly supported by the context."
                    regen_user = f"Context: {context}\n\nPrevious response (not grounded): {current_response}\n\nGenerate a new, more grounded response:"

                    current_response = await self._retry_llm_call(
                        bot_config=bot_config,
                        system_prompt=regen_system,
                        user_prompt=regen_user,
                        temperature=0.3,
                        max_tokens=512,
                    )
                    logger.info(f"Regenerated response (iteration {reflection_counter.current_count})")

            except Exception as e:
                logger.error(f"Groundedness check failed: {e}")
                break

        return current_response, False, 0


reflection_service = ReflectionService()
