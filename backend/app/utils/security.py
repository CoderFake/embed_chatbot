"""Security utilities for password hashing, token management, and webhook verification."""
import hmac
import hashlib
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.config.settings import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

API_KEY_HEADER = "X-Internal-API-Key"


def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """
    Verify the HMAC-SHA256 signature of a webhook payload.

    Args:
        payload: The raw request body as bytes.
        signature: The signature from the 'X-Webhook-Signature' header.

    Returns:
        True if the signature is valid, False otherwise.
    """
    if not settings.BACKEND_WEBHOOK_SECRET:
        logger.warning("BACKEND_WEBHOOK_SECRET is not set. Skipping signature verification.")
        return True

    expected_signature = hmac.new(
        settings.BACKEND_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected_signature, signature)


async def require_internal_api_key(api_key: str = Security(APIKeyHeader(name=API_KEY_HEADER))):
    """
    Dependency to protect internal endpoints.
    Requires a valid internal API key to be present in the header.
    """
    if not settings.INTERNAL_API_KEY:
        logger.warning("Internal API key is not set, endpoint is unprotected")
        return

    if not api_key or api_key != settings.INTERNAL_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing internal API key",
        )