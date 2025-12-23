"""Lead scoring service - scores visitors using RAG + LLM with progress tracking."""
import uuid
from typing import List, Dict
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm_client import llm_service
from app.core.prompt_loader import prompt_loader
from app.schemas.grading import GradingTaskPayload, ScoringResult
from app.common.enums import LeadCategory
from app.config.settings import settings
from app.services.provider import provider_service
from app.services.progress_publisher import ProgressPublisher
from app.services.milvus import milvus_service
from app.services.embedding import embedding_service
from app.services.rerank import rerank_service
from app.services.visitor_data import get_visitor_data
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ScoringService:
    """
    Lead scoring service with RAG + LLM evaluation.
    
    Flow:
    1. Receive task (10%)
    2. Create Milvus collection with conversation history (20%)
    3. Retrieve relevant context for each question (40%)
    4. Rerank results (60%)
    5. Delete collection
    6. Aggregate context (70%)
    7. LLM evaluation (90%)
    8. Send webhook / email (100%)
    """
    
    def __init__(self):
        self.system_prompt = prompt_loader.load_prompt("lead_scoring")
    
    async def score_visitor(
        self,
        task: GradingTaskPayload,
        db: AsyncSession
    ) -> ScoringResult:
        """
        Score a visitor using RAG + LLM pipeline.
        
        Args:
            task: Grading task with visitor/session IDs
            db: Database session
            
        Returns:
            ScoringResult with score, category, and insights
        """
        progress = ProgressPublisher(task.task_id)
        
        try:
            await progress.start()
            await progress.publish(5, "PROCESSING", "Task received, querying visitor data")
            
            visitor_data = await get_visitor_data(
                task.visitor_id,
                task.bot_id,
                task.session_id,
                db
            )
            conversation_history = visitor_data["conversation_history"]
            visitor_profile = visitor_data["visitor_profile"]
            bot_config = visitor_data["bot_config"]
            
            if not conversation_history or len(conversation_history) == 0:
                error_msg = "Cannot score visitor with no chat messages"
                logger.warning(error_msg, extra={"visitor_id": task.visitor_id})
                await progress.fail(error_msg)
                raise ValueError(error_msg)
            
            await progress.publish(10, "PROCESSING", "Visitor data retrieved, preparing scoring")
            
            logger.info(
                "Starting visitor scoring",
                extra={
                    "task_id": task.task_id,
                    "visitor_id": task.visitor_id,
                    "bot_id": task.bot_id,
                    "message_count": len(conversation_history),
                    "key_index": bot_config.get("key_index")
                }
            )
            
            await progress.publish(12, "PROCESSING", "Cleaning up old collections")
            collection_name = self._get_collection_name(task.session_id, task_type="grading")
            
            try:
                await self._delete_milvus_collection(collection_name)
                logger.debug(f"Deleted old collection: {collection_name}")
            except Exception:
                pass
            
            await progress.publish(15, "PROCESSING", "Creating temporary vector collection")
            await self._create_milvus_collection(collection_name, conversation_history)
            await progress.publish(20, "PROCESSING", f"Created collection: {collection_name}")
            
            await progress.publish(25, "PROCESSING", "Retrieving relevant conversation context")
            retrieval_results = await self._retrieve_for_questions(
                collection_name,
                self.questions,
                progress
            )
            await progress.publish(40, "PROCESSING", "Context retrieval completed")
            
            await progress.publish(45, "PROCESSING", "Reranking results for relevance")
            reranked_results = await self._rerank_results(retrieval_results, progress)
            await progress.publish(60, "PROCESSING", "Reranking completed")
            
            await self._delete_milvus_collection(collection_name)
            
            await progress.publish(65, "PROCESSING", "Aggregating context for evaluation")
            aggregated_context = self._aggregate_context(reranked_results)
            await progress.publish(70, "PROCESSING", "Context aggregation completed")
            
            await progress.publish(75, "PROCESSING", "Sending to LLM for evaluation")
            result_json = await llm_service.score_visitor(
                bot_config=bot_config,
                conversation_history=conversation_history,
                visitor_profile=visitor_profile,
                system_prompt=self.system_prompt,
                rag_context=aggregated_context
            )
            await progress.publish(90, "PROCESSING", "LLM evaluation completed")
            
            score = result_json.get("score", 0)
            category = self._determine_category(score)
            
            result = ScoringResult(
                score=score,
                category=category,
                intent_signals=result_json.get("intent_signals", []),
                engagement_level=result_json.get("engagement_level", "low"),
                key_interests=result_json.get("key_interests", []),
                recommended_actions=result_json.get("recommended_actions", []),
                reasoning=result_json.get("reasoning", ""),
                model_used=bot_config.get("model", "unknown")
            )
            
            logger.info(
                "Visitor scored successfully",
                extra={
                    "task_id": task.task_id,
                    "visitor_id": task.visitor_id,
                    "score": result.score,
                    "category": result.category.value
                }
            )
            
            await progress.complete("Visitor grading completed successfully")
            
            return result
            
        except Exception as e:
            logger.error(
                "Scoring failed",
                extra={
                    "task_id": task.task_id,
                    "visitor_id": task.visitor_id,
                    "error": str(e)
                },
                exc_info=True
            )
            await progress.fail(str(e))
            raise
    
    async def assess_visitor(
        self,
        task: GradingTaskPayload,
        db: AsyncSession
    ) -> Dict:
        """
        Assess visitor using custom assessment questions.
        Similar to score_visitor but uses bot's assessment_questions.
        
        Returns dict with: results (list), summary (str), model_used (str), total_messages (int)
        """
        progress = ProgressPublisher(task.task_id, task_type="assessment")
        
        try:
            await progress.publish(5, "PROCESSING", "Starting visitor assessment")
            
            visitor_data = await get_visitor_data(
                task.visitor_id,
                task.bot_id,
                task.session_id,
                db
            )
            
            conversation_history = visitor_data["conversation_history"]
            visitor_profile = visitor_data["visitor_profile"]
            bot_config = visitor_data["bot_config"]
            
            if not conversation_history or len(conversation_history) == 0:
                error_msg = "Cannot assess visitor with no chat messages"
                logger.warning(error_msg, extra={"visitor_id": task.visitor_id})
                await progress.fail(error_msg)
                raise ValueError(error_msg)
            
            if not task.assessment_questions or len(task.assessment_questions) == 0:
                raise ValueError("No assessment questions provided")
            
            all_questions = [
                "Chat history summary (tóm tắt lịch sử chat của khách hàng này)"
            ] + list(task.assessment_questions)
            
            await progress.publish(10, "PROCESSING", "Cleaning up old collections")
            collection_name = self._get_collection_name(task.session_id, task_type="assessment")
            
            try:
                await self._delete_milvus_collection(collection_name)
            except Exception:
                pass 
            
            await progress.publish(15, "PROCESSING", "Creating temporary collection")
            await self._create_milvus_collection(collection_name, conversation_history)
            await progress.publish(25, "PROCESSING", "Retrieving relevant context")
            
            retrieval_results = await self._retrieve_for_questions(
                collection_name,
                all_questions, 
                progress
            )
            await progress.publish(40, "PROCESSING", "Reranking results")
            
            reranked_results = await self._rerank_results(retrieval_results, progress)
            await progress.publish(60, "PROCESSING", "Reranking completed")
            
            await self._delete_milvus_collection(collection_name)
            
            await progress.publish(65, "PROCESSING", "Aggregating context")
            aggregated_context = self._aggregate_context(reranked_results)
            await progress.publish(70, "PROCESSING", "Analyzing with LLM")
            
            result_json = await llm_service.assess_visitor(
                bot_config=bot_config,
                conversation_history=conversation_history,
                visitor_profile=visitor_profile,
                assessment_questions=task.assessment_questions,  
                rag_context=aggregated_context
            )
            
            logger.info(
                f"LLM assessment result received - task_id={task.task_id}, "
                f"keys={list(result_json.keys())}, has_results={('results' in result_json)}, "
                f"num_results={len(result_json.get('results', []))}, "
                f"has_summary={('summary' in result_json)}, "
                f"raw_result={str(result_json)[:500]}"
            )
            
            await progress.publish(90, "PROCESSING", "Assessment completed")
            
            results = {
                "results": result_json.get("results", []),
                "summary": result_json.get("summary", ""),
                "lead_score": result_json.get("lead_score", 0),
                "model_used": bot_config.get("model", "unknown"),
                "total_messages": len(conversation_history)
            }
            
            logger.info(
                f"Visitor assessed successfully - task_id={task.task_id}, "
                f"visitor_id={task.visitor_id}, num_questions={len(task.assessment_questions)}, "
                f"total_messages={len(conversation_history)}, "
                f"num_results_returned={len(results['results'])}"
            )
            
            await progress.complete("Visitor assessment completed successfully")
            
            return results
            
        except Exception as e:
            logger.error(
                "Assessment failed",
                extra={
                    "task_id": task.task_id,
                    "visitor_id": task.visitor_id,
                    "error": str(e)
                },
                exc_info=True
            )
            await progress.fail(str(e))
            raise
    
    def _get_collection_name(self, session_id: str, task_type: str = "grading") -> str:
        """
        Generate collection name from session ID and task type.
        
        Args:
            session_id: Chat session UUID
            task_type: Type of task (grading or assessment)
            
        Returns:
            Collection name with task_type prefix
        """
        return f"{task_type}_{session_id.replace('-', '_')}"
    
    async def _create_milvus_collection(
        self,
        collection_name: str,
        conversation_history: List[Dict]
    ) -> None:
        """
        Create temporary Milvus collection with conversation embeddings.
        
        Steps:
        0. Delete old collection if exists (cleanup from previous failed attempts)
        1. Connect to Milvus
        2. Create collection with schema
        3. Embed all messages
        4. Insert to Milvus
        """
        try:
            await self._delete_milvus_collection(collection_name)
        except Exception as e:
            logger.debug(f"No old collection to delete (expected): {e}")
        
        logger.info(f"Creating Milvus collection: {collection_name}")
        
        messages = []
        texts = []
        
        for idx, msg in enumerate(conversation_history):
            message_data = {
                "id": f"msg_{idx}",
                "role": msg.get("role", "user"),
                "content": msg.get("content", ""),
                "timestamp": msg.get("timestamp", "")
            }
            messages.append(message_data)
            texts.append(message_data["content"])
        
        if not texts:
            logger.warning("No messages to embed - cannot create collection")
            raise ValueError("Session has no messages to analyze")
        
        milvus_service.connect()
        milvus_service.create_collection(collection_name)
        
        embedding_result = embedding_service.embed_batch(texts)
        dense_embeddings = embedding_result["dense_vecs"]
        
        milvus_service.insert_messages(collection_name, messages, dense_embeddings)
        
        logger.info(
            f"Inserted {len(messages)} messages into {collection_name}",
            extra={"collection": collection_name, "message_count": len(messages)}
        )
    
    async def _retrieve_for_questions(
        self,
        collection_name: str,
        questions: List[str],
        progress: ProgressPublisher
    ) -> Dict[str, List[Dict]]:
        """
        Retrieve relevant conversation snippets for each question.
        
        For each evaluation question, search Milvus to find the most relevant
        conversation messages.
        """
        results = {}
        total = len(questions)
        
        for idx, question in enumerate(questions):
            embedding_result = embedding_service.embed(question)
            query_dense = embedding_result["dense_vecs"]
            
            search_results = milvus_service.search(
                collection_name=collection_name,
                query_dense=query_dense,
                top_k=settings.RETRIEVAL_TOP_K,
                output_fields=["message_id", "role", "content", "timestamp"]
            )
            
            results[question] = search_results
            
            progress_pct = 25 + (15 * (idx + 1) / total)
            await progress.publish(
                progress_pct,
                "PROCESSING",
                f"Retrieving context for question {idx + 1}/{total}"
            )
            
            logger.debug(
                f"Retrieved {len(search_results)} results for question",
                extra={
                    "question_idx": idx,
                    "question": question[:50],
                    "result_count": len(search_results)
                }
            )
        
        return results
    
    async def _rerank_results(
        self,
        retrieval_results: Dict[str, List[Dict]],
        progress: ProgressPublisher
    ) -> Dict[str, List[Dict]]:
        """
        Rerank retrieved results using cross-encoder.
        
        For each question's retrieval results, use reranker to get the most
        relevant conversations based on semantic similarity.
        """
        logger.info("Reranking retrieval results")
        reranked_results = {}
        total = len(retrieval_results)
        
        for idx, (question, results) in enumerate(retrieval_results.items()):
            if not results:
                reranked_results[question] = []
                continue
            
            reranked = rerank_service.rerank_results(
                query=question,
                retrieval_results=results,
                top_k=settings.RERANK_TOP_K,
                content_field="content"
            )
            
            reranked_results[question] = reranked
            progress_pct = 45 + (15 * (idx + 1) / total)
            await progress.publish(
                progress_pct,
                "PROCESSING",
                f"Reranking results for question {idx + 1}/{total}"
            )
            
            logger.debug(
                f"Reranked {len(results)} -> {len(reranked)} for question",
                extra={
                    "question": question[:50],
                    "original_count": len(results),
                    "reranked_count": len(reranked)
                }
            )
        
        return reranked_results
    
    async def _delete_milvus_collection(self, collection_name: str) -> None:
        """Delete temporary Milvus collection."""
        logger.info(f"Deleting Milvus collection: {collection_name}")
        milvus_service.delete_collection(collection_name)
    
    def _aggregate_context(self, reranked_results: Dict[str, List[Dict]]) -> str:
        """
        Aggregate reranked results into context string for LLM.
        
        Format:
        ## Question 1
        - Relevant message 1
        - Relevant message 2
        ...
        
        ## Question 2
        ...
        """
        context_parts = []
        
        for question, results in reranked_results.items():
            context_parts.append(f"## {question}")
            context_parts.append("")
            
            if results:
                for idx, result in enumerate(results, 1):
                    role = result.get("role", "unknown")
                    content = result.get("content", "")
                    rerank_score = result.get("rerank_score", 0)
                    
                    context_parts.append(
                        f"{idx}. [{role.upper()}] {content} (relevance: {rerank_score:.3f})"
                    )
            else:
                context_parts.append("- (Không tìm thấy thông tin liên quan trong lịch sử chat)")
            
            context_parts.append("")
        
        aggregated = "\n".join(context_parts)
        
        logger.info(
            f"Aggregated context for {len(reranked_results)} questions",
            extra={"context_length": len(aggregated)}
        )
        
        return aggregated
    
    def _determine_category(self, score: int) -> LeadCategory:
        """Determine category based on score thresholds."""
        if score >= settings.HOT_LEAD_THRESHOLD:
            return LeadCategory.HOT
        elif score >= settings.WARM_LEAD_THRESHOLD:
            return LeadCategory.WARM
        else:
            return LeadCategory.COLD


# Global instance
scoring_service = ScoringService()

