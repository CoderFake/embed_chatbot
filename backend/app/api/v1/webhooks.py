"""
Webhook endpoints for receiving notifications from internal services
- chat-worker: Chat completion notifications
- file-server: File processing status updates
- sitemap-crawler: Sitemap crawl completion updates
- visitor-grader: Visitor lead scoring results
"""
from __future__ import annotations
import json
from fastapi import APIRouter, Request, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from app.cache.invalidation import CacheInvalidation
from app.cache.keys import CacheKeys
from app.core.database import get_db, redis_manager
from app.core.dependencies import get_redis
from app.schemas.webhook import (
    ChatCompletionPayload,
    FileProcessingUpdatePayload,
    SitemapCrawlUpdatePayload,
    WebhookResponse,
    VisitorGradingWebhook,
)
from app.schemas.visitor import VisitorInfoUpdate
from app.services.document import DocumentService
from app.services.visitor import VisitorService
from app.services.chat import chat_service
from app.models.visitor import ChatMessage, ChatSession
from app.common.enums import TaskType, AssessmentTaskType, LeadCategory
from app.models.usage import UsageLog
from pydantic import ValidationError
from app.utils.security import verify_webhook_signature
from app.utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


# ============================================================================
# Chat Worker Webhook - Chat Completion
# ============================================================================

@router.post(
    "/webhooks/chat-completion",
    response_model=WebhookResponse,
    include_in_schema=False
)
async def chat_completion_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    **INTERNAL ONLY** - Webhook from chat-worker after chat task completes.
    
    Verifies HMAC signature and processes chat completion data:
    - Saves chat message
    - Updates visitor info if collected
    - Saves long-term memory
    - Creates usage log
    
    Not exposed in API documentation.
    """
    signature = request.headers.get("X-Webhook-Signature")
    if not signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing webhook signature",
        )

    body = await request.body()
    if not verify_webhook_signature(body, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )

    try:
        payload_dict = json.loads(body.decode())
        payload = ChatCompletionPayload(**payload_dict)
        
        visitor_service = VisitorService(db)
        session = await visitor_service.create_or_find_session(
            bot_id=payload.bot_id,
            visitor_id=payload.visitor_id,
            session_token=payload.session_token,
        )

        if payload.long_term_memory or payload.session_summary:
            session_extra = session.extra_data.copy() if session.extra_data else {}
            
            if payload.long_term_memory:
                session_extra["long_term_memory"] = payload.long_term_memory
                logger.info(
                    "Updating session long_term_memory",
                    extra={
                        "session_id": session.id,
                        "session_token": payload.session_token,
                        "memory_length": len(payload.long_term_memory),
                        "memory_preview": payload.long_term_memory[:200] if len(payload.long_term_memory) > 200 else payload.long_term_memory,
                    }
                )
            if payload.session_summary:
                session_extra["session_summary"] = payload.session_summary
                logger.info(
                    "Updating session_summary",
                    extra={
                        "session_id": session.id,
                        "session_token": payload.session_token,
                        "summary_length": len(payload.session_summary),
                    }
                )
            
            session.extra_data = session_extra
        
        chat_message = ChatMessage(
            session_id=session.id,
            query=payload.query,
            response=payload.response,
            extra_data=payload.extra_data or {},
        )
        db.add(chat_message)

        usage_log = UsageLog(
            bot_id=payload.bot_id,
            model_id=payload.model_id if payload.model_id else None,
            session_id=session.id,
            tokens_input=payload.tokens_input,
            tokens_output=payload.tokens_output,
            cost_usd=payload.cost_usd,
        )
        db.add(usage_log)

        if payload.visitor_info:
            try:
                logger.info(
                    "Processing visitor_info from webhook",
                    extra={
                        "visitor_id": payload.visitor_id,
                        "visitor_info": payload.visitor_info,
                    }
                )
                
                validated_info = VisitorInfoUpdate(**payload.visitor_info)
                validated_dict = validated_info.model_dump(exclude_none=True)
                
                logger.info(
                    "Validated visitor_info",
                    extra={
                        "visitor_id": payload.visitor_id,
                        "validated_fields": list(validated_dict.keys()),
                        "validated_info": validated_dict,
                    }
                )
                
                updated = await visitor_service.update_visitor_info(
                    visitor_id=payload.visitor_id,
                    validated_info=validated_dict
                )
                if updated:
                    logger.info(
                        "Updated visitor info from chat",
                        extra={
                            "visitor_id": payload.visitor_id,
                            "collected": list(validated_dict.keys()),
                            "values": validated_dict,
                        }
                    )
                else:
                    logger.warning(
                        "Failed to update visitor info (no rows affected)",
                        extra={
                            "visitor_id": payload.visitor_id,
                            "attempted_fields": list(validated_dict.keys()),
                        }
                    )
            except ValidationError as e:
                logger.warning(
                    "Invalid visitor info collected from chat",
                    extra={
                        "visitor_id": payload.visitor_id,
                        "errors": e.errors(),
                        "raw_data": payload.visitor_info
                    }
                )

        logger.info(
            "WEBHOOK RECEIVED: Checking contact notification conditions",
            extra={
                "payload_is_contact": payload.is_contact,
                "session_is_contact": session.is_contact,
                "will_send_notification": payload.is_contact and not session.is_contact,
                "session_id": session.id,
                "visitor_id": payload.visitor_id,
                "visitor_info": payload.visitor_info
            }
        )
        
        if payload.is_contact and not session.is_contact:
            logger.info(
                "CONTACT NOTIFICATION: Triggering notification (is_contact: false -> true)",
                extra={
                    "bot_id": payload.bot_id,
                    "visitor_id": payload.visitor_id,
                    "visitor_info": payload.visitor_info,
                    "session_id": session.id
                }
            )
            try:
                await visitor_service.handle_contact_request(
                    bot_id=payload.bot_id,
                    visitor_id=payload.visitor_id,
                    visitor_info=payload.visitor_info,
                    query=payload.query,
                    response=payload.response,
                    session_token=payload.session_token,
                )
                session.is_contact = True
                logger.info(
                    "CONTACT NOTIFICATION: Successfully updated is_contact to True",
                    extra={
                        "session_id": session.id,
                        "visitor_id": payload.visitor_id,
                    }
                )
            except Exception as e:
                logger.error(
                    f"CONTACT NOTIFICATION: Failed to handle contact request: {e}",
                    exc_info=True,
                    extra={"bot_id": payload.bot_id, "visitor_id": payload.visitor_id}
                )
        elif payload.is_contact and session.is_contact:
            logger.info(
                "CONTACT NOTIFICATION: Skipping - contact already collected for this session",
                extra={"session_id": session.id, "visitor_id": payload.visitor_id}
            )
        elif not payload.is_contact:
            logger.debug(
                "CONTACT NOTIFICATION: Skipping - payload.is_contact is False",
                extra={"session_id": session.id, "visitor_id": payload.visitor_id}
            )


        await db.commit()
        
        logger.info(
            "Chat completion processed successfully",
            extra={
                "session_token": payload.session_token,
                "tokens": payload.tokens_input + payload.tokens_output,
                "cost_usd": payload.cost_usd,
                "is_contact": payload.is_contact,
            }
        )
        
        return WebhookResponse()
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in chat completion webhook: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        )
    except ValidationError as ve:
        logger.error(f"Validation error in chat completion webhook: {ve}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid payload structure: {str(ve)}",
        )
    except Exception as e:
        logger.error(f"Chat completion webhook failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process chat completion webhook: {str(e)}",
        )


# ============================================================================
# File Server Webhooks - File Processing & Sitemap Crawl
# ============================================================================

@router.post(
    "/webhooks/file-processing-update",
    include_in_schema=False
)
async def file_processing_update(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """
    **INTERNAL ONLY** - Webhook from file-server for file processing status updates.
    
    Updates document processing status and invalidates cache.
    Not exposed in API documentation.
    """
    try:
        signature = request.headers.get("X-Webhook-Signature")
        if not signature:
            logger.warning(
                "Webhook received without signature",
                extra={"client_ip": request.client.host}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing webhook signature"
            )
        
        body = await request.body()
        
        if not verify_webhook_signature(body, signature):
            logger.warning(
                "Invalid webhook signature",
                extra={"client_ip": request.client.host}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature"
            )
        
        payload_dict = json.loads(body.decode())
        payload = FileProcessingUpdatePayload(**payload_dict)

        logger.info(
            f"File processing update received: task_id={payload.task_id}, success={payload.success}",
            extra={
                "task_id": payload.task_id,
                "bot_id": payload.bot_id,
                "success": payload.success,
                "task_type": payload.task_type
            }
        )

        document_service = DocumentService(db, redis)

        from app.services.notification import NotificationService
        notification_service = NotificationService(db, redis)

        if payload.success and payload.metadata and payload.metadata.results:
            for result in payload.metadata.results:
                if result.document_id:
                    try:
                        await document_service.update_processing_result(
                            document_id=result.document_id,
                            success=result.success,
                            chunks_count=result.chunks_count,
                            error_message=result.error
                        )
                        logger.info(
                            f"Updated document {result.document_id} status",
                            extra={
                                "document_id": result.document_id,
                                "success": result.success,
                                "chunks": result.chunks_count
                            }
                        )
                    except HTTPException:
                        logger.warning(
                            f"Document {result.document_id} not found, skipping update",
                            extra={"document_id": result.document_id}
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to update document {result.document_id}: {e}",
                            extra={"document_id": result.document_id},
                            exc_info=True
                        )
        
        elif not payload.success and payload.error:
            logger.warning(
                f"File processing failed: {payload.error}",
                extra={
                    "bot_id": payload.bot_id,
                    "task_id": payload.task_id,
                    "error": payload.error
                }
            )

        try:
            progress = 100 if payload.success else 0
            task_status = "completed" if payload.success else "failed"
            message = "Processing completed successfully" if payload.success else f"Processing failed: {payload.error}"

            await notification_service.update_task_notification(
                task_id=payload.task_id,
                progress=progress,
                status=task_status,
                message=message
            )
        except Exception as e:
            logger.error(f"Failed to update task notification: {e}", exc_info=True)

        await db.commit()

        try:
            cache = CacheInvalidation(redis)
            await cache.invalidate_bot(payload.bot_id)
            logger.debug(
                f"Invalidated cache for bot: {payload.bot_id}",
                extra={"bot_id": payload.bot_id}
            )
        except Exception as e:
            logger.error(f"Failed to invalidate cache: {e}", exc_info=True)
        
        return WebhookResponse(
            status="received",
            task_id=payload.task_id,
            message="Webhook processed successfully"
        )
    
    except json.JSONDecodeError as e:
        logger.error(
            f"Invalid JSON in webhook payload: {e}",
            extra={"client_ip": request.client.host}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(
            f"Error processing webhook: {e}",
            extra={"client_ip": request.client.host},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process webhook"
        )


@router.post(
    "/sitemap-crawl-update",
    response_model=WebhookResponse,
    status_code=status.HTTP_200_OK,
    summary="[INTERNAL] Receive sitemap crawl update",
    description="""
    **INTERNAL ONLY** - Not exposed to external networks.
    
    Webhook endpoint for sitemap crawler to notify crawl completion.
    
    **Security:**
    - HMAC-SHA256 signature verification
    - Signature provided in `X-Webhook-Signature` header
    - Only accessible from sitemap-crawler container within Docker network
    
    **Flow:**
    1. Sitemap-crawler completes crawling
    2. Sitemap-crawler sends webhook with HMAC signature
    3. Backend verifies signature
    4. Backend updates crawl status
    5. Backend invalidates relevant caches
    """,
    include_in_schema=False  
)
async def sitemap_crawl_update_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
) -> WebhookResponse:
    """
    Receive sitemap crawl update webhook from file-server.

    This endpoint is called by file-server when a crawl task completes.
    It creates Document records for crawled pages and invalidates relevant caches.
    """
    try:
        signature = request.headers.get("X-Webhook-Signature")
        if not signature:
            logger.warning(
                "Webhook received without signature",
                extra={"client_ip": request.client.host}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing webhook signature"
            )

        body = await request.body()

        if not verify_webhook_signature(body, signature):
            logger.warning(
                "Invalid webhook signature",
                extra={"client_ip": request.client.host}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature"
            )

        payload_dict = json.loads(body.decode())
        payload = SitemapCrawlUpdatePayload(**payload_dict)

        logger.info(
            f"Crawl update received: task_id={payload.task_id}, success={payload.success}",
            extra={
                "task_id": payload.task_id,
                "bot_id": payload.bot_id,
                "success": payload.success,
                "task_type": payload.task_type
            }
        )

        from app.services.notification import NotificationService
        notification_service = NotificationService(db, redis)

        if payload.success and payload.metadata and payload.metadata.crawled_pages:
            logger.info(
                f"Creating Document records for {len(payload.metadata.crawled_pages)} crawled pages",
                extra={
                    "bot_id": payload.bot_id,
                    "total_pages": len(payload.metadata.crawled_pages)
                }
            )

            created_count = 0
            failed_count = 0

            for page in payload.metadata.crawled_pages:
                if not page.success or not page.url:
                    failed_count += 1
                    continue

                try:
                    import hashlib
                    from app.models.document import Document
                    from app.common.enums import DocumentStatus

                    content_hash = hashlib.sha256(page.url.encode('utf-8')).hexdigest()

                    doc = Document(
                        bot_id=payload.bot_id,
                        url=page.url,
                        title=page.title or page.url,
                        content_hash=content_hash,
                        status=DocumentStatus.COMPLETED,
                        extra_data={
                            "chunks_count": page.chunks_count,
                            "task_id": payload.task_id,
                            "crawled_at": payload.timestamp.isoformat()
                        }
                    )

                    db.add(doc)
                    created_count += 1

                except Exception as e:
                    logger.error(
                        f"Failed to create document for URL {page.url}: {e}",
                        extra={"url": page.url, "bot_id": payload.bot_id},
                        exc_info=True
                    )
                    failed_count += 1

            logger.info(
                f"Created {created_count} documents, {failed_count} failed",
                extra={
                    "bot_id": payload.bot_id,
                    "created": created_count,
                    "failed": failed_count
                }
            )
        elif payload.success:
            logger.warning(
                f"Crawl successful but no crawled_pages in metadata",
                extra={"bot_id": payload.bot_id, "task_id": payload.task_id}
            )
        else:
            logger.warning(
                f"Crawl failed: {payload.bot_id}, error: {payload.error}",
                extra={"bot_id": payload.bot_id, "error": payload.error}
            )

        try:
            progress = 100 if payload.success else 0
            task_status = "completed" if payload.success else "failed"
            message = "Crawl completed successfully" if payload.success else f"Crawl failed: {payload.error}"

            await notification_service.update_task_notification(
                task_id=payload.task_id,
                progress=progress,
                status=task_status,
                message=message
            )
        except Exception as e:
            logger.error(f"Failed to update task notification: {e}", exc_info=True)

        await db.commit()
        
        try:
            cache = CacheInvalidation(redis)
            await cache.invalidate_bot(payload.bot_id)
            logger.debug(
                f"Invalidated cache for bot: {payload.bot_id}",
                extra={"bot_id": payload.bot_id}
            )
        except Exception as e:
            logger.error(f"Failed to invalidate cache: {e}", exc_info=True)
        
        return WebhookResponse(
            status="received",
            task_id=payload.task_id,
            message="Webhook processed successfully"
        )
    
    except json.JSONDecodeError as e:
        logger.error(
            f"Invalid JSON in webhook payload: {e}",
            extra={"client_ip": request.client.host}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(
            f"Error processing webhook: {e}",
            extra={"client_ip": request.client.host},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process webhook"
        )


# ============================================================================
# Visitor Grader Webhook - Lead Scoring  
# ============================================================================

@router.post(
    "/webhooks/visitor-grading",
    response_model=WebhookResponse,
    include_in_schema=False
)
async def visitor_grading_webhook(
    request: Request,
    payload: VisitorGradingWebhook,
    db: AsyncSession = Depends(get_db),
):
    """
    **INTERNAL ONLY** - Webhook from visitor-grader after scoring/assessment completes.
    
    Handles both:
    - Lead scoring (grading): Updates visitor lead score, sends hot lead notifications
    - Custom assessment: Stores assessment results in visitor extra_data
    
    Security: HMAC signature required
    """
    try:
        body = await request.body()
        signature = request.headers.get("X-Webhook-Signature", "")
        
        if not verify_webhook_signature(body, signature):
            logger.warning(
                "Invalid webhook signature",
                extra={
                    "endpoint": "/webhooks/visitor-grading",
                    "visitor_id": payload.visitor_id
                }
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature"
            )
        
        task_type = payload.task_type or AssessmentTaskType.GRADING.value
        
        logger.info(
            f"Received visitor {task_type} webhook",
            extra={
                "task_id": payload.task_id,
                "task_type": task_type,
                "visitor_id": payload.visitor_id,
                "bot_id": payload.bot_id
            }
        )
        
        visitor_service = VisitorService(db)
        
        if task_type == AssessmentTaskType.ASSESSMENT.value:
            await visitor_service.store_assessment_results(
                visitor_id=payload.visitor_id,
                assessment_data={
                    "results": [r.model_dump() for r in (payload.results or [])],
                    "summary": payload.summary,
                    "assessed_at": payload.assessed_at.isoformat() if payload.assessed_at else None,
                    "model_used": payload.model_used,
                    "total_messages": payload.total_messages,
                },
                lead_score=getattr(payload, 'lead_score', 0)
            )

            redis_client = redis_manager.get_redis()
            active_key = CacheKeys.assessment_active(payload.visitor_id)
            lock_key = CacheKeys.assessment_lock(payload.visitor_id)
            await redis_client.delete(active_key)
            await redis_client.delete(lock_key)
            
            channel = CacheKeys.task_progress_channel(payload.task_id)
            await redis_client.publish(channel, json.dumps({
                "status": "COMPLETED",
                "task_id": payload.task_id,
                "visitor_id": payload.visitor_id,
                "lead_score": getattr(payload, 'lead_score', 0),
                "summary": payload.summary,
            }))
            logger.info(f"Published COMPLETED event to SSE channel: {channel}")
            
        else:
            
            await visitor_service.update_lead_score(
                visitor_id=payload.visitor_id,
                lead_score=payload.lead_score or 0,
                lead_category=payload.lead_category or LeadCategory.COLD.value,
                scoring_data={
                    "intent_signals": payload.intent_signals,
                    "engagement_level": payload.engagement_level,
                    "key_interests": payload.key_interests,
                    "recommended_actions": payload.recommended_actions,
                    "reasoning": payload.reasoning,
                    "graded_at": payload.graded_at.isoformat() if payload.graded_at else None,
                    "model_used": payload.model_used,
                    "conversation_count": payload.conversation_count or 0,
                    "session_id": payload.session_id
                }
            )
            
            redis_client = redis_manager.get_redis()
            lock_key = CacheKeys.grading_lock(payload.visitor_id)
            await redis_client.delete(lock_key)

        message = f"Visitor {task_type} processed successfully"
        return WebhookResponse(message=message)
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(
            f"Error processing visitor grading webhook: {e}",
            extra={
                "task_id": payload.task_id,
                "visitor_id": payload.visitor_id
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process visitor grading webhook"
        )
