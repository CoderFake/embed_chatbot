"""
Widget file management service.
Handles upload, storage, and serving of widget JavaScript files.
"""
from typing import Optional, Dict, List, BinaryIO
import io

from app.services.storage import minio_service
from app.config.settings import settings
from app.common.constants import WidgetFile
from app.utils.logging import get_logger

logger = get_logger(__name__)


class WidgetService:
    """Service for managing widget files in MinIO"""
    
    def __init__(self):
        self.bucket = settings.MINIO_PUBLIC_BUCKET
    
    def validate_file(self, filename: str, file_size: int) -> None:
        """
        Validate widget file.
        
        Args:
            filename: Name of the file
            file_size: Size of the file in bytes
            
        Raises:
            ValueError: If validation fails
        """
        if not any(filename.lower().endswith(ext) for ext in WidgetFile.ALLOWED_EXTENSIONS):
            raise ValueError(WidgetFile.ERROR_INVALID_EXTENSION)
        
        if file_size > WidgetFile.MAX_FILE_SIZE_BYTES:
            raise ValueError(WidgetFile.ERROR_FILE_TOO_LARGE)
    
    def get_object_keys(self, version: Optional[str] = None) -> Dict[str, str]:
        """
        Get MinIO object keys for widget files.
        
        Args:
            version: Widget version (optional)
            
        Returns:
            Dict with 'latest' and optionally 'versioned' keys
        """
        keys = {
            "latest": f"{WidgetFile.STORAGE_PREFIX}/{WidgetFile.LATEST_FILENAME}"
        }
        
        if version:
            versioned_filename = WidgetFile.VERSIONED_FILENAME_TEMPLATE.format(version=version)
            keys["versioned"] = f"{WidgetFile.STORAGE_PREFIX}/{versioned_filename}"
        
        return keys
    
    def get_cache_control(self, is_versioned: bool) -> str:
        """
        Get appropriate Cache-Control header.
        
        Args:
            is_versioned: Whether file is a versioned release
            
        Returns:
            Cache-Control header value
        """
        return (
            WidgetFile.VERSIONED_CACHE_CONTROL if is_versioned 
            else WidgetFile.LATEST_CACHE_CONTROL
        )
    
    def upload_widget(
        self,
        file_data: BinaryIO,
        filename: str,
        file_size: int,
        version: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Upload widget file to MinIO.
        
        Args:
            file_data: File content as binary stream
            filename: Original filename
            file_size: File size in bytes
            version: Widget version (optional)
            
        Returns:
            Dict with uploaded object keys
            
        Raises:
            ValueError: If validation fails
            Exception: If upload fails
        """
        self.validate_file(filename, file_size)
        
        keys = self.get_object_keys(version)
        uploaded_keys = {}
        
        if version and "versioned" in keys:
            versioned_key = keys["versioned"]
            logger.info(f"Uploading versioned widget: {versioned_key}")
            
            content = file_data.read()
            minio_service.upload_file(
                bucket_name=self.bucket,
                object_name=versioned_key,
                file_data=content,
                content_type="application/javascript"
            )
            uploaded_keys["versioned"] = versioned_key
            
            file_data.seek(0)
        
        latest_key = keys["latest"]
        logger.info(f"Uploading latest widget: {latest_key}")
        
        content = file_data.read()
        minio_service.upload_file(
            bucket_name=self.bucket,
            object_name=latest_key,
            file_data=content,
            content_type="application/javascript"
        )
        uploaded_keys["latest"] = latest_key
        
        logger.info(
            "Widget uploaded successfully",
            extra={
                "original_filename": filename,
                "file_size": file_size,
                "widget_version": version,
                "uploaded_keys": uploaded_keys
            }
        )
        
        return uploaded_keys
    
    def get_widget(self, version: Optional[str] = None) -> bytes:
        """
        Get widget file from MinIO.
        
        Args:
            version: Widget version (optional). If None, gets latest.
            
        Returns:
            File content as bytes
            
        Raises:
            FileNotFoundError: If file not found
        """
        keys = self.get_object_keys(version)
        object_name = keys.get("versioned") if version else keys["latest"]
        
        try:
            response = minio_service.client.get_object(self.bucket, object_name)
            content = response.read()
            response.close()
            response.release_conn()
            return content
            
        except Exception as e:
            logger.warning(f"Widget file not found: {object_name}")
            raise FileNotFoundError(WidgetFile.ERROR_FILE_NOT_FOUND)
    
    def list_widgets(self) -> List[Dict]:
        """
        List all widget files in MinIO.
        
        Returns:
            List of file metadata dicts
        """
        file_names = minio_service.list_files(
            bucket_name=self.bucket,
            prefix=f"{WidgetFile.STORAGE_PREFIX}/"
        )
        
        files = []
        for file_name in file_names:
            try:
                stat = minio_service.client.stat_object(self.bucket, file_name)
                
                files.append({
                    "filename": file_name.replace(f"{WidgetFile.STORAGE_PREFIX}/", ""),
                    "full_path": file_name,
                    "size": stat.size,
                    "last_modified": stat.last_modified.isoformat() if stat.last_modified else None,
                    "etag": stat.etag
                })
            except Exception as e:
                logger.warning(f"Failed to get stats for {file_name}: {e}")
                
        return files
    
    def delete_widget(self, filename: str) -> None:
        """
        Delete a widget file from MinIO.
        
        Args:
            filename: Object name/path in MinIO
            
        Raises:
            ValueError: If trying to delete latest version
            FileNotFoundError: If file not found
        """
        latest_key = self.get_object_keys()["latest"]
        if filename == latest_key:
            raise ValueError(WidgetFile.ERROR_CANNOT_DELETE_LATEST)
        
        try:
            minio_service.client.stat_object(self.bucket, filename)
        except Exception:
            raise FileNotFoundError(f"{WidgetFile.ERROR_FILE_NOT_FOUND}: {filename}")
        
        minio_service.client.remove_object(self.bucket, filename)
        
        logger.info(f"Widget file deleted: {filename}")
    
    def get_public_url(self, version: Optional[str] = None, base_url: Optional[str] = None) -> str:
        """
        Get public URL for widget file.
        
        Args:
            version: Widget version (optional)
            base_url: Base URL (optional). If not provided, uses BACKEND_URL from settings
            
        Returns:
            Public URL for widget
        """
        if not base_url:
            base_url = settings.BACKEND_URL
        
        endpoint = "/api/v1/widget/js"
        if version:
            return f"{base_url}{endpoint}?v={version}"
        return f"{base_url}{endpoint}"
    
    def generate_embed_snippet(self, base_url: Optional[str] = None) -> str:
        """
        Generate embed snippet for widget.
        
        Args:
            base_url: Base URL (optional). If not provided, uses BACKEND_URL from settings
            
        Returns:
            HTML script tag for embedding with defer attribute
        """
        url = self.get_public_url(base_url=base_url)
        return f'<script defer src="{url}" data-bot-id="YOUR_BOT_ID"></script>'

widget_service = WidgetService()
