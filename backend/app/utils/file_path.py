"""
Utility functions for file path operations.
Provides consistent file path building and parsing across the application.
"""
import uuid
from app.common.constants import FilePathPattern


def build_avatar_key(file_extension: str) -> str:
    """
    Build object key for bot avatar storage.
    
    Format: avatars/{uuid}.{extension}
    Example: avatars/550e8400-e29b-41d4-a716-446655440000.jpeg
    
    Args:
        file_extension: File extension (jpeg, png, gif, webp)
        
    Returns:
        Object key string
    """
    return f"avatars/{uuid.uuid4()}.{file_extension}"


def build_logo_key(file_extension: str) -> str:
    """
    Build object key for company logo storage.
    
    Format: logos/{uuid}.{extension}
    Example: logos/550e8400-e29b-41d4-a716-446655440000.png
    
    Args:
        file_extension: File extension (jpeg, png, gif, webp)
        
    Returns:
        Object key string
    """
    return f"logos/{uuid.uuid4()}.{file_extension}"


def build_local_filename(doc_id: str, filename: str) -> str:
    """
    Build local filename for shared volume storage.
    
    Format: {doc_id}_{filename}
    Example: uuid-456_document.pdf
    
    Args:
        doc_id: Document UUID
        filename: Original filename with extension
        
    Returns:
        Local filename string
    """
    return f"{doc_id}{FilePathPattern.FILENAME_SEPARATOR}{filename}"


def build_document_file_path(bot_key: str, doc_id: str, filename: str) -> str:
    """
    Build consistent file path for document storage.
    
    Format: {bot_key}/{doc_id}_{filename}
    Example: bot_abc123/uuid-456_document.pdf
    
    Args:
        bot_key: Bot key identifier (e.g., bot_abc123)
        doc_id: Document UUID
        filename: Original filename with extension
        
    Returns:
        Full file path string
    """
    return f"{bot_key}{FilePathPattern.PATH_SEPARATOR}{doc_id}{FilePathPattern.FILENAME_SEPARATOR}{filename}"


def extract_object_name(file_path: str) -> str:
    """
    Extract object name from full file path (remove bot_key prefix).
    
    Converts: bot_abc123/uuid-456_document.pdf
    To: uuid-456_document.pdf
    
    Args:
        file_path: Full file path with bot_key prefix
        
    Returns:
        Object name without bot_key prefix
    """
    parts = file_path.split(FilePathPattern.PATH_SEPARATOR, 1)
    return parts[1] if len(parts) > 1 else file_path


def parse_document_file_path(file_path: str) -> dict:
    """
    Parse document file path into components.
    
    Args:
        file_path: Full file path (e.g., bot_abc123/uuid-456_document.pdf)
        
    Returns:
        Dictionary with keys: bot_key, doc_id, filename, object_name
        Returns empty dict if format is invalid
    """
    try:
        parts = file_path.split(FilePathPattern.PATH_SEPARATOR, 1)
        if len(parts) != 2:
            return {}
        
        bot_key = parts[0]
        object_name = parts[1]
        
        if FilePathPattern.FILENAME_SEPARATOR in object_name:
            first_sep_idx = object_name.index(FilePathPattern.FILENAME_SEPARATOR)
            doc_id = object_name[:first_sep_idx]
            filename = object_name[first_sep_idx + 1:]
        else:
            doc_id = ""
            filename = object_name
        
        return {
            "bot_key": bot_key,
            "doc_id": doc_id,
            "filename": filename,
            "object_name": object_name
        }
    except Exception:
        return {}
