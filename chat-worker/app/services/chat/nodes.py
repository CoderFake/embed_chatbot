"""LangGraph nodes (workflow steps)."""
from __future__ import annotations

import time
import json
import asyncio
from app.config.settings import settings
from app.core.service_manager import service_manager
from app.core.keys import ChatKeys
from app.services.chat.llm_router import llm_router
from app.services.provider import chat_provider_service
from app.services.chat.memory import long_term_memory_service
from app.services.chat.metrics import log_latency_breakdown
from app.services.chat.prompt import prompt_manager
from app.services.chat.reflection import reflection_service, ReflectionCounter
from app.services.chat.reranker import reranker_service
from app.services.key_rotation import key_rotation_service
from app.services.llm import RateLimitError
from app.services.milvus import milvus_service
from app.utils.datetime_utils import now
from app.utils.logging import get_logger

from .state import ChatState

logger = get_logger(__name__)


async def reflection_node(state: ChatState) -> ChatState:
    """Analyse query for language, intent, and query rewriting."""
    start = time.perf_counter()
    query = state.get("query", "")
    conversation_history = state.get("conversation_history", [])
    visitor_profile = state.get("visitor_profile", {}) or {}
    long_term_memory = state.get("long_term_memory")
    bot_config = state.get("bot_config", {})

    analysis = await reflection_service.analyze_query(
        query=query, 
        visitor_profile=visitor_profile, 
        long_term_memory=long_term_memory, 
        bot_config=bot_config,
        conversation_history=conversation_history,
    )
    
    extracted_visitor_info = analysis.get("visitor_info")
    if extracted_visitor_info:
        logger.info(f"Reflection extracted visitor_info: {extracted_visitor_info}")
       
        if isinstance(extracted_visitor_info, dict):
            updated_fields = []
            for field in ["name", "email", "phone", "address"]:
                if extracted_visitor_info.get(field) and extracted_visitor_info[field] != visitor_profile.get(field):
                    old_value = visitor_profile.get(field)
                    visitor_profile[field] = extracted_visitor_info[field]
                    updated_fields.append(f"{field}: {old_value} → {extracted_visitor_info[field]}")
            
            if updated_fields:
                state["visitor_profile"] = visitor_profile
                logger.info(f"Updated visitor_profile in reflection: {', '.join(updated_fields)}")
        else:
            logger.error(f"visitor_info has unexpected type: {type(extracted_visitor_info)}")
    else:
        logger.debug("No visitor_info extracted from reflection")
    
    state["detected_language"] = analysis.get("language", settings.DEFAULT_LANGUAGE)
    state["language_confidence"] = float(analysis.get("confidence", 0.0))
    state["intent"] = analysis.get("intent", "question")
    state["needs_retrieval"] = bool(analysis.get("needs_retrieval", True))
    state["rewritten_query"] = analysis.get("rewritten_query", query)
    state["followup_action"] = analysis.get("followup_action", "")

    latency = (time.perf_counter() - start) * 1000
    state.setdefault("latency_breakdown", {})["reflection"] = latency
    logger.info(
        "Reflection complete",
        extra={
            "language": state["detected_language"],
            "intent": state["intent"],
            "needs_retrieval": state["needs_retrieval"],
            "visitor_profile": state.get("visitor_profile", {}),
            "latency_ms": latency,
        },
    )
    return state


async def chitchat_node(state: ChatState) -> ChatState:
    start = time.perf_counter()

    language = state.get("detected_language", settings.DEFAULT_LANGUAGE)
    intent = state.get("intent", "default")
    query = state.get("query", "")
    bot_config = state.get("bot_config", {})
    visitor_profile = state.get("visitor_profile", {})
    long_term_memory = state.get("long_term_memory")
    followup_action = state.get("followup_action", "")
    stream_mode = state.get("stream_mode", False)
    
    system_prompt_data = prompt_manager.get_system_prompt(language, bot_config, visitor_profile, long_term_memory)
    system_prompt = system_prompt_data.get("system", "")

    if isinstance(system_prompt, dict):
        system_prompt = f"{system_prompt.get('role', '')}\n\n{system_prompt.get('instructions', '')}"

    if followup_action:
        followup_instruction = "\n\n**SUGGESTED FOLLOWUP ACTION:**\n"
        followup_instruction += f"{followup_action}\n"
        followup_instruction += "\n**Execute this action AFTER answering the user's question (if they have one).**\n"
        followup_instruction += f"**Response language: {language}**\n"
        system_prompt += followup_instruction

    user_prompt = f"User message: {query}\n\nPlease respond naturally in a {intent} tone."

    try:
        if stream_mode:
            
            redis = service_manager.get_redis()
            task_id = state.get("task_id", "")
            stream_key = ChatKeys.task_progress_channel(task_id)

            full_response = []
            async for token in llm_router.stream(
                bot_config=bot_config,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            ):
                full_response.append(token)
                
                await redis.publish(stream_key, json.dumps({
                    "type": "token",
                    "data": {"token": token}
                }))
            
            response_text = "".join(full_response)
            
            await redis.publish(stream_key, json.dumps({
                "type": "done",
                "data": {"response": response_text}
            }))
            
            tokens_output = len(response_text.split())
            tokens_input = 0
            cost_usd = 0.0
        else:
            response_data = await llm_router.complete(
                bot_config=bot_config,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            
            response_text = response_data.get("text", "")
            tokens_input = response_data.get("tokens_input", 0)
            tokens_output = response_data.get("tokens_output", 0)
            cost_usd = response_data.get("cost_usd", 0.0)
        
        state["response"] = response_text
        state["tokens_input"] = tokens_input
        state["tokens_output"] = tokens_output
        state["tokens_used"] = tokens_input + tokens_output
        state["cost_usd"] = cost_usd
        
    except Exception as e:
        logger.error(f"Chitchat LLM failed: {e}", exc_info=True)
        state["error"] = f"Chitchat failed: {str(e)}"

        state["response"] = prompt_manager.get_chitchat_response(language, intent, bot_config)
        state["tokens_input"] = 0
        state["tokens_output"] = 0
        state["tokens_used"] = 0
        state["cost_usd"] = 0.0

    state["response_language"] = language
    state["sources"] = []

    latency = (time.perf_counter() - start) * 1000
    state.setdefault("latency_breakdown", {})["generate"] = latency
    logger.info("Chitchat response", extra={"language": language, "intent": intent, "latency_ms": latency, "stream_mode": stream_mode})
    return state


async def retrieve_node(state: ChatState) -> ChatState:
    """Two-stage adaptive retrieval based on confidence."""
    start = time.perf_counter()

    needs_retrieval = state.get("needs_retrieval", False)
    if not needs_retrieval:
        logger.info("Skipping retrieval (chitchat mode)")
        state["retrieved_chunks"] = []
        state["retrieval_count"] = 0
        state["retrieval_stage"] = "skipped"
        return state

    query = state.get("rewritten_query") or state.get("query", "")
    bot_id = state.get("bot_id")
    
    # Stage 1: Fast initial retrieval
    logger.info(f"Stage 1: Retrieving top {settings.RETRIEVAL_STAGE1_TOP_K} chunks")
    try:
        collection_name = f"bot_{bot_id}".replace("-", "_")
        logger.info(f"Searching collection: {collection_name}")
        
        chunks_stage1 = await milvus_service.search_for_chat(
            collection_name=collection_name,
            query_text=query,
            top_k=settings.RETRIEVAL_STAGE1_TOP_K,
            use_cache=True,
        )
        
        logger.info(f"Stage 1 search returned {len(chunks_stage1) if chunks_stage1 else 0} chunks")
        
        if not chunks_stage1:
            logger.warning("Stage 1: No chunks found")
            state["retrieved_chunks"] = []
            state["retrieval_count"] = 0
            state["retrieval_stage"] = "stage1_empty"
            return state
        
        # Stage 1 reranking
        reranked_stage1 = await reranker_service.rerank(
            query=query,
            chunks=chunks_stage1,
            top_n=settings.RERANKER_STAGE1_TOP_N,
        )
        
        if reranked_stage1:
            avg_confidence = sum(c.get("rerank_score", 0.0) for c in reranked_stage1) / len(reranked_stage1)
        else:
            avg_confidence = 0.0
        
        confidence_threshold = 0.8 if not settings.RERANK_MODE else settings.RETRIEVAL_CONFIDENCE_THRESHOLD
        
        logger.info(f"Stage 1 confidence: {avg_confidence:.3f} (threshold: {confidence_threshold}, mode: {'2-stage' if settings.RERANK_MODE else '1-stage'})")
        
        if not settings.RERANK_MODE:
            logger.info(f"✓ Single-stage mode: returning {len(reranked_stage1)} chunks (confidence={avg_confidence:.3f})")
            state["retrieved_chunks"] = reranked_stage1
            state["retrieval_count"] = len(reranked_stage1)
            state["retrieval_stage"] = "stage1_only"
            state["retrieval_confidence"] = avg_confidence
            latency = (time.perf_counter() - start) * 1000
            state.setdefault("latency_breakdown", {})["retrieval"] = latency
            logger.info(f"Retrieval complete (1-stage mode)", extra={"count": len(reranked_stage1), "latency_ms": latency})
            return state
        
        if avg_confidence >= confidence_threshold:
            logger.info(f"Stage 1 sufficient ({len(reranked_stage1)} chunks, confidence={avg_confidence:.3f})")
            state["retrieved_chunks"] = reranked_stage1
            state["retrieval_count"] = len(reranked_stage1)
            state["retrieval_stage"] = "stage1"
            state["retrieval_confidence"] = avg_confidence
            latency = (time.perf_counter() - start) * 1000
            state.setdefault("latency_breakdown", {})["retrieval"] = latency
            logger.info(f"Retrieval complete (Stage 1 only)", extra={"count": len(reranked_stage1), "latency_ms": latency})
            return state
        
        logger.info(f"Stage 1 low confidence ({avg_confidence:.3f}), expanding to Stage 2")
        chunks_stage2 = await milvus_service.search_for_chat(
            collection_name=collection_name,
            query_text=query,
            top_k=settings.RETRIEVAL_STAGE2_TOP_K,
            use_cache=True,
        )
        
        reranked_stage2 = await reranker_service.rerank(
            query=query,
            chunks=chunks_stage2,
            top_n=settings.RERANKER_STAGE2_TOP_N,
        )
        
        if reranked_stage2:
            avg_confidence_s2 = sum(c.get("rerank_score", 0.0) for c in reranked_stage2) / len(reranked_stage2)
        else:
            avg_confidence_s2 = 0.0
        
        logger.info(f"Stage 2 complete ({len(reranked_stage2)} chunks, confidence={avg_confidence_s2:.3f})")
        
        state["retrieved_chunks"] = reranked_stage2
        state["retrieval_count"] = len(reranked_stage2)
        state["retrieval_stage"] = "stage2"
        state["retrieval_confidence"] = avg_confidence_s2
        
    except Exception as e:
        logger.error("Retrieval failed: %s", e, exc_info=True)
        state["retrieved_chunks"] = []
        state["retrieval_count"] = 0
        state["retrieval_stage"] = "failed" 
        state["error"] = f"Retrieval failed: {e}"

    latency = (time.perf_counter() - start) * 1000
    state.setdefault("latency_breakdown", {})["retrieval"] = latency
    logger.info("Retrieval complete", extra={
        "stage": state.get("retrieval_stage"),
        "count": state.get("retrieval_count"),
        "confidence": state.get("retrieval_confidence", 0),
        "latency_ms": latency
    })
    return state


async def generate_node(state: ChatState) -> ChatState:
    """
    Generate final response using LLM with streaming support.
    If stream_mode=True, streams chunks to Redis for SSE delivery.
    """
    start = time.perf_counter()

    language = state.get("detected_language", settings.DEFAULT_LANGUAGE)
    query = state.get("query", "")
    bot_config = state.get("bot_config", {})
    bot_id = state.get("bot_id", "")
    key_index = state.get("key_index")
    chunks = state.get("retrieved_chunks", [])
    visitor_profile = state.get("visitor_profile", {})
    long_term_memory = state.get("long_term_memory")
    stream_mode = state.get("stream_mode", False)
    session_id = state.get("session_id", "")

    context_lines = [f"[{idx + 1}] {chunk.get('content', '').strip()}" for idx, chunk in enumerate(chunks)]
    context = "\n\n".join(context_lines)

    logger.info(f"Generate_node using visitor_profile: {visitor_profile}")
    
    system_prompt_data = prompt_manager.get_system_prompt(language, bot_config, visitor_profile, long_term_memory)
    system_prompt = system_prompt_data.get("system", "")
    
    if isinstance(system_prompt, dict):
        system_prompt = f"{system_prompt.get('role', '')}\n\n{system_prompt.get('instructions', '')}"
    
    followup_action = state.get("followup_action", "")

    if followup_action:
        followup_instruction = "\n\n**SUGGESTED FOLLOWUP ACTION:**\n"
        followup_instruction += f"{followup_action}\n"
        followup_instruction += "\n**Execute this action AFTER answering the user's question (if they have one).**\n"
        followup_instruction += f"**Response language: {language}**\n"
        system_prompt += followup_instruction

    user_prompt = prompt_manager.format_retrieval_prompt(
        language=language,
        query=query,
        context=context,
        bot_config=bot_config,
    )

    sources = [
        {
            "content": chunk.get("content", ""),
            "source": chunk.get("web_url", ""),
            "score": float(chunk.get("rerank_score", chunk.get("score", 0.0))),
            "chunk_index": chunk.get("chunk_index", 0),
        }
        for chunk in chunks[:5]
    ]

    max_retries = 2
    response_text = ""
    tokens_input = 0
    tokens_output = 0
    cost_usd = 0.0

    for attempt in range(max_retries + 1):
        try:
            if stream_mode:
                
                redis = service_manager.get_redis()
                task_id = state.get("task_id", "")
                stream_key = ChatKeys.task_progress_channel(task_id)
                
                if sources:
                    await redis.publish(stream_key, json.dumps({
                        "type": "sources",
                        "data": {"sources": sources}
                    }))
                
                full_response = []
                token_count = 0
                
                try:
                    async with asyncio.timeout(60.0):
                        async for token in llm_router.stream(
                            bot_config=bot_config,
                            system_prompt=system_prompt,
                            user_prompt=user_prompt,
                        ):
                            full_response.append(token)
                            token_count += 1

                            await redis.publish(stream_key, json.dumps({
                                "type": "token",
                                "data": {"token": token}
                            }))
                except asyncio.TimeoutError:
                    logger.error(f"LLM streaming timeout after 60s, attempt {attempt + 1}/{max_retries + 1}")
                    if attempt < max_retries:
                        continue
                    raise Exception("LLM streaming timed out after all retries")
                
                response_text = "".join(full_response)
                
                await redis.publish(stream_key, json.dumps({
                    "type": "done",
                    "data": {"response": response_text}
                }))
                
                tokens_output = len(response_text.split()) 
                
            else:
                response_data = await llm_router.complete(
                    bot_config=bot_config,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                )
                response_text = response_data.get("text", "")
                tokens_input = response_data.get("tokens_input", 0)
                tokens_output = response_data.get("tokens_output", 0)
                cost_usd = response_data.get("cost_usd", 0.0)
            
            break
        
        except RateLimitError:
            if key_index is not None:
                await key_rotation_service.mark_key_rate_limited(bot_id, key_index)
                logger.warning(
                    f"Rate limit hit, marked key {key_index} as rate-limited",
                    extra={"bot_id": bot_id, "key_index": key_index, "attempt": attempt + 1}
                )
            
            if attempt < max_retries:
                new_config = await chat_provider_service.get_bot_config_with_key_selection(bot_id)
                if new_config:
                    bot_config = new_config
                    key_index = new_config.get("key_index")
                    state["bot_config"] = bot_config
                    state["key_index"] = key_index
                    logger.info(
                        f"Retrying with new API key (index={key_index})",
                        extra={"bot_id": bot_id, "attempt": attempt + 2}
                    )
                else:
                    state["error"] = "All API keys are rate-limited"
                    state["response"] = "I'm currently experiencing high traffic. Please try again in a moment."
                    return state
            else:
                state["error"] = f"Rate limit exceeded after {max_retries + 1} attempts"
                state["response"] = "I'm currently experiencing high traffic. Please try again in a moment."
                return state
        
        except Exception as e:
            logger.error(f"LLM generation failed: {e}", exc_info=True)
            state["error"] = f"Generation failed: {str(e)}"
            state["response"] = "I'm having trouble generating a response. Please try again."
            return state
    
    if not response_text:
        state["error"] = "No response from LLM"
        state["response"] = "I'm having trouble generating a response. Please try again."
        return state

    if context and getattr(settings, "ENABLE_GROUNDEDNESS_CHECK", False):
        try:
            counter = ReflectionCounter(max_loops=getattr(settings, "GROUNDEDNESS_MAX_LOOPS", 2))
            final_response, is_grounded, score = await reflection_service.check_response_groundedness(
                response=response_text,
                context=context,
                bot_config=bot_config,
                reflection_counter=counter,
                threshold=getattr(settings, "GROUNDEDNESS_THRESHOLD", 1),
            )
            
            logger.info(f"Groundedness check: score={score}, is_grounded={is_grounded}")
            
            if is_grounded and final_response != response_text:
                logger.info("Using regenerated response (more grounded)")
                response_text = final_response
            elif not is_grounded:
                logger.warning(f"Response not fully grounded (score={score}), using best effort")
        except Exception as e:
            logger.error(f"Groundedness check failed: {e}")

    state["response"] = response_text
    state["response_language"] = language
    state["tokens_input"] = tokens_input
    state["tokens_output"] = tokens_output
    state["tokens_used"] = tokens_input + tokens_output 
    state["cost_usd"] = cost_usd
    state["sources"] = sources

    latency = (time.perf_counter() - start) * 1000
    state.setdefault("latency_breakdown", {})["generate"] = latency
    logger.info("Generation complete", extra={
        "latency_ms": latency, 
        "tokens": state["tokens_used"],
        "stream_mode": stream_mode
    })

    log_latency_breakdown(state)
    return state


async def memory_node(state: ChatState) -> ChatState:
    """Persist user memory."""
    start = time.perf_counter()
    try:
        result = await long_term_memory_service.write_memory(state)
        if result and result.get("latest"):
            latest = result["latest"]
            state["memory_written"] = True
            summary = latest.get("summary", "")
            state["memory_summary"] = summary
            state["is_contact"] = latest.get("is_contact", False)

            state["long_term_memory"] = summary

            try:
                import re

                visitor_profile = state.get("visitor_profile", {}) or {}

                if summary:
                    if not visitor_profile.get("name"):
                        m = re.search(r"-\s*(?:User\s+)?[Nn]ame:\s*([^\n]+)", summary)
                        if m:
                            visitor_profile["name"] = m.group(1).strip()

                    if not visitor_profile.get("email"):
                        m = re.search(r"-\s*[Ee]mail:\s*([^\n\s]+)", summary)
                        if m:
                            visitor_profile["email"] = m.group(1).strip()

                    if not visitor_profile.get("phone"):
                        m = re.search(r"-\s*[Pp]hone:\s*([0-9\-\+()\s]{6,})", summary)
                        if m:
                            visitor_profile["phone"] = m.group(1).strip()

                    if not visitor_profile.get("address"):
                        m = re.search(r"-\s*[Aa]ddress:\s*([^\n]+)", summary)
                        if m:
                            visitor_profile["address"] = m.group(1).strip()

                state["visitor_profile"] = visitor_profile
                logger.info("Enriched visitor profile from memory_node", extra={"visitor_profile": visitor_profile})
            except Exception as e:
                logger.exception("Failed to parse memory summary for visitor_profile: %s", e)
        else:
            state["memory_written"] = False
            state["memory_summary"] = ""
    except Exception as e:
        logger.error("Long-term memory write failed: %s", e, exc_info=True)
        state["memory_written"] = False
        state.setdefault("memory_summary", "")
        state["error"] = state.get("error") or f"Memory write failed: {e}"

    latency = (time.perf_counter() - start) * 1000
    state.setdefault("latency_breakdown", {})["memory"] = latency
    logger.info("Memory node completed", extra={"latency_ms": latency})
    return state


async def final_node(state: ChatState) -> ChatState:
    """
    Final node: Finalize response, collect visitor info, and trigger webhook.
    This runs after streaming is complete to handle post-processing.
    """
    start = time.perf_counter()
    
    state["completed_at"] = now()
    
    latency_breakdown = state.get("latency_breakdown", {})
    total_latency = sum(latency_breakdown.values())
    state.setdefault("latency_breakdown", {})["total"] = total_latency
    
    log_latency_breakdown(state)
    
    latency = (time.perf_counter() - start) * 1000
    state.setdefault("latency_breakdown", {})["final"] = latency
    logger.info("Final node completed", extra={
        "latency_ms": latency,
        "total_latency": total_latency,
        "visitor_profile": state.get("visitor_profile", {}),
        "long_term_memory": state.get("long_term_memory", ""),
    })
    
    return state
