"""
Utility functions for image processing.
Provides image type detection and validation.
"""
from typing import Optional


def detect_image_type(data: bytes) -> Optional[str]:
    """
    Detect image type from bytes without using deprecated imghdr.
    
    Args:
        data: Image file bytes
        
    Returns:
        Image type string ('jpeg', 'png', 'gif', 'webp') or None if not recognized
    """
    if data.startswith(b'\xff\xd8\xff'):
        return 'jpeg'
    elif data.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'png'
    elif data.startswith(b'GIF87a') or data.startswith(b'GIF89a'):
        return 'gif'
    elif data.startswith(b'RIFF') and b'WEBP' in data[:20]:
        return 'webp'
    return None


def parse_content_type(content_type: str) -> tuple[str, dict]:
    """
    Parse Content-Type header into type and options.
    
    Example: "multipart/form-data; boundary=----WebKitFormBoundary"
    Returns: ("multipart/form-data", {"boundary": "----WebKitFormBoundary"})
    
    Args:
        content_type: Content-Type header value
        
    Returns:
        Tuple of (media_type, options_dict)
    """
    parts = content_type.split(';')
    media_type = parts[0].strip()
    options = {}
    
    for part in parts[1:]:
        if '=' in part:
            key, value = part.split('=', 1)
            options[key.strip()] = value.strip()
    
    return media_type, options
