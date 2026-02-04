"""
Gatekeeper Orchestrator

Two-stage coordinator that replaces the multi-agent pipeline:
  Stage 1: ValidatorService (Groq Llama 8B) — domain classification + field validation
  Stage 2: RAGEngine — knowledge base search (only if Stage 1 passes)
"""
import time
import logging
from typing import Dict, Any, Optional

from app.services.validator_service import ValidatorService
from app.core.rag_engine import RAGEngine
from app.services.call_session_manager import CallSessionManager

logger = logging.getLogger(__name__)


class GatekeeperOrchestrator:
    """
    Two-stage Intelligence Gatekeeper.

    Called when the support agent clicks "Analyze & Search".
    """

    def __init__(
        self,
        validator_service: ValidatorService,
        rag_engine: RAGEngine,
        session_manager: CallSessionManager,
    ):
        self.validator = validator_service
        self.rag_engine = rag_engine
        self.session_manager = session_manager

    def analyze_and_search(
        self,
        session_id: str,
        company_id: int,
        language: str = "en",
        force_search: bool = False,
    ) -> Dict[str, Any]:
        """
        Main entry point — called when agent clicks "Analyze & Search".

        Args:
            session_id: Active call session ID
            company_id: Company ID for schema lookup and KB filtering
            language: Language code for responses
            force_search: If True, skip validation and search anyway

        Returns:
            Dict with validation result and any suggestions
        """
        start_time = time.time()

        result = {
            "session_id": session_id,
            "status": "",
            "validation": {},
            "suggestions": [],
            "processing_time_ms": 0,
        }

        # Get conversation context
        conversation_text = self.session_manager.get_conversation_context(
            session_id, last_n_segments=20
        )

        if not conversation_text.strip():
            result["status"] = "error"
            result["validation"] = {
                "error_message": "No conversation data available yet.",
            }
            result["processing_time_ms"] = int((time.time() - start_time) * 1000)
            return result

        # Stage 1: Validate conversation
        if not force_search:
            validation = self.validator.validate(
                conversation_text=conversation_text,
                company_id=company_id,
                language=language,
            )

            result["validation"] = validation.to_dict()
            result["status"] = validation.status

            # Log validation step
            self._log_action(
                session_id=session_id,
                agent_name="gatekeeper_validator",
                action_type="validate_conversation",
                input_data={"conversation_length": len(conversation_text), "company_id": company_id},
                output_data=validation.to_dict(),
                status=validation.status,
                confidence=validation.domain_confidence,
                start_time=start_time,
            )

            # If required fields are missing and not forcing, stop here
            if validation.status != "ready":
                result["processing_time_ms"] = int((time.time() - start_time) * 1000)
                return result

            search_query = validation.optimized_query
        else:
            # Force search: skip validation, use raw conversation as query
            result["status"] = "forced"
            result["validation"] = {"status": "forced", "reasoning": "Search forced by agent"}
            search_query = conversation_text[:500]  # Use first 500 chars as query

            self._log_action(
                session_id=session_id,
                agent_name="gatekeeper_validator",
                action_type="force_search",
                input_data={"conversation_length": len(conversation_text)},
                output_data={"query": search_query},
                status="forced",
                confidence=0.0,
                start_time=start_time,
            )

        # Stage 2: RAG search
        if search_query:
            suggestions = self._execute_rag_search(
                session_id=session_id,
                query=search_query,
                language=language,
                company_id=company_id,
                domain=result["validation"].get("domain", ""),
                start_time=start_time,
            )
            result["suggestions"] = suggestions
            if not force_search:
                result["status"] = "ready"

        result["processing_time_ms"] = int((time.time() - start_time) * 1000)
        return result

    def _execute_rag_search(
        self,
        session_id: str,
        query: str,
        language: str,
        company_id: int,
        domain: str,
        start_time: float,
    ) -> list:
        """Execute RAG search and store suggestions."""
        suggestions = []

        try:
            rag_result = self.rag_engine.ask(
                query=query,
                language=language,
                company_id=company_id,
            )

            if rag_result.get("answer"):
                suggestion = self.session_manager.add_suggestion(
                    session_id=session_id,
                    suggestion_type="knowledge_base",
                    title=f"Solution: {domain}" if domain else "Knowledge Base Result",
                    content=rag_result["answer"],
                    source_chunks=rag_result.get("context_chunks", []),
                    query_used=query,
                    confidence_score=0.85,
                    relevance_score=0.8,
                )

                suggestions.append({
                    "id": suggestion.id,
                    "type": "knowledge_base",
                    "title": suggestion.title,
                    "content": suggestion.content,
                    "confidence": suggestion.confidence_score,
                    "query_used": query,
                    "source_chunks": rag_result.get("context_chunks", []),
                })

            # Log RAG step
            self._log_action(
                session_id=session_id,
                agent_name="gatekeeper_rag",
                action_type="knowledge_base_search",
                input_data={"query": query, "company_id": company_id},
                output_data={"suggestions_count": len(suggestions)},
                status="success",
                confidence=0.85 if suggestions else 0.0,
                start_time=start_time,
            )

        except Exception as e:
            logger.error(f"RAG search failed: {e}")
            self._log_action(
                session_id=session_id,
                agent_name="gatekeeper_rag",
                action_type="knowledge_base_search",
                input_data={"query": query},
                output_data={"error": str(e)},
                status="error",
                confidence=0.0,
                start_time=start_time,
            )

        return suggestions

    def _log_action(
        self,
        session_id: str,
        agent_name: str,
        action_type: str,
        input_data: dict,
        output_data: dict,
        status: str,
        confidence: float,
        start_time: float,
    ):
        """Log an agent action to the database."""
        try:
            self.session_manager.log_agent_action(
                session_id=session_id,
                agent_name=agent_name,
                action_type=action_type,
                input_data=input_data,
                output_data=output_data,
                status=status,
                confidence=confidence,
                processing_time_ms=int((time.time() - start_time) * 1000),
            )
        except Exception as e:
            logger.error(f"Failed to log agent action: {e}")
