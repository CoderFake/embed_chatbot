"""Tests for chat worker graph."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))
sys.path.append(str(ROOT / "chat-worker"))

import pytest
from langgraph.store.memory import InMemoryStore

import app.services.chat.graph as graph
import app.services.chat.nodes as nodes
from app.services.chat.graph import route_after_reflection
from app.services.chat.state import ChatState
from app.utils.datetime_utils import now


@pytest.mark.asyncio
async def test_graph_retrieval_flow(monkeypatch):
    """Full RAG path executes when retrieval is required."""

    async def fake_analyze(query: str):
        return {
            "language": "en",
            "confidence": 0.99,
            "intent": "question",
            "needs_retrieval": True,
        }

    async def fake_rewrite(query: str, history):
        return "rewritten question"

    async def fake_search_for_chat(**kwargs):
        return [
            {"content": "Chunk one", "score": 0.2, "web_url": "https://example.com/1", "chunk_index": 1},
            {"content": "Chunk two", "score": 0.1, "web_url": "https://example.com/2", "chunk_index": 2},
        ]

    async def fake_rerank(query: str, chunks, top_n: int | None = None):
        return [
            {"content": "Chunk one", "rerank_score": 0.9, "web_url": "https://example.com/1", "chunk_index": 1},
        ]

    async def fake_complete(*, bot_config, system_prompt, user_prompt):
        assert "Chunk one" in user_prompt
        return "Generated answer"

    async def fake_memory_summary(**kwargs):
        return "- User is interested in documentation"

    monkeypatch.setattr(nodes.reflection_service, "analyze_query", fake_analyze)
    monkeypatch.setattr(nodes.reflection_service, "rewrite_query", fake_rewrite)
    monkeypatch.setattr(nodes.milvus_service, "search_for_chat", fake_search_for_chat)
    monkeypatch.setattr(nodes.reranker_service, "rerank", fake_rerank)
    monkeypatch.setattr(nodes.llm_router, "complete", fake_complete)
    monkeypatch.setattr(nodes.long_term_memory_service, "summarize_user_profile", fake_memory_summary)

    store = InMemoryStore()
    graph.memory_store = store
    local_graph = graph.create_chat_graph(store=store)

    initial_state: ChatState = {
        "query": "Original question",
        "bot_id": "bot-123",
        "session_id": "session-1",
        "conversation_history": [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ],
        "bot_config": {"provider": "openai", "model": "gpt-4"},
        "retrieved_chunks": [],
        "reranked_chunks": [],
        "response": "",
        "response_language": "",
        "sources": [],
        "tokens_used": 0,
        "latency_breakdown": {},
        "error": None,
        "stream_mode": False,
        "started_at": now(),
        "completed_at": None,
        "memory_summary": "",
        "memory_written": False,
    }

    result = await local_graph.ainvoke(initial_state)

    assert result["response"] == "Generated answer"
    assert result["rerank_count"] == 1
    assert result["retrieval_count"] == 2
    assert result["detected_language"] == "en"
    assert result["sources"]
    assert result["memory_written"] is True
    assert "documentation" in result["memory_summary"]

    stored = await store.aget(("long_term_memory", "bot-123"), "session-1")
    assert stored is not None
    assert stored.value["entries"][-1]["summary"].startswith("- User")


@pytest.mark.asyncio
async def test_graph_chitchat_flow(monkeypatch):
    """Chitchat path bypasses retrieval and generation."""

    async def fake_analyze(query: str):
        return {
            "language": "vi",
            "confidence": 1.0,
            "intent": "greeting",
            "needs_retrieval": False,
        }

    async def fake_memory_summary(**kwargs):
        return "No new information"

    monkeypatch.setattr(nodes.reflection_service, "analyze_query", fake_analyze)
    monkeypatch.setattr(nodes.long_term_memory_service, "summarize_user_profile", fake_memory_summary)

    store = InMemoryStore()
    graph.memory_store = store
    local_graph = graph.create_chat_graph(store=store)

    initial_state: ChatState = {
        "query": "Xin chào",
        "bot_id": "bot-123",
        "session_id": "session-1",
        "conversation_history": [],
        "bot_config": {},
        "retrieved_chunks": [],
        "reranked_chunks": [],
        "response": "",
        "response_language": "",
        "sources": [],
        "tokens_used": 0,
        "latency_breakdown": {},
        "error": None,
        "stream_mode": False,
        "started_at": now(),
        "completed_at": None,
        "memory_summary": "",
        "memory_written": False,
    }

    result = await local_graph.ainvoke(initial_state)

    assert result["intent"] == "greeting"
    assert result["needs_retrieval"] is False
    assert result["response"]
    assert result["sources"] == []
    assert result["memory_written"] is False
    assert result["memory_summary"] in ("", "No new information")


def test_route_after_reflection():
    assert route_after_reflection({"needs_retrieval": True}) == "retrieve"
    assert route_after_reflection({"needs_retrieval": False}) == "chitchat"
