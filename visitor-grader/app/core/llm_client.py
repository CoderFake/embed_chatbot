"""LLM service for lead scoring - uses bot's provider config from database."""
from typing import Any, Dict
import json
from app.core.prompt_loader import prompt_loader
from app.utils.logging import get_logger

logger = get_logger(__name__)


class LLMService:
    """LLM service that uses bot's provider configuration."""
    
    async def score_visitor(
        self,
        bot_config: Dict[str, Any],
        conversation_history: list,
        visitor_profile: dict,
        system_prompt: str,
        rag_context: str = None
    ) -> Dict[str, Any]:
        """
        Score visitor using bot's configured LLM provider.
        
        Args:
            bot_config: Bot configuration with provider, model, api_key
            conversation_history: List of conversation messages
            visitor_profile: Visitor profile data
            system_prompt: System prompt for scoring
            rag_context: Optional RAG context from retrieval+rerank
            
        Returns:
            Dict with scoring result (score, category, intent_signals, etc.)
        """
        provider = bot_config.get("provider", "openai")
        
        logger.info(
            "Scoring visitor with LLM",
            extra={
                "provider": provider,
                "model": bot_config.get("model"),
                "has_rag_context": bool(rag_context)
            }
        )
        
        user_prompt = self._build_user_prompt(conversation_history, visitor_profile, rag_context)
        
        if provider == "openai":
            return await self._call_openai(bot_config, system_prompt, user_prompt)
        elif provider == "gemini":
            return await self._call_gemini(bot_config, system_prompt, user_prompt)
        elif provider == "ollama":
            return await self._call_ollama(bot_config, system_prompt, user_prompt)
        else:
            raise ValueError(f"Unsupported provider: {provider}")
    
    async def assess_visitor(
        self,
        bot_config: Dict[str, Any],
        conversation_history: list,
        visitor_profile: dict,
        assessment_questions: list,
        rag_context: str = None
    ) -> Dict[str, Any]:
        """
        Assess visitor using custom assessment questions.
        Returns dict with: results (list of {question, answer, confidence, relevant_messages}), summary (str)
        """
        provider = bot_config.get("provider", "openai")
        
        logger.info(
            "Assessing visitor with LLM",
            extra={
                "provider": provider,
                "model": bot_config.get("model"),
                "num_questions": len(assessment_questions)
            }
        )
        
        system_prompt = self._build_assessment_system_prompt(assessment_questions)
        user_prompt = self._build_user_prompt(
            conversation_history, 
            visitor_profile, 
            rag_context,
            bot_desc=bot_config.get("desc", "")
        )
        
        if provider == "openai":
            return await self._call_openai(bot_config, system_prompt, user_prompt)
        elif provider == "gemini":
            return await self._call_gemini(bot_config, system_prompt, user_prompt)
        elif provider == "ollama":
            return await self._call_ollama(bot_config, system_prompt, user_prompt)
        else:
            raise ValueError(f"Unsupported provider: {provider}")
    
    def _build_assessment_system_prompt(self, questions: list) -> str:
        """Build system prompt for assessment from YAML template."""
        import yaml
        from pathlib import Path
        
        prompt_file = Path("app/static/prompts/assessment.yaml")
        with open(prompt_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        system_prompt = data.get("system", "")
        
        questions_text = "\n".join([f"  {i+1}. {q}" for i, q in enumerate(questions)])
        full_prompt = f"{system_prompt}\n\n**ASSESSMENT QUESTIONS:**\n{questions_text}"
        
        return full_prompt
    
    def _build_user_prompt(
        self, 
        conversation_history: list, 
        visitor_profile: dict,
        rag_context: str = None,
        bot_desc: str = ""
    ) -> str:
        """Build user prompt with conversation, profile, and RAG context."""
        prompt_parts = []
        
        if bot_desc:
            prompt_parts.append("=== BUSINESS GOALS ===")
            prompt_parts.append(bot_desc)
            prompt_parts.append("")
        
        if rag_context:
            prompt_parts.append("=== RELEVANT CONVERSATION CONTEXT (FROM RAG) ===")
            prompt_parts.append(rag_context)
            prompt_parts.append("")
        
        prompt_parts.append("=== VISITOR PROFILE ===")
        basic_info = {
            "name": visitor_profile.get("name", "Unknown"),
            "email": visitor_profile.get("email", "N/A"),
            "phone": visitor_profile.get("phone", "N/A"),
        }
        for key, value in basic_info.items():
            if value:
                prompt_parts.append(f"{key}: {value}")
        
        if "long_term_memory" in visitor_profile and visitor_profile["long_term_memory"]:
            prompt_parts.append("\n=== LONG-TERM MEMORY (Key Information) ===")
            ltm = visitor_profile["long_term_memory"]
            if isinstance(ltm, dict):
                for key, value in ltm.items():
                    prompt_parts.append(f"{key}: {value}")
            else:
                prompt_parts.append(str(ltm))
        
        prompt_parts.append("\nPlease analyze the relevant conversation context above and respond in the EXACT JSON format specified in the system prompt.")
        
        return "\n".join(prompt_parts)
    
    async def _call_openai(
        self, 
        bot_config: Dict[str, Any], 
        system_prompt: str, 
        user_prompt: str
    ) -> Dict[str, Any]:
        """Call OpenAI API."""
        from openai import AsyncOpenAI
        
        api_key = bot_config.get("api_key", "")
        api_base_url = bot_config.get("api_base_url", "")
        model = bot_config.get("model", "gpt-4o-mini")
        temperature = bot_config.get("temperature", 0.3)
        max_tokens = bot_config.get("max_tokens", 1000)
        
        if not api_key:
            raise ValueError("No API key configured for OpenAI")
        
        client = AsyncOpenAI(
            api_key=api_key,
            base_url=api_base_url if api_base_url else None,
        )
        
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"}
            )
            
            raw_content = response.choices[0].message.content
            
            result_json = json.loads(raw_content)
            result_json["model_used"] = model
            
            logger.info(
                f"Parsed OpenAI result: has_results={('results' in result_json)}, "
                f"num_results={len(result_json.get('results', []))}, keys={list(result_json.keys())}"
            )
            
            return result_json
            
        except Exception as e:
            logger.error(f"OpenAI scoring error: {e}", exc_info=True)
            raise
    
    async def _call_gemini(
        self, 
        bot_config: Dict[str, Any], 
        system_prompt: str, 
        user_prompt: str
    ) -> Dict[str, Any]:
        """Call Google Gemini API."""
        import google.generativeai as genai
        
        api_key = bot_config.get("api_key", "")
        model_name = bot_config.get("model", "gemini-1.5-flash")
        temperature = bot_config.get("temperature", 0.3)
        max_tokens = bot_config.get("max_tokens", 1000)
        
        if not api_key:
            raise ValueError("No API key configured for Gemini")
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        try:
            response = await model.generate_content_async(
                full_prompt,
                generation_config={
                    "temperature": temperature,
                    "max_output_tokens": max_tokens,
                }
            )
            
            if not response.candidates or not response.candidates[0].content.parts:
                finish_reason = response.candidates[0].finish_reason if response.candidates else "UNKNOWN"
                logger.warning(f"Gemini response has no content. Finish reason: {finish_reason}")
                
                return {
                    "score": 0,
                    "category": "cold",
                    "intent_signals": [],
                    "engagement_level": "low",
                    "key_interests": [],
                    "recommended_actions": ["Review conversation for content violations"],
                    "reasoning": f"Unable to score - Gemini blocked by safety filter (finish_reason: {finish_reason})",
                    "model_used": model_name
                }
            
            raw_text = response.text
            logger.info(
                "Gemini response received",
                extra={
                    "model": model_name,
                    "raw_response": raw_text[:500]  # Log first 500 chars
                }
            )
            
            result_json = json.loads(raw_text)
            result_json["model_used"] = model_name
            
            logger.info(
                "Parsed Gemini result",
                extra={
                    "has_results": "results" in result_json,
                    "num_results": len(result_json.get("results", [])),
                    "keys": list(result_json.keys())
                }
            )
            
            return result_json
            
        except Exception as e:
            logger.error(f"Gemini scoring error: {e}", exc_info=True)
            raise
    
    async def _call_ollama(
        self, 
        bot_config: Dict[str, Any], 
        system_prompt: str, 
        user_prompt: str
    ) -> Dict[str, Any]:
        """Call Ollama API."""
        import httpx
        
        api_base_url = bot_config.get("api_base_url", "http://localhost:11434")
        model = bot_config.get("model", "llama3.1:8b")
        temperature = bot_config.get("temperature", 0.3)
        max_tokens = bot_config.get("max_tokens", 1000)
        
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
            },
            "stream": False,
            "format": "json"
        }
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                result = response.json()
                
                raw_content = result.get("message", {}).get("content", "{}")
                logger.info(
                    "Ollama response received",
                    extra={
                        "model": model,
                        "raw_response": raw_content[:500]  # Log first 500 chars
                    }
                )
                
                result_json = json.loads(raw_content)
                result_json["model_used"] = model
                
                logger.info(
                    "Parsed Ollama result",
                    extra={
                        "has_results": "results" in result_json,
                        "num_results": len(result_json.get("results", [])),
                        "keys": list(result_json.keys())
                    }
                )
                
                return result_json
                
        except Exception as e:
            logger.error(f"Ollama scoring error: {e}", exc_info=True)
            raise


llm_service = LLMService()

