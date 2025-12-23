"""LangGraph workflow for chat system."""
from __future__ import annotations

from langgraph.graph import END, StateGraph
from langgraph.store.base import BaseStore
from langgraph.store.memory import InMemoryStore

from app.utils.datetime_utils import now

from app.services.provider import chat_provider_service
from app.services.chat.nodes import (
    chitchat_node,
    memory_node,
    generate_node,
    reflection_node,
    retrieve_node,
    final_node,
)
from app.services.chat.state import ChatState


def route_after_reflection(state: ChatState) -> str:
    """Decide next node after reflection."""
    return "retrieve" if state.get("needs_retrieval", True) else "chitchat"


memory_store: BaseStore = InMemoryStore()


def create_chat_graph(*, store: BaseStore | None = None) -> StateGraph:
    workflow = StateGraph(ChatState)
    workflow.add_node("reflection", reflection_node)
    workflow.add_node("chitchat", chitchat_node)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("generate", generate_node)
    workflow.add_node("memory", memory_node)
    workflow.add_node("final", final_node)

    workflow.set_entry_point("reflection")
    workflow.add_conditional_edges(
        "reflection",
        route_after_reflection,
        {
            "chitchat": "chitchat",
            "retrieve": "retrieve",
        },
    )

    workflow.add_edge("chitchat", "memory")
    workflow.add_edge("retrieve", "generate") 
    workflow.add_edge("generate", "memory")
    workflow.add_edge("memory", "final")
    workflow.add_edge("final", END)

    selected_store = store or memory_store
    return workflow.compile(store=selected_store)


async def prepare_initial_state(
    *,
    task_id: str,
    query: str,
    bot_id: str,
    session_token: str,
    conversation_history: list,
    visitor_profile: dict,
    long_term_memory: str | None = None,
    stream_mode: bool = False,
) -> ChatState:
    """Prepare initial chat state with configuration and key rotation."""
    bot_config = await chat_provider_service.get_bot_config_with_key_selection(bot_id)
    
    if not bot_config:
        raise ValueError(f"Failed to load bot configuration for bot_id={bot_id}")
    
    key_index = bot_config.get("key_index")

    return ChatState(
        task_id=task_id,
        query=query,
        bot_id=bot_id,
        session_id=session_token,
        conversation_history=conversation_history,
        bot_config=bot_config,
        key_index=key_index,
        visitor_profile=visitor_profile,
        long_term_memory=long_term_memory,
        detected_language="",
        language_confidence=0.0,
        intent="",
        needs_retrieval=True,
        rewritten_query="",
        retrieved_chunks=[],
        retrieval_count=0,
        reranked_chunks=[],
        rerank_count=0,
        response="",
        response_language="",
        sources=[],
        tokens_input=0,
        tokens_output=0,
        tokens_used=0,
        cost_usd=0.0,
        latency_breakdown={},
        error=None,
        stream_mode=stream_mode,
        started_at=now(),
        completed_at=None,
        memory_summary="",
        memory_written=False,
        is_contact=visitor_profile.get("is_contact", False),
    )


chat_graph = create_chat_graph()
