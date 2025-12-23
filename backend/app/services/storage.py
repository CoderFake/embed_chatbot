from minio import Minio
from minio.error import S3Error
from typing import Optional
import io

from app.config.settings import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class MinIOService:
    """
    MinIO object storage service for managing buckets and files.
    """
    
    def __init__(self):
        self.client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE
        )
    
    def create_bucket(self, bucket_name: str) -> bool:
        """
        Create a new bucket for bot's documents.
        
        Args:
            bucket_name: S3-compatible bucket name (UUID without hyphens from bot.bucket_name)
                        Example: a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
            
        Returns:
            True if created successfully
        """
        try:
            if self.client.bucket_exists(bucket_name):
                logger.warning(f"Bucket {bucket_name} already exists")
                return True
            
            self.client.make_bucket(bucket_name)
            
            logger.info(f"Created MinIO bucket: {bucket_name}")
            return True
            
        except S3Error as e:
            logger.error(f"Failed to create bucket {bucket_name}: {e}")
            raise
    
    def delete_bucket(self, bucket_name: str, force: bool = False) -> bool:
        """
        Delete a bucket.
        
        Args:
            bucket_name: Name of bucket to delete
            force: If True, delete all objects first
            
        Returns:
            True if deleted successfully
        """
        try:
            if not self.client.bucket_exists(bucket_name):
                logger.warning(f"Bucket {bucket_name} does not exist")
                return False
            
            if force:
                objects = self.client.list_objects(bucket_name, recursive=True)
                for obj in objects:
                    self.client.remove_object(bucket_name, obj.object_name)
            
            self.client.remove_bucket(bucket_name)
            
            logger.info(f"Deleted MinIO bucket: {bucket_name}")
            return True
            
        except S3Error as e:
            logger.error(f"Failed to delete bucket {bucket_name}: {e}")
            raise
    
    def bucket_exists(self, bucket_name: str) -> bool:
        """
        Check if bucket exists.
        
        Args:
            bucket_name: Name of bucket
            
        Returns:
            True if exists
        """
        try:
            return self.client.bucket_exists(bucket_name)
        except S3Error as e:
            logger.error(f"Failed to check bucket {bucket_name}: {e}")
            return False
    
    def upload_file(
        self,
        bucket_name: str,
        object_name: str,
        file_data: bytes,
        content_type: str = "application/octet-stream"
    ) -> str:
        """
        Upload file to bucket.
        
        Args:
            bucket_name: Bucket name
            object_name: Object name in bucket
            file_data: File content as bytes
            content_type: MIME type of file
            
        Returns:
            Object path
        """
        try:
            if not self.client.bucket_exists(bucket_name):
                self.create_bucket(bucket_name)
            
            self.client.put_object(
                bucket_name,
                object_name,
                io.BytesIO(file_data),
                length=len(file_data),
                content_type=content_type
            )
            
            logger.info(f"Uploaded file to {bucket_name}/{object_name}")
            return f"{bucket_name}/{object_name}"
            
        except S3Error as e:
            logger.error(f"Failed to upload file to {bucket_name}/{object_name}: {e}")
            raise
    
    def download_file(self, bucket_name: str, object_name: str) -> bytes:
        """
        Download file from bucket.
        
        Args:
            bucket_name: Bucket name
            object_name: Object name
            
        Returns:
            File content as bytes
        """
        try:
            response = self.client.get_object(bucket_name, object_name)
            data = response.read()
            response.close()
            response.release_conn()
            
            return data
            
        except S3Error as e:
            logger.error(f"Failed to download file from {bucket_name}/{object_name}: {e}")
            raise
    
    def delete_file(self, bucket_name: str, object_name: str) -> bool:
        """
        Delete file from bucket.
        
        Args:
            bucket_name: Bucket name
            object_name: Object name
            
        Returns:
            True if deleted successfully
        """
        try:
            self.client.remove_object(bucket_name, object_name)
            logger.info(f"Deleted file from {bucket_name}/{object_name}")
            return True
            
        except S3Error as e:
            logger.error(f"Failed to delete file from {bucket_name}/{object_name}: {e}")
            raise
    
    def list_files(self, bucket_name: str, prefix: str = "") -> list:
        """
        List files in bucket.
        
        Args:
            bucket_name: Bucket name
            prefix: Object prefix filter
            
        Returns:
            List of object names
        """
        try:
            objects = self.client.list_objects(bucket_name, prefix=prefix, recursive=True)
            return [obj.object_name for obj in objects]
            
        except S3Error as e:
            logger.error(f"Failed to list files in {bucket_name}: {e}")
            return []
    
    def set_bucket_policy_public(self, bucket_name: str) -> bool:
        """Set bucket policy to public read (no auth required)."""
        import json
        
        policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"AWS": ["*"]},
                "Action": ["s3:GetObject"],
                "Resource": [f"arn:aws:s3:::{bucket_name}/*"]
            }]
        }
        
        try:
            self.client.set_bucket_policy(bucket_name, json.dumps(policy))
            logger.info(f"Set public policy for bucket: {bucket_name}")
            return True
        except S3Error as e:
            logger.error(f"Failed to set public policy: {e}")
            raise
    
    def upload_public_file(self, object_name: str, file_data: bytes, content_type: str = "image/jpeg") -> str:
        """Upload to public bucket, return public URL."""
        bucket_name = settings.MINIO_PUBLIC_BUCKET
        
        if not self.client.bucket_exists(bucket_name):
            self.create_bucket(bucket_name)
            self.set_bucket_policy_public(bucket_name)
        
        self.upload_file(bucket_name, object_name, file_data, content_type)
        return f"{settings.MINIO_PUBLIC_URL}/{bucket_name}/{object_name}"
    
    def delete_public_file(self, object_name: str) -> bool:
        """Delete from public bucket."""
        return self.delete_file(settings.MINIO_PUBLIC_BUCKET, object_name)


# Global instance
    
    def set_bucket_policy_public(self, bucket_name: str) -> bool:
        """
        Set bucket policy to public read (anonymous GET requests allowed).
        
        Args:
            bucket_name: Bucket name to make public
            
        Returns:
            True if policy set successfully
        """
        import json
        
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": ["*"]},
                    "Action": ["s3:GetObject"],
                    "Resource": [f"arn:aws:s3:::{bucket_name}/*"]
                }
            ]
        }
        
        try:
            self.client.set_bucket_policy(bucket_name, json.dumps(policy))
            logger.info(f"Set public read policy for bucket: {bucket_name}")
            return True
        except S3Error as e:
            logger.error(f"Failed to set public policy for {bucket_name}: {e}")
            raise
    
    def upload_public_file(
        self,
        object_name: str,
        file_data: bytes,
        content_type: str = "image/jpeg"
    ) -> str:
        """
        Upload file to public bucket and return public URL (no auth required to access).
        
        Args:
            object_name: Path in bucket (e.g., "avatars/bot-123.jpg")
            file_data: File content as bytes
            content_type: MIME type
            
        Returns:
            Public URL that can be accessed without authentication
        """
        bucket_name = settings.MINIO_PUBLIC_BUCKET
        
        if not self.client.bucket_exists(bucket_name):
            self.create_bucket(bucket_name)
            self.set_bucket_policy_public(bucket_name)
        
        # Upload file
        self.upload_file(bucket_name, object_name, file_data, content_type)
        
        # Generate public URL
        public_url = f"{settings.MINIO_PUBLIC_URL}/{bucket_name}/{object_name}"
        logger.info(f"Uploaded public file: {public_url}")
        return public_url
    
    def delete_public_file(self, object_name: str) -> bool:
        """
        Delete file from public bucket.
        
        Args:
            object_name: Object path (e.g., "avatars/bot-123.jpg")
            
        Returns:
            True if deleted successfully
        """
        return self.delete_file(settings.MINIO_PUBLIC_BUCKET, object_name)
    
    def get_public_url(self, object_name: str) -> str:
        """
        Get public URL for object (without uploading).
        
        Args:
            object_name: Object path in public bucket
            
        Returns:
            Public URL
        """
        return f"{settings.MINIO_PUBLIC_URL}/{settings.MINIO_PUBLIC_BUCKET}/{object_name}"


# Global instance
minio_service = MinIOService()

