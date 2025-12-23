"""Client for sending requests to the backend webhook with HMAC signature."""
from __future__ import annotations

import httpx
import hmac
import hashlib
import json
from app.config.settings import settings
from app.schemas.webhook import ChatCompletionPayload
from app.utils.logging import get_logger

logger = get_logger(__name__)


class BackendWebhookClient:
    def __init__(self):
        self.base_url = settings.BACKEND_API_URL
        self.webhook_secret = settings.BACKEND_WEBHOOK_SECRET
        self.timeout = 15.0

    def _generate_signature(self, payload_bytes: bytes) -> str:
        """Generate HMAC-SHA256 signature for the webhook payload."""
        if not self.webhook_secret:
            return ""
        return hmac.new(
            self.webhook_secret.encode(),
            payload_bytes,
            hashlib.sha256
        ).hexdigest()

    async def send_chat_completion(self, payload: ChatCompletionPayload):
        """Send the chat completion data to the backend webhook."""
        if not self.base_url:
            logger.warning("BACKEND_API_URL is not set. Skipping webhook call.")
            return

        url = f"{self.base_url}/api/v1/webhooks/chat-completion"

        payload_dict = payload.model_dump()
        payload_bytes = json.dumps(payload_dict, sort_keys=True).encode('utf-8')

        signature = self._generate_signature(payload_bytes)

        headers = {
            "Content-Type": "application/json",
        }
        if signature:
            headers["X-Webhook-Signature"] = signature

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    content=payload_bytes,
                    headers=headers,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                logger.info("Successfully sent chat completion webhook to backend.", extra={"status_code": response.status_code})
        except httpx.HTTPStatusError as e:
            logger.error(
                "HTTP error calling backend webhook.",
                exc_info=True,
                extra={"url": url, "status_code": e.response.status_code, "response": e.response.text},
            )
            raise
        except httpx.RequestError as e:
            logger.error(
                "Request error calling backend webhook.",
                exc_info=True,
                extra={"url": url},
            )
            raise

backend_webhook_client = BackendWebhookClient()
