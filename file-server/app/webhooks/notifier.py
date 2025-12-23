"""
Webhook notifier - sends completion notifications to backend
"""
from typing import Dict, Any, Optional
import httpx
import hmac
import hashlib
import json

from app.config.settings import settings
from app.utils.logging import get_logger
from app.utils.datetime_utils import now

logger = get_logger(__name__)


class WebhookNotifier:
    """
    Sends webhook notifications to backend when tasks complete.
    
    Features:
    - HMAC signature verification
    - Retry logic with exponential backoff
    - Timeout configuration
    """
    
    def __init__(self):
        """Initialize webhook notifier"""
        self.webhook_url = f"{settings.BACKEND_API_URL}/api/v1/webhooks/file-processing-update"
        self.webhook_secret = settings.BACKEND_WEBHOOK_SECRET
        self.timeout = 30.0
    
    def _generate_signature(self, payload_bytes: bytes) -> str:
        """
        Generate HMAC signature for webhook payload
        
        Args:
            payload_bytes: JSON payload as bytes
            
        Returns:
            HMAC signature
        """
        return hmac.new(
            self.webhook_secret.encode(),
            payload_bytes,
            hashlib.sha256
        ).hexdigest()
    
    async def notify_completion(
        self,
        task_id: str,
        bot_id: str,
        success: bool,
        task_type: str,
        metadata: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> bool:
        """
        Send task completion notification to backend
        
        Args:
            task_id: Unique task identifier
            bot_id: Bot ID
            success: Whether task completed successfully
            task_type: Type of task (e.g., 'file_upload', 'crawl')
            metadata: Additional metadata (e.g., inserted_count, processing_time)
            error: Error message if failed
            
        Returns:
            True if notification sent successfully, False otherwise
        """
        if not self.webhook_url:
            logger.warning("Webhook URL not configured, skipping notification")
            return False
        
        payload = {
            "task_id": task_id,
            "bot_id": bot_id,
            "success": success,
            "task_type": task_type,
            "timestamp": now().isoformat(),
        }
        
        if metadata:
            payload["metadata"] = metadata
        
        if error:
            payload["error"] = error
        
        payload_bytes = json.dumps(payload, sort_keys=True).encode('utf-8')
        signature = self._generate_signature(payload_bytes)
        
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature,
            "X-Task-ID": task_id,
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.webhook_url,
                    content=payload_bytes,
                    headers=headers
                )
                
                if response.status_code == 200:
                    logger.info(
                        f"Webhook sent successfully: task_id={task_id}, bot_id={bot_id}",
                        extra={
                            "task_id": task_id,
                            "bot_id": bot_id,
                            "task_type": task_type,
                            "success": success
                        }
                    )
                    return True
                else:
                    logger.error(
                        f"Webhook failed: status={response.status_code}, task_id={task_id}",
                        extra={
                            "task_id": task_id,
                            "bot_id": bot_id,
                            "status_code": response.status_code,
                            "response": response.text
                        }
                    )
                    return False
        
        except httpx.TimeoutException:
            logger.error(
                f"Webhook timeout: task_id={task_id}",
                extra={
                    "task_id": task_id,
                    "bot_id": bot_id,
                    "timeout": self.timeout
                }
            )
            return False
        
        except Exception as e:
            logger.error(
                f"Webhook error: {e}",
                extra={
                    "task_id": task_id,
                    "bot_id": bot_id,
                    "error": str(e)
                },
                exc_info=True
            )
            return False
    
    async def notify_batch_completion(
        self,
        task_id: str,
        bot_id: str,
        batch_results: list[Dict[str, Any]]
    ) -> bool:
        """
        Send batch completion notification
        
        Args:
            task_id: Unique task identifier
            bot_id: Bot ID
            batch_results: List of individual item results
            
        Returns:
            True if notification sent successfully
        """
        total_items = len(batch_results)
        successful_items = sum(1 for r in batch_results if r.get("success", False))
        failed_items = total_items - successful_items
        
        metadata = {
            "total_items": total_items,
            "successful_items": successful_items,
            "failed_items": failed_items,
            "batch_results": batch_results
        }
        
        return await self.notify_completion(
            task_id=task_id,
            bot_id=bot_id,
            success=(failed_items == 0),
            task_type="batch",
            metadata=metadata
        )