"""
File processor - orchestrates file processing (extraction → chunking → embedding → storage)
"""
from typing import List, Dict, Any, Optional
from pathlib import Path
import asyncio

from app.processors.text_extractor import TextExtractor
from app.processors.embedding import embedding_service
from app.storage.milvus_service import MilvusService
from app.storage.minio_service import MinIOService
from app.progress.publisher import ProgressPublisher
from app.services.batch_import import batch_import_service
from app.common.enums import TaskType
from app.config.settings import settings
from app.utils.logging import get_logger
from app.utils.datetime_utils import now

logger = get_logger(__name__)


class FileProcessor:
    """
    Orchestrates complete file processing pipeline:
    1. Text extraction from files
    2. Chunking into manageable pieces
    3. Embedding generation
    4. Storage in Milvus + MinIO
    
    Features:
    - Batch processing (MinIO: 100 items, Milvus: 1000 vectors)
    - Progress tracking with throttling
    - Error handling with partial success
    """
    
    def __init__(
        self,
        milvus_service: MilvusService,
        minio_service: MinIOService,
        progress_publisher: Optional[ProgressPublisher] = None
    ):
        """
        Initialize processor
        
        Args:
            milvus_service: Milvus service for vector storage
            minio_service: MinIO service for file storage
            progress_publisher: Optional progress publisher
        """
        self.text_extractor = TextExtractor()
        self.milvus_service = milvus_service
        self.minio_service = minio_service
        self.progress_publisher = progress_publisher
        
        self.minio_batch_size = settings.MINIO_BATCH_SIZE
        self.milvus_batch_size = settings.MILVUS_BATCH_SIZE
    
    async def process_file(
        self,
        file_path: Path,
        bot_id: str,
        task_id: str,
        document_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process a single file
        
        Args:
            file_path: Path to file in /tmp/uploads
            bot_id: Bot ID
            task_id: Task ID for progress tracking
            document_id: Document ID for Milvus
            metadata: Additional metadata
            
        Returns:
            Processing result with statistics
        """
        start_time = now()

        try:
            if self.progress_publisher:
                await self.progress_publisher.publish_progress(
                    task_id=task_id,
                    bot_id=bot_id,
                    progress=5,
                    status="processing",
                    message=f"Extracting text from {file_path.name}",
                    force=True
                )

            logger.info(f"Extracting text from {file_path.name}")
            chunks = await self.text_extractor.process_file(
                file_path=str(file_path),
                file_name=file_path.name,
                doc_id=document_id,
                metadata=metadata
            )

            if not chunks:
                return {
                    "success": False,
                    "error": "No chunks extracted from file",
                    "file_name": file_path.name
                }

            total_chunks = len(chunks)
            logger.info(f"Extracted {total_chunks} chunks from {file_path.name}")

            if self.progress_publisher:
                await self.progress_publisher.publish_progress(
                    task_id=task_id,
                    bot_id=bot_id,
                    progress=20,
                    status="processing",
                    message=f"Generating embeddings for {total_chunks} chunks",
                    force=True
                )

            logger.info(f"Generating embeddings for {total_chunks} chunks")
            texts = [chunk.page_content for chunk in chunks]
            embeddings_result = await asyncio.to_thread(
                embedding_service.encode_documents,
                texts
            )
            embeddings = embeddings_result["dense_vectors"].tolist()

            if self.progress_publisher:
                await self.progress_publisher.publish_progress(
                    task_id=task_id,
                    bot_id=bot_id,
                    progress=40,
                    status="processing",
                    message=f"Inserting {total_chunks} chunks to database",
                    force=True
                )
            
            documents = []
            for i, chunk in enumerate(chunks):
                documents.append({
                    "text": chunk.page_content,
                    "document_id": document_id,
                    "web_url": "",
                    "chunk_index": i,
                    "metadata": {
                        "file_name": file_path.name,
                        **(metadata or {}),
                        **(chunk.metadata or {})
                    }
                })
            

            collection_name = f"bot_{bot_id}".replace("-", "_")
            inserted_count = 0
            total_batches = (len(documents) + self.milvus_batch_size - 1) // self.milvus_batch_size
            
            for batch_index, batch_start in enumerate(range(0, len(documents), self.milvus_batch_size)):
                batch_end = min(batch_start + self.milvus_batch_size, len(documents))
                doc_batch = documents[batch_start:batch_end]
                emb_batch = embeddings[batch_start:batch_end]
                
                await self.milvus_service.insert_documents(
                    collection_name=collection_name,
                    documents=doc_batch,
                    embeddings=emb_batch
                )
                
                inserted_count += len(doc_batch)
                
                await batch_import_service.notify_batch_completion(
                    task_id=task_id,
                    bot_id=bot_id,
                    document_id=document_id,
                    batch_index=batch_index,
                    total_batches=total_batches,
                    chunks_in_batch=len(doc_batch),
                    batch_data=doc_batch,
                    source_type="file",
                    file_path=str(file_path)
                )
                
                progress = 40 + (inserted_count / total_chunks) * 55
                if self.progress_publisher:
                    await self.progress_publisher.publish_progress(
                        task_id=task_id,
                        bot_id=bot_id,
                        progress=progress,
                        status="processing",
                        message=f"Inserted {inserted_count}/{total_chunks} chunks (batch {batch_index + 1}/{total_batches})"
                    )
            
            try:
                bucket_name = f"bot-{bot_id}"
                object_name = f"documents/{document_id}/{file_path.name}"

                with open(file_path, 'rb') as f:
                    file_data = f.read()

                await asyncio.to_thread(
                    self.minio_service.upload_file,
                    bucket_name,
                    object_name,
                    file_data
                )
                logger.info(f"Uploaded {file_path.name} to MinIO: {bucket_name}/{object_name}")
            except Exception as e:
                logger.warning(f"Failed to upload file to MinIO: {e}")
            
            processing_time = (now() - start_time).total_seconds()
            
            result = {
                "success": True,
                "file_name": file_path.name,
                "document_id": document_id,
                "chunks_count": total_chunks,
                "inserted_count": inserted_count,
                "processing_time": processing_time
            }
            
            try:
                file_path.unlink()
                logger.info(f"Cleaned up temporary file: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to delete temporary file {file_path}: {e}")
            
            return result
        
        except Exception as e:
            logger.error(f"Failed to process file {file_path.name}: {e}", exc_info=True)
            
            try:
                if file_path.exists():
                    file_path.unlink()
                    logger.info(f"Cleaned up temporary file after error: {file_path}")
            except Exception as cleanup_error:
                logger.warning(f"Failed to delete temporary file {file_path}: {cleanup_error}")
            
            return {
                "success": False,
                "error": str(e),
                "file_name": file_path.name
            }
    
    async def process_files_batch(
        self,
        files: List[Dict[str, Any]],
        bot_id: str,
        task_id: str
    ) -> Dict[str, Any]:
        """
        Process multiple files in a batch
        
        Args:
            files: List of file info dicts with 'path', 'document_id', 'metadata'
            bot_id: Bot ID
            task_id: Task ID
            
        Returns:
            Batch processing results
        """
        results = []
        total_files = len(files)
        
        if self.progress_publisher:
            await self.progress_publisher.publish_start(
                task_id=task_id,
                bot_id=bot_id,
                task_type=TaskType.FILE_UPLOAD.value,
                total_items=total_files
            )
        
        for i, file_info in enumerate(files):
            file_path = Path(file_info["path"])
            document_id = file_info.get("document_id", f"doc_{task_id}_{i}")
            metadata = file_info.get("metadata", {})
            
            result = await self.process_file(
                file_path=file_path,
                bot_id=bot_id,
                task_id=task_id,
                document_id=document_id,
                metadata=metadata
            )
            
            results.append(result)
            
            progress = ((i + 1) / total_files) * 100
            if self.progress_publisher:
                await self.progress_publisher.publish_progress(
                    task_id=task_id,
                    bot_id=bot_id,
                    progress=progress,
                    status="processing",
                    message=f"Processed {i + 1}/{total_files} files"
                )
        
        successful_files = sum(1 for r in results if r.get("success", False))
        failed_files = total_files - successful_files
        total_chunks = sum(r.get("chunks_count", 0) for r in results)
        
        if self.progress_publisher:
            await self.progress_publisher.publish_completion(
                task_id=task_id,
                bot_id=bot_id,
                success=(failed_files == 0),
                message=f"Processed {successful_files}/{total_files} files",
                metadata={
                    "total_files": total_files,
                    "successful_files": successful_files,
                    "failed_files": failed_files,
                    "total_chunks": total_chunks,
                    "results": results
                }
            )
        
        return {
            "task_id": task_id,
            "bot_id": bot_id,
            "total_files": total_files,
            "successful_files": successful_files,
            "failed_files": failed_files,
            "total_chunks": total_chunks,
            "results": results
        }
