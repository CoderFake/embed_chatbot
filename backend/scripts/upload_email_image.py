#!/usr/bin/env python3
"""
Upload email branding image to MinIO
Runs during Docker build to ensure logo is available for emails
"""
import os
import sys
from pathlib import Path

try:
    from minio import Minio
    from minio.error import S3Error
except ImportError:
    print("Warning: minio package not installed, skipping upload")
    sys.exit(0)

# Configuration from environment
MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT')
MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY', 'minioadmin')
MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY', 'minioadmin')
MINIO_BUCKET = 'public-assets'
MINIO_PUBLIC_URL = os.getenv('MINIO_PUBLIC_URL')

# File to upload
SCRIPT_DIR = Path(__file__).parent
IMAGE_PATH = SCRIPT_DIR.parent / "app" / "static" / "img" / "email.jpg"
OBJECT_NAME = "avatars/email-logo.jpg"


def upload_logo():
    """Upload email logo to MinIO"""
    if not IMAGE_PATH.exists():
        print(f"Error: Image not found at {IMAGE_PATH}")
        sys.exit(1)
    
    print(f"Uploading {IMAGE_PATH.name} to MinIO...")
    print(f"  Endpoint: {MINIO_ENDPOINT}")
    print(f"  Bucket: {MINIO_BUCKET}")
    print(f"  Object: {OBJECT_NAME}")
    
    try:
        client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=False 
        )
        
        if not client.bucket_exists(MINIO_BUCKET):
            client.make_bucket(MINIO_BUCKET)
            print(f"  Created bucket: {MINIO_BUCKET}")
        
        client.fput_object(
            MINIO_BUCKET,
            OBJECT_NAME,
            str(IMAGE_PATH),
            content_type="image/jpeg"
        )
        
        public_url = f"{MINIO_PUBLIC_URL}/{MINIO_BUCKET}/{OBJECT_NAME}"
        print(f"Upload successful!")
        print(f"   Public URL: {public_url}")
        
        url_file = SCRIPT_DIR.parent / "app" / "static" / "email_logo_url.txt"
        url_file.write_text(public_url)
        print(f"   URL saved to: {url_file.name}")
        
        return public_url
        
    except S3Error as e:
        print(f"MinIO error: {e}")
        print("   Continuing anyway - emails will use fallback")
        sys.exit(0)  
    except Exception as e:
        print(f"Upload failed: {e}")
        print("   Continuing anyway - emails will use fallback")
        sys.exit(0) 


if __name__ == "__main__":
    upload_logo()
