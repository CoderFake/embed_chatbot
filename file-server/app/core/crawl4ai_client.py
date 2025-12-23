"""
Crawl4AI API Client
Simple HTTP client to connect to Crawl4AI service
"""
import httpx
import json
from typing import Dict, Any, List

from app.config.settings import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class Crawl4AIClient:
    """
    HTTP client for Crawl4AI API service.
    
    This is just a connection client
    All processing logic should be in processors.
    """
    
    def __init__(self):
        """Initialize HTTP client with auth from settings"""
        self.base_url = settings.CRAWL4AI_URL
        self.api_token = settings.CRAWL4AI_API_TOKEN
        self.timeout = settings.CRAWL4AI_TIMEOUT
        
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers={"Authorization": f"Bearer {self.api_token}"}
        )
    
    async def crawl(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send crawl request to Crawl4AI API
        
        Args:
            payload: Request payload (urls, crawler_config, etc.)
            
        Returns:
            Dict with "results" key containing list of crawl results
            
        Raises:
            httpx.HTTPError: If request fails
        """
        try:
            response = await self.client.post("/crawl", json=payload)
            response.raise_for_status()
            
            response_text = response.text
            logger.info(f"Crawl4AI response length: {len(response_text)} chars")
            
           
            try:
                data = response.json()
                if isinstance(data, dict):
                    if "results" in data and isinstance(data["results"], list):
                        results = data["results"]
                        results = [data]
                elif isinstance(data, list):
                    results = data
                else:
                    results = []
            except json.JSONDecodeError:
                results = []
                for line in response_text.strip().split('\n'):
                    if line.strip():
                        try:
                            results.append(json.loads(line))
                        except json.JSONDecodeError as e:
                            logger.warning(f"Failed to parse JSON line: {e}")
                            continue
            
            logger.info(f"Parsed {len(results)} crawl results")
            
            return {"results": results}
            
        except httpx.HTTPError as e:
            logger.error(f"Crawl4AI API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error calling Crawl4AI: {e}")
            if 'response' in locals():
                logger.error(f"Response text (first 500 chars): {response.text[:500]}")
            raise
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()
    
    async def __aenter__(self):
        """Context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        await self.close()
