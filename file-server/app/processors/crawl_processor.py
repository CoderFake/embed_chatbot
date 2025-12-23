"""
Crawl processor - handles crawl data processing from /tmp/crawl
"""
from typing import List, Dict, Any, Optional, Set
from pathlib import Path
import json
import asyncio

from app.processors.embedding import embedding_service
from app.processors.text_extractor import TextExtractor
from app.common.constants import ORIGIN_CRAWLER_CONFIG, BATCH_BROWSER_CONFIG
from app.storage.milvus_service import MilvusService
from app.progress.publisher import ProgressPublisher, TaskStatus
from app.services.batch_import import batch_import_service
from app.common.enums import TaskType
from app.core.redis_keys import RedisKeys
from app.core.crawl4ai_client import Crawl4AIClient
from app.config.settings import settings
from app.utils.logging import get_logger
from app.utils.datetime_utils import now

logger = get_logger(__name__)


class CrawlProcessor:
    """
    Processes crawl data from /tmp/crawl directory.
    
    Expected crawl data format:
    {
        "url": "https://example.com/page",
        "title": "Page Title",
        "content": "Page content text",
        "metadata": {
            "crawled_at": "2024-01-01T00:00:00Z",
            "status_code": 200,
            ...
        }
    }
    
    Features:
    - Batch processing for embeddings and Milvus insertion
    - Progress tracking
    - Error handling with partial success
    """
    
    def __init__(
        self,
        milvus_service: MilvusService,
        progress_publisher: Optional[ProgressPublisher] = None,
        redis_client = None
    ):
        """
        Initialize processor
        
        Args:
            milvus_service: Milvus service for vector storage
            progress_publisher: Optional progress publisher
            redis_client: Optional Redis client for checking cancellation
        """
        self.milvus_service = milvus_service
        self.progress_publisher = progress_publisher
        self.redis_client = redis_client
        self.milvus_batch_size = settings.MILVUS_BATCH_SIZE
    
    async def check_cancellation(self, bot_id: str):
        """Check if crawl task matches cancellation signal"""
        if self.redis_client:
            is_cancelled = await self.redis_client.exists(RedisKeys.crawl_stop(bot_id))
            if is_cancelled:
                logger.warning(f"Crawl task cancelled for bot {bot_id}")
                raise ValueError("Crawl task cancelled by user")
    
    async def process_crawl_file(
        self,
        crawl_file: Path,
        bot_id: str,
        task_id: str,
        crawl_id: str
    ) -> Dict[str, Any]:
        """
        Process a single crawl results file
        
        Args:
            crawl_file: Path to crawl JSON file in /tmp/crawl
            bot_id: Bot ID
            task_id: Task ID for progress tracking
            crawl_id: Crawl ID
            
        Returns:
            Processing result with statistics
        """
        start_time = now()
        
        try:
            logger.info(f"Loading crawl data from {crawl_file.name}")
            with open(crawl_file, 'r', encoding='utf-8') as f:
                crawl_data = json.load(f)
            
            if not isinstance(crawl_data, list):
                crawl_data = [crawl_data]
            
            if not crawl_data:
                return {
                    "success": False,
                    "error": "No crawl data found in file",
                    "file_name": crawl_file.name
                }
            
            total_pages = len(crawl_data)
            logger.info(f"Processing {total_pages} crawled pages from {crawl_file.name}")
            
            texts = []
            for page in crawl_data:
                text = ""
                if page.get("title"):
                    text += f"{page['title']}\n\n"
                if page.get("content"):
                    text += page["content"]
                
                if not text.strip():
                    logger.warning(f"Empty content for URL: {page.get('url', 'unknown')}")
                    continue
                
                texts.append(text)
            
            if not texts:
                return {
                    "success": False,
                    "error": "No valid text content extracted",
                    "file_name": crawl_file.name
                }
            
            logger.info(f"Generating embeddings for {len(texts)} pages")
            embeddings_result = await asyncio.to_thread(
                embedding_service.encode_documents,
                texts
            )
            embeddings = embeddings_result["dense_vectors"].tolist()
            
            documents = []
            for i, page in enumerate(crawl_data[:len(texts)]):
                documents.append({
                    "text": texts[i],
                    "document_id": crawl_id,
                    "web_url": page.get("url", ""),
                    "chunk_index": i,
                    "metadata": {
                        "crawl_id": crawl_id,
                        "title": page.get("title", ""),
                        "page_index": i,
                        **(page.get("metadata", {}))
                    }
                })
            

            collection_name = f"bot_{bot_id}".replace("-", "_")
            inserted_count = 0
            
            for batch_start in range(0, len(documents), self.milvus_batch_size):
                batch_end = min(batch_start + self.milvus_batch_size, len(documents))
                doc_batch = documents[batch_start:batch_end]
                emb_batch = embeddings[batch_start:batch_end]
                
                await self.milvus_service.insert_documents(
                    collection_name=collection_name,
                    documents=doc_batch,
                    embeddings=emb_batch
                )
                
                inserted_count += len(doc_batch)
                
                progress = (inserted_count / len(documents)) * 100
                if self.progress_publisher:
                    await self.progress_publisher.publish_progress(
                        task_id=task_id,
                        bot_id=bot_id,
                        progress=progress,
                        status=TaskStatus.PROCESSING,
                        message=f"Inserted {inserted_count}/{len(documents)} pages"
                    )
            
            processing_time = (now() - start_time).total_seconds()
            result = {
                "success": True,
                "file_name": crawl_file.name,
                "crawl_id": crawl_id,
                "pages_count": total_pages,
                "inserted_count": inserted_count,
                "processing_time": processing_time
            }
            
            try:
                crawl_file.unlink()
                logger.info(f"Cleaned up temporary crawl file: {crawl_file}")
            except Exception as e:
                logger.warning(f"Failed to delete temporary crawl file {crawl_file}: {e}")
            
            return result
        
        except Exception as e:
            logger.error(f"Failed to process crawl file {crawl_file.name}: {e}", exc_info=True)
            
            try:
                if crawl_file.exists():
                    crawl_file.unlink()
                    logger.info(f"Cleaned up temporary crawl file after error: {crawl_file}")
            except Exception as cleanup_error:
                logger.warning(f"Failed to delete temporary crawl file {crawl_file}: {cleanup_error}")
            
            return {
                "success": False,
                "error": str(e),
                "file_name": crawl_file.name
            }
    
    async def process_crawl_batch(
        self,
        crawl_files: List[Dict[str, Any]],
        bot_id: str,
        task_id: str
    ) -> Dict[str, Any]:
        """
        Process multiple crawl files in a batch
        
        Args:
            crawl_files: List of crawl file info dicts with 'path' and 'crawl_id'
            bot_id: Bot ID
            task_id: Task ID for progress tracking
            
        Returns:
            Batch processing result with statistics
        """
        start_time = now()
        results = []
        total_files = len(crawl_files)
        
        logger.info(f"Processing batch of {total_files} crawl files")
        
        if self.progress_publisher:
            await self.progress_publisher.publish_start(
                task_id=task_id,
                bot_id=bot_id,
                task_type="crawl_batch",
                total_items=total_files
            )
        
        for i, file_info in enumerate(crawl_files):
            crawl_file_path = Path(file_info["path"])
            crawl_id = file_info["crawl_id"]
            
            result = await self.process_crawl_file(
                crawl_file=crawl_file_path,
                bot_id=bot_id,
                task_id=task_id,
                crawl_id=crawl_id
            )
            
            results.append(result)
            
            progress = ((i + 1) / total_files) * 100
            if self.progress_publisher:
                await self.progress_publisher.publish_progress(
                    task_id=task_id,
                    bot_id=bot_id,
                    progress=progress,
                    status=TaskStatus.PROCESSING,
                    message=f"Processed {i + 1}/{total_files} files"
                )
        
        successful_files = sum(1 for r in results if r.get("success"))
        failed_files = total_files - successful_files
        total_pages = sum(r.get("pages_count", 0) for r in results)
        total_inserted = sum(r.get("inserted_count", 0) for r in results)
        
        processing_time = (now() - start_time).total_seconds()
        
        return {
            "success": failed_files == 0,
            "total_files": total_files,
            "successful_files": successful_files,
            "failed_files": failed_files,
            "total_pages": total_pages,
            "total_inserted": total_inserted,
            "processing_time": processing_time,
            "results": results
        }
    
    async def process_crawl_direct(
        self,
        origin: str,
        sitemap_urls: Optional[List[str]],
        collection_name: str,
        bot_id: str,
        task_id: str
    ) -> Dict[str, Any]:
        """
        Process crawl data directly from URLs using Crawl4AI service
        
        Args:
            origin: Origin domain to crawl
            sitemap_urls: Optional list of specific URLs to crawl
            collection_name: Milvus collection name
            bot_id: Bot ID
            task_id: Task ID for progress tracking
            
        Returns:
            Processing result with statistics
        """
        start_time = now()
        
        try:
            if self.progress_publisher:
                await self.progress_publisher.publish_start(
                    task_id=task_id,
                    bot_id=bot_id,
                    task_type=TaskType.CRAWL.value,
                    total_items=len(sitemap_urls) if sitemap_urls else 1
                )
            
            crawl_mode = f"{len(sitemap_urls)} URLs" if sitemap_urls else "BFS from origin"
            logger.info(f"Starting crawl for {origin} ({crawl_mode})")
            
            if self.progress_publisher:
                await self.progress_publisher.publish_progress(
                    task_id=task_id,
                    bot_id=bot_id,
                    progress=5,
                    status=TaskStatus.PROCESSING,
                    message=f"Crawling {origin}..."
                )
            
            all_crawl_results = []
            crawled_urls: Set[str] = set()
            urls_queue: List[str] = []
            total_chunks_inserted = 0
            successful_pages = 0
            failed_pages = 0
            crawled_pages_info = []
            text_extractor = TextExtractor()
            
            async with Crawl4AIClient() as client:
                if sitemap_urls:
                    logger.info(f"Sitemap mode: Crawling {len(sitemap_urls)} URLs")
                    
                    for i in range(0, len(sitemap_urls), settings.CRAWL_BATCH_SIZE):
                        await self.check_cancellation(bot_id)
                        batch = sitemap_urls[i:i + settings.CRAWL_BATCH_SIZE]
                        
                        if len(crawled_urls) >= settings.MAX_CRAWL_PAGES:
                            break
                        
                        logger.info(f"Crawling batch {i//settings.CRAWL_BATCH_SIZE + 1}: {len(batch)} URLs")
                        
                        payload = {
                            "urls": batch,
                            "browser_config": BATCH_BROWSER_CONFIG
                        }
                        
                        try:
                            response = await client.crawl(payload)
                            results = response.get("results", [])
                        except Exception as e:
                            logger.error(f"Failed to crawl sitemap batch {i//settings.CRAWL_BATCH_SIZE + 1}: {e}")
                            
                            continue
                        
                        batch_chunks = []
                        for result in results:
                            url = result.get("url", "")
                            if url and url not in crawled_urls:
                                crawled_urls.add(url)
                                all_crawl_results.append(result)
                                
                                chunk_result = await self._extract_and_chunk_page(
                                    result, text_extractor, len(all_crawl_results) - 1
                                )
                                
                                if chunk_result["success"]:
                                    batch_chunks.extend(chunk_result["chunks"])
                                    successful_pages += 1
                                else:
                                    failed_pages += 1
                                
                                crawled_pages_info.append(chunk_result["page_info"])
                        
                        if batch_chunks:
                            inserted = await self._process_and_insert_chunks(
                                chunks=batch_chunks,
                                collection_name=collection_name,
                                bot_id=bot_id,
                                task_id=task_id,
                                embedding_batch_size=settings.CRAWL_EMBEDDING_BATCH_SIZE
                            )
                            total_chunks_inserted += inserted
                        
                        progress = 10 + (len(crawled_urls) / len(sitemap_urls)) * 85
                        if self.progress_publisher:
                            await self.progress_publisher.publish_progress(
                                task_id=task_id,
                                bot_id=bot_id,
                                progress=int(progress),
                                status=TaskStatus.PROCESSING,
                                message=f"Processed {len(crawled_urls)}/{len(sitemap_urls)} URLs, inserted {total_chunks_inserted} vectors"
                            )
                
                else:
                    logger.info(f"BFS mode: Starting with origin {origin}")
                    
                    payload = {
                        "urls": [origin],
                        "crawler_config": ORIGIN_CRAWLER_CONFIG
                    }
                    
                    response = await client.crawl(payload)
                    results = response.get("results", [])
                    
                    if not results:
                        raise ValueError(f"Failed to crawl origin: {origin}")
                    
                    origin_result = results[0]
                    origin_url = origin_result.get("url", "")
                    if origin_url:
                        crawled_urls.add(origin_url)
                        all_crawl_results.append(origin_result)
                    
                    chunk_result = await self._extract_and_chunk_page(
                        origin_result, text_extractor, 0
                    )
                    
                    if chunk_result["success"]:
                        inserted = await self._process_and_insert_chunks(
                            chunks=chunk_result["chunks"],
                            collection_name=collection_name,
                            bot_id=bot_id,
                            task_id=task_id,
                            embedding_batch_size=settings.CRAWL_EMBEDDING_BATCH_SIZE
                        )
                        total_chunks_inserted += inserted
                        successful_pages += 1
                    else:
                        failed_pages += 1
                    
                    crawled_pages_info.append(chunk_result["page_info"])
                    
                    links = origin_result.get("links", {})
                    internal_links = links.get("internal", [])
                    
                    for link in internal_links:
                        if isinstance(link, dict):
                            href = link.get("href", "")
                            if href and href not in crawled_urls and href.startswith(("http://", "https://")):
                                urls_queue.append(href)
                    
                    urls_queue = list(dict.fromkeys(urls_queue))
                    
                    logger.info(f"Found {len(urls_queue)} internal links from origin")
                    
                    batch_num = 1
                    while urls_queue and len(crawled_urls) < settings.MAX_CRAWL_PAGES:
                        await self.check_cancellation(bot_id)
                        batch_size = min(settings.CRAWL_BATCH_SIZE, settings.MAX_CRAWL_PAGES - len(crawled_urls))
                        batch = urls_queue[:batch_size]
                        urls_queue = urls_queue[batch_size:]
                        
                        logger.info(f"Crawling batch {batch_num}: {len(batch)} URLs")
                        logger.debug(f"Batch URLs: {batch[:3]}..." if len(batch) > 3 else f"Batch URLs: {batch}")
                        
                        payload = {
                            "urls": batch,
                            "browser_config": BATCH_BROWSER_CONFIG
                        }
                        
                        try:
                            response = await client.crawl(payload)
                            results = response.get("results", [])
                        except Exception as e:
                            logger.error(f"Failed to crawl batch {batch_num}: {e}")
                            failed_pages += len(batch)
                            for url in batch:
                                crawled_pages_info.append({
                                    "url": url,
                                    "title": None,
                                    "chunks_count": 0,
                                    "success": False,
                                    "error": f"Crawl API error: {str(e)}"
                                })
                            batch_num += 1
                            continue
                        
                        batch_chunks = []
                        for result in results:
                            url = result.get("url", "")
                            if url and url not in crawled_urls:
                                crawled_urls.add(url)
                                all_crawl_results.append(result)
                                
                                chunk_result = await self._extract_and_chunk_page(
                                    result, text_extractor, len(all_crawl_results) - 1
                                )
                                
                                if chunk_result["success"]:
                                    batch_chunks.extend(chunk_result["chunks"])
                                    successful_pages += 1
                                else:
                                    failed_pages += 1
                                
                                crawled_pages_info.append(chunk_result["page_info"])
                                
                                if len(crawled_urls) < settings.MAX_CRAWL_PAGES:
                                    links = result.get("links", {})
                                    internal_links = links.get("internal", [])
                                    
                                    for link in internal_links:
                                        if isinstance(link, dict):
                                            href = link.get("href", "")
                                            if (href and 
                                                href not in crawled_urls and 
                                                href not in urls_queue and 
                                                href.startswith(("http://", "https://"))):
                                                urls_queue.append(href)
                        
                        if batch_chunks:
                            inserted = await self._process_and_insert_chunks(
                                chunks=batch_chunks,
                                collection_name=collection_name,
                                bot_id=bot_id,
                                task_id=task_id,
                                embedding_batch_size=settings.CRAWL_EMBEDDING_BATCH_SIZE
                            )
                            total_chunks_inserted += inserted
                        
                        batch_num += 1
                        
                        progress = 10 + (len(crawled_urls) / settings.MAX_CRAWL_PAGES) * 85
                        if self.progress_publisher:
                            await self.progress_publisher.publish_progress(
                                task_id=task_id,
                                bot_id=bot_id,
                                progress=int(progress),
                                status=TaskStatus.PROCESSING,
                                message=f"Processed {len(crawled_urls)} pages, inserted {total_chunks_inserted} vectors"
                            )
            
            if not all_crawl_results:
                raise ValueError("No pages crawled")
            
            total_pages = len(all_crawl_results)
            logger.info(f"Completed crawl: {total_pages} pages, {successful_pages} successful, {failed_pages} failed")
            logger.info(f"Total chunks inserted: {total_chunks_inserted}")
            
            self.milvus_service.flush_collection(collection_name)
            
            duration = (now() - start_time).total_seconds()
            
            result = {
                "success": True,
                "origin": origin,
                "crawl_mode": crawl_mode,
                "total_pages": total_pages,
                "successful_pages": successful_pages,
                "failed_pages": failed_pages,
                "total_chunks": total_chunks_inserted,
                "inserted_vectors": total_chunks_inserted,
                "duration_seconds": duration,
                "crawled_pages": crawled_pages_info
            }
            
            if self.progress_publisher:
                await self.progress_publisher.publish_completion(
                    task_id=task_id,
                    bot_id=bot_id,
                    success=True,
                    message=f"Crawled and processed {successful_pages} pages successfully",
                    metadata=result
                )
            
            return result
            
        except Exception as e:
            logger.error(f"Crawl processing failed: {e}", exc_info=True)
            
            if self.progress_publisher:
                await self.progress_publisher.publish_completion(
                    task_id=task_id,
                    bot_id=bot_id,
                    success=False,
                    message=f"Crawl processing failed: {str(e)}"
                )
            
            raise ValueError(f"Crawl processing failed: {str(e)}")
    
    async def _extract_and_chunk_page(
        self,
        result: Dict[str, Any],
        text_extractor: TextExtractor,
        page_index: int
    ) -> Dict[str, Any]:
        """
        Extract markdown and chunk a single crawl result
        
        Args:
            result: Crawl result from Crawl4AI
            text_extractor: TextExtractor instance
            page_index: Index of this page in crawl sequence
            
        Returns:
            Dict with success, chunks, and page_info
        """
        url = result.get("url", "")
        success = result.get("success", False)
        
        if not success:
            error = result.get("error", "Unknown error")
            logger.warning(f"Failed to crawl: {url} - {error}")
            return {
                "success": False,
                "chunks": [],
                "page_info": {
                    "url": url,
                    "title": None,
                    "chunks_count": 0,
                    "success": False,
                    "error": error
                }
            }
        
        try:
            markdown_data = result.get("markdown", {})
            if isinstance(markdown_data, dict):
                markdown_content = markdown_data.get("raw_markdown", "")
            else:
                markdown_content = str(markdown_data) if markdown_data else ""
            
            if not markdown_content:
                logger.warning(f"No markdown content for {url}")
                return {
                    "success": False,
                    "chunks": [],
                    "page_info": {
                        "url": url,
                        "title": None,
                        "chunks_count": 0,
                        "success": False,
                        "error": "No markdown content"
                    }
                }
            
            chunks = await asyncio.to_thread(
                text_extractor.chunk_text,
                markdown_content
            )
            
            page_title = result.get("metadata", {}).get("title", "") if result.get("metadata") else ""
            
            chunk_list = []
            for j, chunk in enumerate(chunks):
                chunk_list.append({
                    "text": chunk.page_content,
                    "metadata": {
                        "url": url,
                        "title": page_title,
                        "chunk_index": j,
                        "total_chunks": len(chunks),
                        "page_index": page_index,
                        "crawled_at": now().isoformat()
                    }
                })
            
            return {
                "success": True,
                "chunks": chunk_list,
                "page_info": {
                    "url": url,
                    "title": page_title,
                    "chunks_count": len(chunks),
                    "success": True,
                    "error": None
                }
            }
            
        except Exception as e:
            logger.error(f"Error processing page {url}: {e}")
            return {
                "success": False,
                "chunks": [],
                "page_info": {
                    "url": url,
                    "title": result.get("metadata", {}).get("title", "") if result.get("metadata") else "",
                    "chunks_count": 0,
                    "success": False,
                    "error": str(e)
                }
            }
    
    async def _process_and_insert_chunks(
        self,
        chunks: List[Dict[str, Any]],
        collection_name: str,
        bot_id: str,
        task_id: str,
        embedding_batch_size: Optional[int] = None
    ) -> int:
        """
        Generate embeddings in batches and insert into Milvus
        
        Args:
            chunks: List of chunk dicts with text and metadata
            collection_name: Milvus collection name
            bot_id: Bot ID
            task_id: Task ID
            embedding_batch_size: Number of chunks to process per embedding batch (default from settings)
            
        Returns:
            Number of vectors inserted
        """
        if not chunks:
            return 0
        
        if embedding_batch_size is None:
            embedding_batch_size = settings.CRAWL_EMBEDDING_BATCH_SIZE
        
        total_inserted = 0
        _chunk_id_offset = 0
        global_batch_index = 0

        _total_embedding_batches = (len(chunks) + embedding_batch_size - 1) // embedding_batch_size
        total_milvus_batches = 0
        for batch_start in range(0, len(chunks), embedding_batch_size):
            batch_end = min(batch_start + embedding_batch_size, len(chunks))
            chunk_batch = chunks[batch_start:batch_end]
            total_milvus_batches += (len(chunk_batch) + self.milvus_batch_size - 1) // self.milvus_batch_size
        
        for batch_start in range(0, len(chunks), embedding_batch_size):
            batch_end = min(batch_start + embedding_batch_size, len(chunks))
            chunk_batch = chunks[batch_start:batch_end]
            
            texts = [chunk["text"] for chunk in chunk_batch]
            
            embed_start = now()
            embeddings_result = await asyncio.to_thread(
                embedding_service.encode_documents,
                texts
            )
            embed_duration = (now() - embed_start).total_seconds()
            
            embeddings = embeddings_result["dense_vectors"].tolist()
            logger.debug(f"Generated {len(embeddings)} embeddings in {embed_duration:.2f}s")
            
            documents = []
            for i, chunk in enumerate(chunk_batch):
                documents.append({
                    "text": chunk["text"],
                    "document_id": f"crawl_{task_id}",
                    "web_url": chunk["metadata"].get("url", ""),
                    "chunk_index": chunk["metadata"].get("chunk_index", i),
                    "metadata": {
                        **chunk["metadata"],
                        "bot_id": bot_id,
                        "source": "crawl"
                    }
                })
            
            for milvus_batch_start in range(0, len(documents), self.milvus_batch_size):
                milvus_batch_end = min(milvus_batch_start + self.milvus_batch_size, len(documents))
                doc_batch = documents[milvus_batch_start:milvus_batch_end]
                emb_batch = embeddings[milvus_batch_start:milvus_batch_end]
                
                await self.milvus_service.insert_documents(
                    collection_name=collection_name,
                    documents=doc_batch,
                    embeddings=emb_batch
                )
                
                total_inserted += len(doc_batch)
                
                web_url = doc_batch[0].get("web_url", "") if doc_batch else ""
                
                await batch_import_service.notify_batch_completion(
                    task_id=task_id,
                    bot_id=bot_id,
                    document_id=f"crawl_{task_id}",
                    batch_index=global_batch_index,
                    total_batches=total_milvus_batches,
                    chunks_in_batch=len(doc_batch),
                    batch_data=doc_batch,
                    source_type="crawl",
                    web_url=web_url
                )
                
                global_batch_index += 1
            
            logger.info(f"Processed and inserted embedding batch {batch_start}-{batch_end}: {len(documents)} vectors")
        
        return total_inserted