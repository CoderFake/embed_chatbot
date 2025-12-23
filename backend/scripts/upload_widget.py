#!/usr/bin/env python3
"""
Upload widget.js to backend via API

Usage:
    # From host machine (local):
    python backend/scripts/upload_widget.py --url http://localhost:18000
    
    # From host machine (production):
    python backend/scripts/upload_widget.py --url https://your-domain.com
    
    # From Docker container (reads credentials from .env):
    docker exec embed_chatbot_backend python scripts/upload_widget.py
"""

import argparse
import os
import sys
from pathlib import Path
import requests
from getpass import getpass

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
WIDGET_FILE = PROJECT_ROOT / "app" / "static" / "widget" / "standalone-widget.js"

# API Configuration
API_URL = os.getenv("BACKEND_URL", "http://localhost:18000")
LOGIN_ENDPOINT = "/api/v1/auth/login"
UPLOAD_ENDPOINT = "/api/v1/widget/admin/upload"


def login(email: str, password: str) -> str:
    """Login and get access token"""
    print("Logging in...")
    
    try:
        response = requests.post(
            f"{API_URL}{LOGIN_ENDPOINT}",
            json={"email": email, "password": password},
            timeout=10
        )
        response.raise_for_status()
        
        data = response.json()
        token = data.get("access_token")
        
        if not token:
            print("No access token in response")
            sys.exit(1)
        
        print("Login successful")
        return token
        
    except Exception as e:
        print(f"Login failed: {e}")
        sys.exit(1)


def upload_widget(token: str, version: str = None):
    """Upload widget file to backend"""
    
    if not WIDGET_FILE.exists():
        print(f"Widget file not found: {WIDGET_FILE}")
        sys.exit(1)
    
    print("\nUploading widget to backend...")
    print(f"   File: {WIDGET_FILE}")
    print(f"   Size: {WIDGET_FILE.stat().st_size:,} bytes")
    print(f"   Version: {version or 'latest'}")
    
    # Prepare request
    url = f"{API_URL}{UPLOAD_ENDPOINT}"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    with open(WIDGET_FILE, 'rb') as f:
        files = {
            'file': ('standalone-widget.js', f, 'application/javascript')
        }
        data = {}
        if version:
            data['version'] = version
        
        try:
            response = requests.post(
                url,
                headers=headers,
                files=files,
                data=data,
                timeout=60
            )
            
            response.raise_for_status()
            result = response.json()
            
            print("\nUpload successful!")
            print(f"\nFile Info:")
            print(f"   Filename: {result['file']['filename']}")
            print(f"   Size: {result['file']['size']:,} bytes")
            print(f"   Version: {result['file']['version']}")
            
            print(f"\nURLs:")
            print(f"   Latest: {result['urls']['latest']}")
            if result['urls'].get('versioned'):
                print(f"   Versioned: {result['urls']['versioned']}")
            
            print(f"\nEmbed snippet:")
            print(f"   {result['embed_snippet']}")
            
            print("   Customers can embed the script tag above into their websites.")
            
        except requests.exceptions.HTTPError as e:
            print(f"\nUpload failed: {e}")
            if e.response:
                try:
                    error_detail = e.response.json()
                    print(f"   Error: {error_detail.get('detail', 'Unknown error')}")
                except:
                    print(f"   Response: {e.response.text}")
            sys.exit(1)
            
        except Exception as e:
            print(f"\nUpload failed: {e}")
            sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Upload widget.js to backend")
    parser.add_argument(
        "--url",
        default=os.getenv("BACKEND_URL", "http://localhost:18000"),
        help="Backend API URL (default: from BACKEND_URL env or http://localhost:18000)"
    )
    parser.add_argument(
        "--email",
        default=os.getenv("ROOT_EMAIL", "admin@example.com"),
        help="Root user email (default: from ROOT_EMAIL env or admin@example.com)"
    )
    parser.add_argument(
        "--password",
        default=os.getenv("ROOT_PASSWORD"),
        help="Root user password (default: from ROOT_PASSWORD env, will prompt if not set)"
    )
    parser.add_argument(
        "--version",
        help="Widget version (e.g., 1.0.0). If not specified, uploads as latest only"
    )
    
    args = parser.parse_args()
    
    global API_URL
    API_URL = args.url.rstrip('/')
    
    # Get password
    password = args.password
    if not password:
        password = getpass(f"Enter password for {args.email}: ")
        
        if not password:
            print("Password is required")
            sys.exit(1)
    
    # Login and get token
    token = login(api_url, args.email, password)
    
    # Upload widget
    upload_widget(api_url, token, args.version)


if __name__ == "__main__":
    main()
