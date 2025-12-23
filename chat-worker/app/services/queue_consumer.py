"""RabbitMQ consumer for chat tasks."""
from __future__ import annotations

import asyncio
import json
from typing import Set, Dict

from aio_pika import Message

from app.config.settings import settings
from app.core.service_manager import service_manager
from app.core.keys import ChatKeys
from app.services.chat.graph import prepare_initial_state, chat_graph
from app.services.webhook_client import backend_webhook_client
from app.schemas.webhook import ChatCompletionPayload
from app.utils.logging import get_logger
from app.utils.datetime_utils import now

logger = get_logger(__name__)


class ChatQueueConsumer:
    """RabbitMQ consumer for processing chat tasks."""

    def __init__(self):
        self._running = False
        self._concurrent_semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_CHAT_TASKS)
        self._active_tasks: Set[asyncio.Task] = set()
        self._session_tasks: Dict[str, asyncio.Task] = {}
        self._cleanup_task: asyncio.Task | None = None
        self._cancel_listener_task: asyncio.Task | None = None

    async def _consume_messages(self) -> None:
        """Consume messages from queue."""
        channel = service_manager.get_rabbitmq_channel()
        queue_name = settings.CHAT_QUEUE_NAME

        queue = await channel.get_queue(queue_name)

        async def message_handler(message: Message) -> None:
            """Handle incoming message with concurrent processing."""
            try:
                task_data = json.loads(message.body.decode("utf-8"))

                logger.info("Received chat task", extra={
                    "task_id": task_data.get("task_id"),
                    "bot_id": task_data.get("bot_id"),
                    "session_token": task_data.get("session_token"),
                    "query_length": len(task_data.get("query", ""))
                })

                task = asyncio.create_task(
                    self._process_chat_task_with_semaphore(task_data, message)
                )
                self._active_tasks.add(task)
                
                session_token = task_data.get("session_token")
                if session_token:
                    self._session_tasks[session_token] = task

            except json.JSONDecodeError as e:
                logger.error("Invalid JSON message", exc_info=e)
                await message.nack(requeue=False)
            except Exception as e:
                logger.error("Message processing failed", exc_info=e)
                await message.nack(requeue=True)

        await queue.consume(message_handler)
        logger.info("Started consuming chat tasks")

        while self._running:
            await asyncio.sleep(1)

    async def _update_task_status(
        self,
        task_id: str,
        status: str,
        *,
        error: str | None = None,
        result: dict | None = None,
        progress: dict | None = None,
    ) -> None:
        """Update task status in Redis."""
        try:
            redis = service_manager.get_redis()
            key = ChatKeys.task_state(task_id)
            task_data = await redis.get(key)
            if not task_data:
                logger.warning("Task not found for status update", extra={"task_id": task_id})
                return

            task_state = json.loads(task_data)
            task_state["status"] = status
            task_state["updated_at"] = now().isoformat()

            if status == "completed" and result:
                task_state["completed_at"] = now().isoformat()
                task_state["result"] = result
            elif status == "failed" and error:
                task_state["error"] = error


            stream_key = ChatKeys.task_progress_channel(task_id)
            event_data = {
                "task_id": task_id,
                "status": status,
                "timestamp": now().isoformat(),
            }

            if progress:
                event_data.update(progress)
            if result:
                event_data["result"] = result
            if error:
                event_data["error"] = error

            await redis.publish(stream_key, json.dumps(event_data))
            logger.info(f"Published SSE event: status={status}, channel={stream_key}", extra={
                "task_id": task_id,
                "status": status,
                "has_result": result is not None,
                "has_progress": progress is not None
            })
            

            if status in ["completed", "failed"]:
                await redis.setex(key, 60, json.dumps(task_state))
                logger.debug("Task state will expire in 60s", extra={"task_id": task_id})
            else:
                await redis.setex(key, 3600, json.dumps(task_state))

            logger.debug("Updated task status", extra={
                "task_id": task_id,
                "status": status
            })

        except Exception as e:
            logger.error("Failed to update task status", extra={
                "task_id": task_id,
                "error": str(e)
            }, exc_info=e)

    async def _publish_progress_events(self, task_id: str, result: dict) -> None:
        """Publish progress events for streaming."""
        try:
            tokens_used = result.get("tokens_used", 0)
            latency_ms = result.get("latency_breakdown", {}).get("total", 0)

            if tokens_used > 0 or latency_ms > 0:
                await self._update_task_status(
                    task_id, "metrics",
                    progress={
                        "tokens_used": tokens_used,
                        "latency_ms": latency_ms
                    }
                )

        except Exception as e:
            logger.error("Failed to publish progress events", extra={
                "task_id": task_id,
                "error": str(e)
            }, exc_info=e)
    
    async def _publish_response_chunk(self, task_id: str, chunk: str) -> None:
        """Publish response chunk for real-time streaming to widget."""
        try:
            await self._update_task_status(
                task_id, "streaming",
                progress={"chunk": chunk}
            )
        except Exception as e:
            logger.error("Failed to publish response chunk", extra={
                "task_id": task_id,
                "error": str(e)
            }, exc_info=e)

    async def _process_chat_task_with_semaphore(self, task_data: dict, message: Message) -> None:
        """Process chat task with semaphore control and proper message handling."""
        session_token = task_data.get("session_token")
        
        async with self._concurrent_semaphore:
            try:
                await self._process_chat_task(task_data)
                await message.ack()
            except asyncio.CancelledError:
                logger.info(
                    "Chat task cancelled",
                    extra={"task_id": task_data.get("task_id"), "session_token": session_token}
                )
                await message.nack(requeue=False)
                raise
            except Exception as e:
                logger.error("Chat task processing failed, requeuing", extra={
                    "task_id": task_data.get("task_id"),
                    "error": str(e)
                }, exc_info=e)
                await message.nack(requeue=True)
                raise
            finally:
                if session_token and session_token in self._session_tasks:
                    del self._session_tasks[session_token]

    async def _process_chat_task(self, task_data: dict) -> None:
        """Process a single chat task using LangGraph."""
        task_id = task_data.get("task_id")
        if not task_id:
            logger.error("Task missing task_id", extra={"task_data": task_data})
            return

        try:
            await self._update_task_status(task_id, "processing")

            initial_state = await prepare_initial_state(
                task_id=task_id,
                query=task_data["query"],
                bot_id=task_data["bot_id"],
                session_token=task_data["session_token"],
                conversation_history=task_data.get("conversation_history", []),
                visitor_profile=task_data.get("visitor_profile", {}),
                long_term_memory=task_data.get("long_term_memory"),
                stream_mode=True,
            )

            result = await chat_graph.ainvoke(initial_state)

          
            visitor_profile_full = result.get("visitor_profile", {})
            visitor_id = visitor_profile_full.get("id")
            
            visitor_info_to_update = {
                k: v for k, v in visitor_profile_full.items()
                if k in ["name", "email", "phone", "address"] and v
            }

            long_term_memory = result.get("long_term_memory") or result.get("memory_summary")

            logger.info(
                "Preparing webhook payload",
                extra={
                    "task_id": task_id,
                    "has_visitor_info": bool(visitor_info_to_update),
                    "visitor_info": visitor_info_to_update,
                    "has_long_term_memory": bool(long_term_memory),
                    "long_term_memory_length": len(long_term_memory) if long_term_memory else 0,
                    "long_term_memory_preview": long_term_memory[:200] if long_term_memory else None,
                }
            )
            
            conversation_history = initial_state.get("conversation_history", [])
            session_summary = {
                "message_count": len(conversation_history) + 1,
                "topics": [result.get("intent", ""), result.get("detected_language", "")],
            }
            
            await self._publish_progress_events(task_id, result)
            
            bot_config = result.get("bot_config", {})
            model_id = bot_config.get("model_id")
            
            is_contact_value = result.get("is_contact", False)
            logger.info(
                "WEBHOOK PAYLOAD DEBUG - is_contact tracking",
                extra={
                    "task_id": task_id,
                    "is_contact_from_result": is_contact_value,
                    "visitor_profile_is_contact": visitor_profile_full.get("is_contact", False),
                    "memory_written": result.get("memory_written", False),
                    "memory_summary_preview": long_term_memory[:200] if long_term_memory else None,
                    "has_visitor_info": bool(visitor_info_to_update),
                    "visitor_info_fields": list(visitor_info_to_update.keys()) if visitor_info_to_update else [],
                }
            )
            
            webhook_payload = ChatCompletionPayload(
                session_token=initial_state.get("session_id"),
                bot_id=initial_state.get("bot_id"),
                visitor_id=visitor_id,
                query=initial_state.get("query"),
                response=result.get("response", ""),
                tokens_input=result.get("tokens_input", 0),
                tokens_output=result.get("tokens_output", 0),
                cost_usd=result.get("cost_usd", 0.0),
                model_id=model_id,
                visitor_info=visitor_info_to_update,
                long_term_memory=long_term_memory,
                session_summary=session_summary,
                is_contact=is_contact_value,
                extra_data={
                    "sources": result.get("sources", []),
                    "latency_ms": result.get("latency_breakdown", {}).get("total", 0),
                    "response_language": result.get("response_language", ""),
                    "detected_language": result.get("detected_language", ""),
                }
            )
            
            try:
                await backend_webhook_client.send_chat_completion(webhook_payload)
                logger.info(
                    "Webhook sent successfully after stream completion",
                    extra={"task_id": task_id, "visitor_id": visitor_id}
                )
            except Exception as webhook_error:
                logger.error(
                    "Failed to send webhook",
                    extra={"task_id": task_id, "error": str(webhook_error)},
                    exc_info=webhook_error
                )


            task_result = {
                "response": result.get("response", ""),
                "sources": result.get("sources", []),
                "tokens_used": result.get("tokens_used", 0),
                "latency_ms": result.get("latency_breakdown", {}).get("total", 0),
                "response_language": result.get("response_language", ""),
                "detected_language": result.get("detected_language", ""),
            }

            await self._update_task_status(task_id, "completed", result=task_result)

            logger.info("Chat task completed", extra={
                "task_id": task_id,
                "response_length": len(task_result["response"]),
                "tokens_used": task_result["tokens_used"]
            })

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            logger.error(f"Chat task failed: {str(e)}\n{error_details}", extra={
                "task_id": task_id,
                "error": str(e),
                "error_type": type(e).__name__
            })

            await self._update_task_status(task_id, "failed", error=str(e))
    
    async def _send_webhook_background(
        self, 
        webhook_payload: ChatCompletionPayload, 
        task_id: str,
        visitor_id: str | None
    ) -> None:
        """
        Send webhook as background task (non-blocking).
        This runs in parallel with progress events and SSE streaming.
        """
        try:
            await backend_webhook_client.send_chat_completion(webhook_payload)
            logger.info(
                "Webhook sent successfully",
                extra={"task_id": task_id, "visitor_id": visitor_id}
            )
        except Exception as webhook_error:
            logger.error(
                "Failed to send webhook (background)",
                extra={"task_id": task_id, "error": str(webhook_error)},
                exc_info=webhook_error
            )

    async def _cleanup_done_tasks_periodically(self) -> None:
        """Periodically cleanup done tasks to prevent memory leaks."""
        while self._running:
            await asyncio.sleep(10)
            
            try:
                done_tasks = {t for t in self._active_tasks if t.done()}
                
                if done_tasks:
                    logger.debug(f"Cleaning up {len(done_tasks)} completed tasks")
                    
                    for task in done_tasks:
                        self._active_tasks.discard(task)
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass
                        except Exception as e:
                            logger.error(f"Background task failed: {e}", exc_info=e)
                
                active_count = len(self._active_tasks)
                if active_count > 0:
                    logger.info(f"Active chat tasks: {active_count}/{settings.MAX_CONCURRENT_CHAT_TASKS}")
                    
            except Exception as e:
                logger.error(f"Error during task cleanup: {e}", exc_info=e)
    
    async def _listen_for_cancellations(self) -> None:
        """Listen for session cancellation signals from Redis."""
        try:
            redis = service_manager.get_redis()
            pubsub = redis.pubsub()
            
            await pubsub.psubscribe(f"{ChatKeys.task_cancel_channel('*')}")
            logger.info("Started listening for cancellation signals")
            
            while self._running:
                try:
                    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    
                    if message and message["type"] == "pmessage":
                        try:
                            data = json.loads(message["data"])
                            session_token = data.get("session_token")
                            
                            if session_token and session_token in self._session_tasks:
                                task = self._session_tasks[session_token]
                                if not task.done():
                                    task.cancel()
                                    logger.info(
                                        "Cancelled chat task for closed session",
                                        extra={"session_token": session_token}
                                    )
                        except json.JSONDecodeError:
                            logger.error("Invalid cancel message format")
                        except Exception as e:
                            logger.error(f"Error processing cancel message: {e}", exc_info=e)
                    
                    await asyncio.sleep(0.1)
                    
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.error(f"Error in cancel listener: {e}", exc_info=e)
                    await asyncio.sleep(1)
            
            await pubsub.unsubscribe(f"{ChatKeys.task_cancel_channel('*')}")
            await pubsub.close()
            logger.info("Stopped listening for cancellation signals")
            
        except Exception as e:
            logger.error("Cancel listener failed", exc_info=e)

    async def start_consuming(self) -> None:
        """Start the consumer loop with automatic reconnection."""
        self._running = True
        retry_count = 0
        max_retries = None 
        base_delay = 1
        max_delay = 60

        while self._running:
            try:
                self._cleanup_task = asyncio.create_task(self._cleanup_done_tasks_periodically())
                logger.info("Started periodic task cleanup")
                
                self._cancel_listener_task = asyncio.create_task(self._listen_for_cancellations())
                logger.info("Started cancel listener")
                
                if retry_count > 0:
                    logger.info("Successfully reconnected to RabbitMQ")
                    retry_count = 0
                
                await self._consume_messages()
                
            except asyncio.CancelledError:
                logger.info("Consumer cancelled, shutting down gracefully")
                break
                
            except Exception as e:
                retry_count += 1
                delay = min(base_delay * (2 ** (retry_count - 1)), max_delay)
                
                logger.error(
                    f"Consumer loop failed (attempt {retry_count}), retrying in {delay}s",
                    extra={"retry_count": retry_count, "delay": delay},
                    exc_info=e
                )
                
                if self._cleanup_task and not self._cleanup_task.done():
                    self._cleanup_task.cancel()
                    try:
                        await self._cleanup_task
                    except asyncio.CancelledError:
                        pass
                
                if self._cancel_listener_task and not self._cancel_listener_task.done():
                    self._cancel_listener_task.cancel()
                    try:
                        await self._cancel_listener_task
                    except asyncio.CancelledError:
                        pass
                
                await asyncio.sleep(delay)
                
                try:
                    logger.info("Attempting to reconnect to RabbitMQ...")
                    await service_manager._init_rabbitmq()
                    logger.info("RabbitMQ connection re-established")
                except Exception as reconnect_error:
                    logger.error(f"Failed to reconnect to RabbitMQ: {reconnect_error}")
                    
            finally:
                self._running = False
            
            if self._cleanup_task and not self._cleanup_task.done():
                self._cleanup_task.cancel()
                try:
                    await self._cleanup_task
                except asyncio.CancelledError:
                    pass
            
            if self._cancel_listener_task and not self._cancel_listener_task.done():
                self._cancel_listener_task.cancel()
                try:
                    await self._cancel_listener_task
                except asyncio.CancelledError:
                    pass

    async def stop_consuming(self) -> None:
        """Stop the consumer and cancel all active tasks."""
        self._running = False

        if self._active_tasks:
            logger.info(f"Cancelling {len(self._active_tasks)} active tasks")
            for task in self._active_tasks:
                if not task.done():
                    task.cancel()

            try:
                await asyncio.gather(*self._active_tasks, return_exceptions=True)
            except asyncio.CancelledError:
                pass

            self._active_tasks.clear()
            logger.info("All active tasks cancelled")


chat_queue_consumer = ChatQueueConsumer()
