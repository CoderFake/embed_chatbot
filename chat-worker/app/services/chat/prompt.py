"""Prompt Manager - Load and manage YAML prompts."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

import yaml

from app.config.settings import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class PromptManager:
    """Manage multi-language prompts from YAML files."""

    def __init__(self) -> None:
        self.prompts_dir = Path(__file__).parent.parent.parent / "static" / "prompts"
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._load_all_prompts()

    def _load_yaml(self, path: Path) -> Dict[str, Any]:
        with open(path, "r", encoding="utf-8") as file:
            return yaml.safe_load(file) or {}

    def _load_all_prompts(self) -> None:
        for lang in settings.supported_languages_list():
            system_path = self.prompts_dir / "system" / f"{lang}.yaml"
            if system_path.exists():
                self._cache[f"system_{lang}"] = self._load_yaml(system_path)
            else:
                logger.warning("System prompt not found: %s", system_path)

        for filename in ("analyzer", "relevance", "groundedness"):
            reflection_path = self.prompts_dir / "reflection" / f"{filename}.yaml"
            if reflection_path.exists():
                self._cache[f"reflection_{filename}"] = self._load_yaml(reflection_path)
            else:
                logger.warning("Reflection prompt not found: %s", reflection_path)

        memory_path = self.prompts_dir / "memory" / "session_summary.yaml"
        if memory_path.exists():
            self._cache["memory_session_summary"] = self._load_yaml(memory_path)
        else:
            logger.warning("Memory prompt not found: %s", memory_path)

        contact_detection_path = self.prompts_dir / "memory" / "contact_detection.yaml"
        if contact_detection_path.exists():
            self._cache["memory_contact_detection"] = self._load_yaml(contact_detection_path)
        else:
            logger.warning("Contact detection prompt not found: %s", contact_detection_path)

        logger.info("Loaded %s prompt templates", len(self._cache))

    def _format_visitor_profile(self, visitor_profile: dict | None) -> str:
        """Format visitor profile data into readable text for prompt injection."""
        if not visitor_profile:
            return "No customer information collected yet."
        
        visitor_fields = settings.visitor_info_fields_list()
        collected_info = []
        
        for field in visitor_fields:
            value = visitor_profile.get(field)
            if value:
                field_display = field.replace('_', ' ').title()
                collected_info.append(f"- {field_display}: {value}")
        
        if not collected_info:
            return "No customer information collected yet."
        
        profile_text = "\n".join(collected_info)
    
        return profile_text

    def get_system_prompt(
        self, 
        language: str, 
        bot_config: dict | None = None, 
        visitor_profile: dict | None = None,
        long_term_memory: str | None = None
    ) -> Dict[str, Any]:
        key = f"system_{language}"
        if key not in self._cache:
            logger.warning("System prompt not found for %s, falling back to default", language)
            key = f"system_{settings.DEFAULT_LANGUAGE}"
        
        prompt_data = self._cache.get(key, {}).copy()
       
        if bot_config:
            bot_name = bot_config.get("name", "AI Assistant")
            bot_desc = bot_config.get("desc", "")
            system_section = prompt_data.get("system", {})
            
            if isinstance(system_section, dict):
                role = system_section.get("role", "")
                instructions = system_section.get("instructions", "")
                
                role = role.format(bot_name=bot_name)
                
                instructions = instructions.replace("{bot_desc}", bot_desc if bot_desc else "")
                
                if visitor_profile is not None:
                    visitor_profile_text = self._format_visitor_profile(visitor_profile)
                    instructions = instructions.replace("{visitor_profile}", visitor_profile_text)
                
                if long_term_memory:
                    instructions = f"{instructions}\n\n**Conversation Context (Previous Summary):**\n{long_term_memory}"
                
                prompt_data["system"] = {"role": role, "instructions": instructions}
            else:
                prompt_text = system_section.format(bot_name=bot_name)
                
                prompt_text = prompt_text.replace("{bot_desc}", bot_desc if bot_desc else "")
                
                if visitor_profile is not None:
                    visitor_profile_text = self._format_visitor_profile(visitor_profile)
                    prompt_text = prompt_text.replace("{visitor_profile}", visitor_profile_text)
                
                if long_term_memory:
                    prompt_text = f"{prompt_text}\n\n**Conversation Context (Previous Summary):**\n{long_term_memory}"
                
                prompt_data["system"] = prompt_text
        else:
            if visitor_profile is not None:
                system_section = prompt_data.get("system", {})
                if isinstance(system_section, dict):
                    instructions = system_section.get("instructions", "")
                    visitor_profile_text = self._format_visitor_profile(visitor_profile)
                    instructions = instructions.replace("{visitor_profile}", visitor_profile_text)
                    
                    if long_term_memory:
                        instructions = f"{instructions}\n\n**Conversation Context (Previous Summary):**\n{long_term_memory}"
                    
                    system_section["instructions"] = instructions
                    prompt_data["system"] = system_section
                else:
                    visitor_profile_text = self._format_visitor_profile(visitor_profile)
                    prompt_text = system_section.replace("{visitor_profile}", visitor_profile_text)
                    
                    if long_term_memory:
                        prompt_text = f"{prompt_text}\n\n**Conversation Context (Previous Summary):**\n{long_term_memory}"
                    
                    prompt_data["system"] = prompt_text
        
        return prompt_data

    def get_reflection_analyzer_prompt(self) -> str:
        reflection = self._cache.get("reflection_analyzer", {})
        return reflection.get("system", "")

    def get_reflection_relevance_prompt(self) -> Dict[str, str]:
        """Get relevance check prompts (system + template)."""
        reflection = self._cache.get("reflection_relevance", {})
        return {
            "system": reflection.get("system", ""),
            "template": reflection.get("template", "Question: {query}\n\nContext: {context}\n\nRelevance score:"),
        }

    def get_reflection_groundedness_prompt(self) -> Dict[str, str]:
        """Get groundedness check prompts (system + template)."""
        reflection = self._cache.get("reflection_groundedness", {})
        return {
            "system": reflection.get("system", ""),
            "template": reflection.get("template", "Context: {context}\n\nResponse: {response}\n\nGroundedness score:"),
        }

    def format_reflection_analyzer(
        self,
        query: str,
        visitor_profile: dict | None = None,
        long_term_memory: str | None = None,
        conversation_history: List[Dict[str, str]] | None = None,
    ) -> str:
        """
        Format reflection analyzer prompt with full context.

        Template expects: conversation_history, visitor_profile, long_term_memory, query
        """
        reflection = self._cache.get("reflection_analyzer", {})
        template = reflection.get("template", "Query: {query}\n\nAnalysis:")

        history_text = "(No previous conversation)"
        if conversation_history and len(conversation_history) > 0:
            history_text = self._format_history(conversation_history[-5:], limit=None)

        profile_text = self._format_visitor_profile(visitor_profile)

        memory_text = long_term_memory if long_term_memory else "(No long-term memory)"

        return template.format(
            conversation_history=history_text,
            visitor_profile=profile_text,
            long_term_memory=memory_text,
            query=query,
        )

    def _format_history(
        self,
        conversation_history: List[Dict[str, str]],
        *,
        limit: int | None = 3,
    ) -> str:
        if not conversation_history:
            return "(No previous conversation)"
        lines: List[str] = []
        history = conversation_history[-limit:] if limit else conversation_history
        for message in history:
            role = message.get("role", "user")
            content = message.get("content", "")
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    def format_retrieval_prompt(
        self,
        language: str,
        query: str,
        context: str,
        bot_config: dict | None = None,
    ) -> str:
        """
        Format retrieval prompt with context and query only.

        visitor_profile and long_term_memory are already in system_prompt.
        conversation_history is handled by followup_action.
        """
        system_prompt = self.get_system_prompt(language, bot_config)
        template = system_prompt.get("retrieval_template", "Context:\n{context}\n\nQuestion: {query}\n\nAnswer:")

        return template.format(context=context, query=query)

    def get_chitchat_response(self, language: str, intent: str, bot_config: dict | None = None) -> str:
        """
        Get chitchat fallback response with bot_name injection.

        Args:
            language: Language code
            intent: Chitchat intent (greeting, thanks, goodbye, default)
            bot_config: Bot configuration containing bot name

        Returns:
            Chitchat response with bot_name replaced
        """
        system_prompt = self.get_system_prompt(language)
        chitchat = system_prompt.get("chitchat", {})
        response = chitchat.get(intent, chitchat.get("default", "Hello!"))

        if bot_config:
            bot_name = bot_config.get("name", "AI Assistant")
            response = response.replace("{bot_name}", bot_name)

        return response

    def get_memory_prompt(self) -> Dict[str, Any]:
        return self._cache.get("memory_session_summary", {})
    
    def get_contact_detection_prompt(self) -> Dict[str, str]:
        """Get contact detection prompts (system + template)."""
        contact = self._cache.get("memory_contact_detection", {})
        return {
            "system": contact.get("system", ""),
            "template": contact.get("template", "Query: {query}\n\nRewritten Query: {rewritten_query}\n\nConversation History:\n{conversation_history}\n\nDoes the user want to be contacted?"),
        }
    
    def format_contact_detection_prompt(
        self,
        query: str,
        rewritten_query: str,
        conversation_history: List[Dict[str, str]],
    ) -> str:
        """Format contact detection prompt with conversation context."""
        contact = self._cache.get("memory_contact_detection", {})
        template = contact.get("template", "Query: {query}\n\nRewritten Query: {rewritten_query}\n\nConversation History:\n{history}\n\nDoes the user want to be contacted?")
        
        history_text = self._format_history(conversation_history[-5:], limit=None) if conversation_history else "(No previous conversation)"
        
        return template.format(
            query=query,
            rewritten_query=rewritten_query,
            history=history_text,
        )

    def format_memory_prompt(
        self,
        conversation_history: List[Dict[str, str]],
        query: str,
        response: str,
    ) -> str:
        """Format initial memory prompt - process last 10 messages."""
        memory = self._cache.get("memory_session_summary", {})
        template = memory.get(
            "template",
            "Conversation transcript (last 10 messages):\n{transcript}\n\nSummarise enduring user details in 3 bullet points."
        )
        
        recent_history = conversation_history[-10:] if len(conversation_history) > 10 else conversation_history
        transcript_history = self._format_history(recent_history, limit=None)
        
        transcript = "\n".join(
            part
            for part in [
                transcript_history if transcript_history else "(No previous conversation)",
                f"user: {query}" if query else "",
                f"assistant: {response}" if response else "",
            ]
            if part
        )
        return template.format(transcript=transcript)
    
    def format_memory_prompt_incremental(
        self,
        previous_summary: str,
        recent_messages: List[Dict[str, str]],
        query: str,
        response: str,
    ) -> str:
        """Format incremental memory update prompt - merge last 10 messages with existing summary."""
        memory = self._cache.get("memory_session_summary", {})
        incremental_template = memory.get(
            "incremental_template",
            "**Existing user summary:**\n{previous_summary}\n\n**New conversation (last 10 messages):**\n{new_transcript}\n\n**Updated summary:**"
        )
        
        last_10 = recent_messages[-10:] if len(recent_messages) > 10 else recent_messages
        recent_transcript = self._format_history(last_10, limit=None)
        
        new_exchange = []
        if query:
            new_exchange.append(f"user: {query}")
        if response:
            new_exchange.append(f"assistant: {response}")
        
        new_transcript = "\n".join([recent_transcript] + new_exchange) if recent_transcript else "\n".join(new_exchange)
        
        return incremental_template.format(
            previous_summary=previous_summary,
            new_transcript=new_transcript
        )

    def reload(self) -> None:
        self._cache.clear()
        self._load_all_prompts()
        logger.info("Prompts reloaded")


@lru_cache()
def _get_prompt_manager() -> PromptManager:
    return PromptManager()


prompt_manager = _get_prompt_manager()
