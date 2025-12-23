"""
Webhook security utilities
"""
import hmac
import hashlib

from app.config.settings import settings


def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """
    Verify HMAC-SHA256 signature from file-server webhook
    
    Args:
        payload: Raw request body bytes
        signature: Signature from X-Webhook-Signature header
        
    Returns:
        True if signature is valid, False otherwise
    """
    expected_signature = hmac.new(
        settings.BACKEND_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected_signature)
