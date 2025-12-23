"""Webhook client for sending results to backend."""
import httpx
import hmac
import hashlib
from typing import Dict, Any, Union

from app.config.settings import settings
from app.schemas.grading import GradingWebhookPayload, AssessmentWebhookPayload
from app.utils.logging import get_logger

logger = get_logger(__name__)


class WebhookClient:
    """Send grading results to backend via webhook."""
    
    def __init__(self):
        self.url = f"{settings.BACKEND_API_URL}/api/v1/webhooks/visitor-grading"
        self.secret = settings.BACKEND_WEBHOOK_SECRET
        self.timeout = settings.WEBHOOK_TIMEOUT
        self.max_retries = settings.WEBHOOK_MAX_RETRIES
    
    def _generate_signature(self, payload: str) -> str:
        """Generate HMAC signature for webhook payload."""
        return hmac.new(
            self.secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
    
    async def send_result(self, payload: Union[GradingWebhookPayload, AssessmentWebhookPayload]) -> bool:
        """
        Send result to backend (grading or assessment).
        
        Args:
            payload: Result payload (GradingWebhookPayload or AssessmentWebhookPayload)
            
        Returns:
            True if successful, False otherwise
        """
        url = self.url
        payload_json = payload.model_dump_json()
        signature = self._generate_signature(payload_json)
        
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature,
        }
        
        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        url,
                        content=payload_json,
                        headers=headers
                    )
                    
                    if response.status_code == 200:
                        logger.info(
                            "Webhook sent successfully",
                            extra={
                                "task_id": payload.task_id,
                                "visitor_id": payload.visitor_id,
                                "attempt": attempt
                            }
                        )
                        return True
                    else:
                        logger.warning(
                            f"Webhook failed with status {response.status_code}",
                            extra={
                                "task_id": payload.task_id,
                                "attempt": attempt,
                                "response": response.text[:200]
                            }
                        )
                        
            except Exception as e:
                logger.error(
                    f"Webhook attempt {attempt} failed: {e}",
                    extra={
                        "task_id": payload.task_id,
                        "attempt": attempt
                    },
                    exc_info=True
                )
            
            if attempt < self.max_retries:
                import asyncio
                await asyncio.sleep(2 ** attempt)
        
        logger.error(
            f"Webhook failed after {self.max_retries} attempts",
            extra={
                "task_id": payload.task_id,
                "visitor_id": payload.visitor_id
            }
        )
        return False


# Global instance
webhook_client = WebhookClient()
