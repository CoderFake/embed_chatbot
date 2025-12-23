"""Long-term memory writer built on LangGraph stores."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from langgraph.config import get_store
from langgraph.store.base import BaseStore

from app.utils.logging import get_logger
from app.utils.datetime_utils import now
from app.services.chat.prompt import prompt_manager
from app.services.chat.llm_router import llm_router

if TYPE_CHECKING:
    from app.services.chat.state import ChatState


logger = get_logger(__name__)


class LongTermMemoryService:
    """Persist user-focused summaries for future sessions."""

    def __init__(self, *, namespace_root: tuple[str, ...] | None = None) -> None:
        self.namespace_root = namespace_root or ("long_term_memory",)

    async def summarize_user_profile(
        self,
        *,
        bot_config: Dict[str, Any],
        conversation_history: List[Dict[str, str]],
        query: str,
        response: str,
        previous_summary: str | None = None,
        visitor_profile: Dict | None = None,
    ) -> str:
        """Use the LLM router to extract durable facts about the user.
        
        Strategy: Always process last 10 messages + current exchange
        - If previous_summary exists: Incremental merge mode
        - If no previous_summary: Initial summary mode
        - Priority: Use visitor_profile fields if available (already extracted by reflection)
        
        Args:
            bot_config: Bot configuration for LLM
            conversation_history: Full conversation history
            query: Current user query
            response: Current bot response
            previous_summary: Existing summary to update (incremental mode)
            visitor_profile: Current visitor profile from state (with extracted info)
        
        Returns:
            Updated summary as bullet points
        """
        summary_parts = []
        if visitor_profile:
            if visitor_profile.get("name"):
                summary_parts.append(f"- Name: {visitor_profile['name']}")
            if visitor_profile.get("email"):
                summary_parts.append(f"- Email: {visitor_profile['email']}")
            if visitor_profile.get("phone"):
                summary_parts.append(f"- Phone: {visitor_profile['phone']}")
            if visitor_profile.get("address"):
                summary_parts.append(f"- Address: {visitor_profile['address']}")
        
        if summary_parts:
            logger.info(f"Using visitor_profile fields in memory: {', '.join(summary_parts)}")
            
            memory_prompt = prompt_manager.get_memory_prompt()
            system_prompt = memory_prompt.get("system", "")
            
            if previous_summary:
                user_prompt = prompt_manager.format_memory_prompt_incremental(
                    previous_summary=previous_summary,
                    recent_messages=conversation_history, 
                    query=query,
                    response=response,
                )
            else:
                user_prompt = prompt_manager.format_memory_prompt(
                    conversation_history=conversation_history,
                    query=query,
                    response=response,
                )
            
            result = await llm_router.complete(
                bot_config=bot_config,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            llm_summary = result.get("text", "").strip()
            
            if llm_summary and llm_summary.lower() not in ("no new information", "no update needed"):
                llm_lines = [line for line in llm_summary.split('\n') if line.strip().startswith('-')]
                non_contact_lines = []
                for line in llm_lines:
                    lower_line = line.lower()
                    if not any(x in lower_line for x in ['name:', 'email:', 'phone:', 'address:']):
                        non_contact_lines.append(line)
                
                summary_parts.extend(non_contact_lines)
            
            return '\n'.join(summary_parts) if summary_parts else "No new information"
        
        memory_prompt = prompt_manager.get_memory_prompt()
        system_prompt = memory_prompt.get("system", "")
        
        if previous_summary:
            user_prompt = prompt_manager.format_memory_prompt_incremental(
                previous_summary=previous_summary,
                recent_messages=conversation_history, 
                query=query,
                response=response,
            )
        else:
            user_prompt = prompt_manager.format_memory_prompt(
                conversation_history=conversation_history,
                query=query,
                response=response,
            )
        
        result = await llm_router.complete(
            bot_config=bot_config,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        summary_text = result.get("text", "").strip()
        return summary_text

    async def _ensure_store(self) -> Optional[BaseStore]:
        try:
            return get_store()
        except RuntimeError:
            logger.warning("Long-term memory store is not configured")
            return None

    async def detect_contact_request(
        self,
        *,
        bot_config: Dict[str, Any],
        query: str,
        rewritten_query: str,
        conversation_history: List[Dict[str, str]],
        previous_summary: str | None = None,
        is_contact: bool = False,
    ) -> bool:
        """Use LLM to detect if user requests to be contacted.
        
        Args:
            bot_config: Bot configuration for LLM
            query: Original user query
            rewritten_query: Rewritten query from reflection
            conversation_history: Full conversation history
            previous_summary: Previous long-term memory summary
            is_contact: Current session's is_contact status from DB
            
        Returns:
            True if contact request detected AND is_contact is False, False otherwise
        """
        # Check session's is_contact state first
        if is_contact:
            logger.info("Session is_contact already True, skipping contact detection")
            return False
        
        if previous_summary and "- Contact Requested: Yes" in previous_summary:
            logger.info("Contact already requested in previous summary, skipping")
            return False
        
        try:
            contact_prompts = prompt_manager.get_contact_detection_prompt()
            system_prompt = contact_prompts.get("system", "")
            user_prompt = prompt_manager.format_contact_detection_prompt(
                query=query,
                rewritten_query=rewritten_query,
                conversation_history=conversation_history
            )
            
            result = await llm_router.complete(
                bot_config=bot_config,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            answer = result.get("text", "").strip().upper()
            
            is_contact = answer.startswith("YES")
            logger.info(f"LLM contact detection: {answer} → is_contact={is_contact}")
            return is_contact
            
        except Exception as e:
            logger.error(f"Failed to detect contact request via LLM: {e}", exc_info=True)
            return False

    def _build_entry(
        self,
        *,
        summary: str,
        state: "ChatState",
        is_contact: bool = False,
    ) -> Dict[str, Any]:
        return {
            "summary": summary,
            "query": state.get("query", ""),
            "response": state.get("response", ""),
            "language": state.get("detected_language", ""),
            "intent": state.get("intent", ""),
            "is_contact": is_contact,
            "captured_at": now().isoformat(),
        }

    async def write_memory(self, state: "ChatState") -> Optional[Dict[str, Any]]:
        """Persist the latest session information into the configured store."""
        store = await self._ensure_store()
        if not store:
            return None

        namespace = self.namespace_root + (state.get("bot_id", "default"),)
        key = state.get("session_id", "session")
        existing = await store.aget(namespace, key)
        
        previous_summary = None
        if existing and isinstance(existing.value, dict):
            entries = existing.value.get("entries", [])
            if entries and isinstance(entries, list) and len(entries) > 0:
                previous_summary = entries[-1].get("summary")

        summary = await self.summarize_user_profile(
            bot_config=state.get("bot_config", {}),
            conversation_history=state.get("conversation_history", []),
            query=state.get("query", ""),
            response=state.get("response", ""),
            previous_summary=previous_summary,
            visitor_profile=state.get("visitor_profile", {}),
        )
        
        current_is_contact = state.get("is_contact", False)
        
        is_contact = await self.detect_contact_request(
            bot_config=state.get("bot_config", {}),
            query=state.get("query", ""),
            rewritten_query=state.get("rewritten_query", state.get("query", "")),
            conversation_history=state.get("conversation_history", []),
            previous_summary=previous_summary,
            is_contact=current_is_contact,
        )
        
        visitor_profile = state.get("visitor_profile", {}) or {}
        has_contact_info = bool(visitor_profile.get("phone") or visitor_profile.get("email"))
        
        if is_contact and summary and has_contact_info:
            if "Contact Requested:" not in summary:
                summary += "\n- Contact Requested: Yes"
                logger.info(f"Added contact request marker (has_contact_info: phone={bool(visitor_profile.get('phone'))}, email={bool(visitor_profile.get('email'))})")
        elif is_contact and not has_contact_info:
            logger.info("User wants contact but no phone/email yet, skipping marker")
        
        if not summary:
            logger.info("Skipping long-term memory write: empty summary")
            return None
        if summary.strip().lower() in ("no new information", "no update needed", "no changes"):
            logger.info("Skipping long-term memory write: no new user information")
            return None

        entry = self._build_entry(summary=summary, state=state, is_contact=is_contact)

        entries: List[Dict[str, Any]] = []
        if existing and isinstance(existing.value, dict):
            previous = existing.value.get("entries")
            if isinstance(previous, list):
                entries = list(previous)

        entries.append(entry)
        entries = entries[-20:]

        await store.aput(
            namespace,
            key,
            {"entries": entries},
            index=["entries[*].summary", "entries[*].query", "entries[*].intent"],
        )
        logger.info(
            "Updated long-term memory", extra={
                "namespace": namespace, 
                "key": key, 
                "entries": len(entries),
                "is_contact": is_contact
            }
        )
        return {"entries": entries, "latest": entry}


long_term_memory_service = LongTermMemoryService()
