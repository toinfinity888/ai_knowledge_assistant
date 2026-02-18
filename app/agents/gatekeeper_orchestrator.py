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
from app.services.pii_detector import get_pii_detector

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
        validate_only: bool = False,
        edited_fields_query: str = "",
    ) -> Dict[str, Any]:
        """
        Main entry point — called when agent clicks "Analyze Context" or "Search".

        Args:
            session_id: Active call session ID
            company_id: Company ID for schema lookup and KB filtering
            language: Language code for responses
            force_search: If True, skip validation and search anyway
            validate_only: If True, only validate without searching (even if ready)
            edited_fields_query: Manually edited/corrected field values for search

        Returns:
            Dict with validation result and any suggestions
        """
        start_time = time.time()

        logger.info(f"[Gatekeeper] analyze_and_search called: session_id={session_id}, company_id={company_id}, language={language}, force_search={force_search}")

        result = {
            "session_id": session_id,
            "status": "",
            "validation": {},
            "suggestions": [],
            "pii_flags": [],
            "processing_time_ms": 0,
        }

        # Get conversation context
        conversation_text = self.session_manager.get_conversation_context(
            session_id, last_n_segments=20
        )

        logger.info(f"[Gatekeeper] Conversation context length: {len(conversation_text)} chars")
        logger.debug(f"[Gatekeeper] Conversation text: {conversation_text[:500]}...")

        # Detect PII in conversation
        pii_detector = get_pii_detector()
        pii_flags = pii_detector.detect(conversation_text)
        result["pii_flags"] = pii_flags
        if pii_flags:
            logger.info(f"[Gatekeeper] PII detected: {pii_flags}")

        if not conversation_text.strip():
            result["status"] = "error"
            result["validation"] = {
                "error_message": "No conversation data available yet.",
            }
            result["processing_time_ms"] = int((time.time() - start_time) * 1000)
            return result

        # Prepare consolidated log data
        log_input = {
            "company_id": company_id,
            "conversation_text": conversation_text[:1000],  # First 1000 chars for context
            "conversation_length": len(conversation_text),
            "language": language,
            "force_search": force_search,
            "validate_only": validate_only,
        }
        log_output = {
            "pii_flags": pii_flags,
        }

        # Stage 1: Validate conversation
        if not force_search:
            validation = self.validator.validate(
                conversation_text=conversation_text,
                company_id=company_id,
                language=language,
            )

            result["validation"] = validation.to_dict()
            result["status"] = validation.status

            logger.info(f"[Gatekeeper] Validation result: status={validation.status}, domain={validation.domain}, domain_name={validation.domain_name}, confidence={validation.domain_confidence}")
            if validation.error_message:
                logger.warning(f"[Gatekeeper] Validation error message: {validation.error_message}")

            # Add validation to log output
            log_output["validation"] = validation.to_dict()

            # If required fields are missing and not forcing, stop here
            if validation.status != "ready":
                result["processing_time_ms"] = int((time.time() - start_time) * 1000)
                # Log the complete analysis
                self._log_action(
                    session_id=session_id,
                    agent_name="gatekeeper",
                    action_type="analyze_context",
                    input_data=log_input,
                    output_data=log_output,
                    status=validation.status,
                    confidence=validation.domain_confidence,
                    start_time=start_time,
                )
                return result

            # If validate_only, return without searching (user will click search button)
            if validate_only:
                logger.info(f"[Gatekeeper] Validate only mode - returning without RAG search")
                result["processing_time_ms"] = int((time.time() - start_time) * 1000)
                # Log the complete analysis
                self._log_action(
                    session_id=session_id,
                    agent_name="gatekeeper",
                    action_type="analyze_context",
                    input_data=log_input,
                    output_data=log_output,
                    status=validation.status,
                    confidence=validation.domain_confidence,
                    start_time=start_time,
                )
                return result

            search_query = validation.optimized_query
        else:
            # Force search: skip validation, use raw conversation as query
            result["status"] = "forced"
            result["validation"] = {"status": "forced", "reasoning": "Search forced by agent"}
            search_query = conversation_text[:500]  # Use first 500 chars as query
            log_output["validation"] = {"status": "forced", "reasoning": "Search forced by agent"}

        # Enhance search query with manually edited fields if provided
        if edited_fields_query:
            search_query = f"{edited_fields_query} {search_query}" if search_query else edited_fields_query
            logger.info(f"[Gatekeeper] Enhanced search query with edited fields: {search_query[:200]}")

        # Stage 2: RAG search
        suggestions = []
        if search_query:
            log_output["search_query"] = search_query
            log_output["edited_fields_query"] = edited_fields_query
            suggestions = self._execute_rag_search(
                session_id=session_id,
                query=search_query,
                language=language,
                company_id=company_id,
                domain=result["validation"].get("domain", ""),
            )
            result["suggestions"] = suggestions
            if not force_search:
                result["status"] = "ready"

            # Add suggestions to log output (with content preview)
            log_output["suggestions"] = [
                {
                    "id": s.get("id"),
                    "title": s.get("title"),
                    "content_preview": s.get("content", "")[:500],  # First 500 chars
                    "confidence": s.get("confidence"),
                    "source_metadata": s.get("source_metadata", []),
                }
                for s in suggestions
            ]

        result["processing_time_ms"] = int((time.time() - start_time) * 1000)

        # Log the complete analysis (single consolidated log entry)
        self._log_action(
            session_id=session_id,
            agent_name="gatekeeper",
            action_type="analyze_and_search" if suggestions else "analyze_context",
            input_data=log_input,
            output_data=log_output,
            status=result["status"],
            confidence=result["validation"].get("domain_confidence", 0.0),
            start_time=start_time,
        )

        return result

    def _execute_rag_search(
        self,
        session_id: str,
        query: str,
        language: str,
        company_id: int,
        domain: str,
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
                source_metadata = rag_result.get("source_metadata", [])

                suggestion = self.session_manager.add_suggestion(
                    session_id=session_id,
                    suggestion_type="knowledge_base",
                    title=f"Solution: {domain}" if domain else "Knowledge Base Result",
                    content=rag_result["answer"],
                    source_chunks=rag_result.get("context_chunks", []),
                    source_metadata=source_metadata,
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
                    "source_metadata": source_metadata,
                })

        except Exception as e:
            logger.error(f"RAG search failed: {e}")

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
