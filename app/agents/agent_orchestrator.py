"""
Agent Orchestrator
Coordinates all agents to process incoming transcription and generate suggestions
"""
import time
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.agents.base_agent import AgentStatus
from app.agents.context_analyzer_agent import ContextAnalyzerAgent
from app.agents.query_formulation_agent import QueryFormulationAgent
from app.agents.clarification_agent import ClarificationAgent
from app.core.rag_engine import RAGEngine
from app.services.call_session_manager import CallSessionManager
from app.llm.base_llm import BaseLLM


class AgentOrchestrator:
    """
    Orchestrates the agent pipeline:
    1. Analyze conversation context
    2. Formulate queries OR generate clarifying questions
    3. Query RAG system
    4. Generate suggestions for support agent
    """

    def __init__(
        self,
        context_agent: ContextAnalyzerAgent,
        query_agent: QueryFormulationAgent,
        clarification_agent: ClarificationAgent,
        rag_engine: RAGEngine,
        session_manager: CallSessionManager,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.context_agent = context_agent
        self.query_agent = query_agent
        self.clarification_agent = clarification_agent
        self.rag_engine = rag_engine
        self.session_manager = session_manager
        self.config = config or {}

        # Configuration
        self.min_context_confidence = config.get("min_context_confidence", 0.6)
        self.min_query_results = config.get("min_query_results", 1)
        self.max_suggestions = config.get("max_suggestions", 5)

    async def process_transcription_update(
        self,
        session_id: str,
        new_transcription: str,
        speaker: str,
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Main entry point: Process new transcription segment and generate suggestions

        Args:
            session_id: Call session identifier
            new_transcription: New transcribed text
            speaker: Who spoke ('customer' or 'agent')
            language: Language code (e.g., 'en', 'fr', 'es') for response generation

        Returns:
            Dict with suggestions, questions, and processing metadata
        """
        start_time = time.time()

        # Get conversation context
        conversation_context = self.session_manager.get_conversation_context(
            session_id, last_n_segments=10
        )

        # Build context for agents
        agent_context = {
            "conversation_text": conversation_context,
            "customer_last_message": new_transcription if speaker == "customer" else "",
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "language": language or "en",  # Default to English if not specified
        }

        result = {
            "session_id": session_id,
            "suggestions": [],
            "clarifying_questions": [],
            "processing_steps": [],
            "total_time_ms": 0,
        }

        try:
            # STEP 1: Analyze context
            context_analysis = await self._step_analyze_context(session_id, agent_context)
            result["processing_steps"].append(context_analysis)

            # Extract analysis results
            has_sufficient_context = context_analysis["result"].get("has_sufficient_context", False)
            detected_issue = context_analysis["result"].get("detected_issue", "")
            detected_entities = context_analysis["result"].get("detected_entities", [])
            needs_clarification = context_analysis["result"].get("needs_clarification", False)
            clarification_needed_for = context_analysis["result"].get("clarification_needed_for", [])

            # Update session metadata
            self.session_manager.update_session_metadata(
                session_id,
                detected_intent=detected_issue,
                detected_entities=[e["value"] for e in detected_entities],
            )

            # STEP 2: Decide next action based on context analysis
            if has_sufficient_context and not needs_clarification:
                # We have enough context -> formulate queries and search
                suggestions = await self._step_generate_suggestions(
                    session_id,
                    agent_context,
                    detected_issue,
                    detected_entities,
                )
                result["suggestions"] = suggestions["suggestions"]
                result["processing_steps"].append(suggestions["step_info"])

            elif needs_clarification or not has_sufficient_context:
                # Need clarification -> generate clarifying questions
                clarifications = await self._step_generate_clarifications(
                    session_id,
                    agent_context,
                    detected_issue,
                    detected_entities,
                    clarification_needed_for,
                )
                result["clarifying_questions"] = clarifications["questions"]
                result["processing_steps"].append(clarifications["step_info"])

                # Also try to generate suggestions anyway (might find something)
                try:
                    suggestions = await self._step_generate_suggestions(
                        session_id,
                        agent_context,
                        detected_issue,
                        detected_entities,
                    )
                    # Merge knowledge base suggestions with clarifying questions
                    result["suggestions"].extend(suggestions["suggestions"])
                    result["processing_steps"].append(suggestions["step_info"])
                except Exception as e:
                    # If suggestions fail, log it but continue with clarifications
                    import logging
                    logging.error(f"Failed to generate suggestions alongside clarifications: {e}")

        except Exception as e:
            result["error"] = str(e)
            result["processing_steps"].append({
                "step": "error",
                "error": str(e),
            })

        # Calculate total time
        result["total_time_ms"] = int((time.time() - start_time) * 1000)

        return result

    async def _step_analyze_context(
        self,
        session_id: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Step 1: Analyze conversation context"""
        step_start = time.time()

        # Run context analyzer
        response = await self.context_agent.process(context)

        # Log to database
        self.session_manager.log_agent_action(
            session_id=session_id,
            agent_name="context_analyzer",
            action_type="analyze_context",
            input_data=context,
            output_data=response.to_dict(),
            status=response.status.value,
            confidence=response.confidence,
            message=response.message,
            processing_time_ms=int((time.time() - step_start) * 1000),
        )

        return {
            "step": "context_analysis",
            "status": response.status.value,
            "result": response.data,
            "confidence": response.confidence,
            "time_ms": int((time.time() - step_start) * 1000),
        }

    async def _step_generate_suggestions(
        self,
        session_id: str,
        context: Dict[str, Any],
        detected_issue: str,
        detected_entities: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Step 2a: Generate knowledge base suggestions"""
        step_start = time.time()

        suggestions = []

        # Formulate queries
        query_context = {
            **context,
            "detected_issue": detected_issue,
            "detected_entities": detected_entities,
            "previous_queries": [],  # TODO: Track previous queries
        }

        query_response = await self.query_agent.process(query_context)

        # Log query formulation
        self.session_manager.log_agent_action(
            session_id=session_id,
            agent_name="query_formulation",
            action_type="formulate_queries",
            input_data=query_context,
            output_data=query_response.to_dict(),
            status=query_response.status.value,
            confidence=query_response.confidence,
            processing_time_ms=int((time.time() - step_start) * 1000),
        )

        # Execute queries against RAG system
        if query_response.status == AgentStatus.SUCCESS:
            queries = query_response.data.get("queries", [])

            for query_info in queries[:3]:  # Limit to top 3 queries
                query_text = query_info["text"]

                # Query RAG with language parameter
                try:
                    language = context.get("language", "en")
                    rag_result = self.rag_engine.ask(query_text, language=language)

                    # Create suggestion from RAG result
                    if rag_result.get("answer"):
                        suggestion = self.session_manager.add_suggestion(
                            session_id=session_id,
                            suggestion_type="knowledge_base",
                            title=f"Solution: {detected_issue or 'Customer Issue'}",
                            content=rag_result["answer"],
                            source_chunks=rag_result.get("context_chunks", []),
                            query_used=query_text,
                            confidence_score=query_info.get("confidence", 0.7),
                            relevance_score=0.8,  # TODO: Calculate actual relevance
                        )

                        suggestions.append({
                            "id": suggestion.id,
                            "type": "knowledge_base",
                            "title": suggestion.title,
                            "content": suggestion.content,
                            "confidence": suggestion.confidence_score,
                            "query_used": query_text,
                        })

                except Exception as e:
                    # Log RAG error but continue
                    self.session_manager.log_agent_action(
                        session_id=session_id,
                        agent_name="rag_engine",
                        action_type="query_knowledge_base",
                        input_data={"query": query_text},
                        output_data={"error": str(e)},
                        status="error",
                        confidence=0.0,
                    )

        return {
            "suggestions": suggestions[:self.max_suggestions],
            "step_info": {
                "step": "generate_suggestions",
                "queries_generated": len(query_response.data.get("queries", [])),
                "suggestions_created": len(suggestions),
                "time_ms": int((time.time() - step_start) * 1000),
            },
        }

    async def _step_generate_clarifications(
        self,
        session_id: str,
        context: Dict[str, Any],
        detected_issue: str,
        detected_entities: List[Dict[str, Any]],
        clarification_needed_for: List[str],
    ) -> Dict[str, Any]:
        """Step 2b: Generate clarifying questions"""
        step_start = time.time()

        clarification_context = {
            **context,
            "detected_issue": detected_issue,
            "detected_entities": detected_entities,
            "clarification_needed_for": clarification_needed_for,
        }

        response = await self.clarification_agent.process(clarification_context)

        # Log clarification generation
        self.session_manager.log_agent_action(
            session_id=session_id,
            agent_name="clarification",
            action_type="generate_questions",
            input_data=clarification_context,
            output_data=response.to_dict(),
            status=response.status.value,
            confidence=response.confidence,
            processing_time_ms=int((time.time() - step_start) * 1000),
        )

        questions = []
        if response.status == AgentStatus.SUCCESS:
            questions_data = response.data.get("questions", [])

            # Store clarifying questions as suggestions
            for q in questions_data:
                suggestion = self.session_manager.add_suggestion(
                    session_id=session_id,
                    suggestion_type="clarification_question",
                    title="Suggested Question",
                    content=q["text"],
                    query_used=None,
                    confidence_score=response.confidence,
                    relevance_score=0.9 if q.get("priority", 2) == 1 else 0.7,
                )

                questions.append({
                    "id": suggestion.id,
                    "text": q["text"],
                    "purpose": q.get("purpose", ""),
                    "priority": q.get("priority", 2),
                })

        return {
            "questions": questions,
            "step_info": {
                "step": "generate_clarifications",
                "questions_generated": len(questions),
                "display_to_agent": response.data.get("display_to_agent", True),
                "time_ms": int((time.time() - step_start) * 1000),
            },
        }

    def get_pipeline_stats(self) -> Dict[str, Any]:
        """Get statistics about agent pipeline performance"""
        return {
            "context_agent_history_size": len(self.context_agent.get_history()),
            "query_agent_history_size": len(self.query_agent.get_history()),
            "clarification_agent_history_size": len(self.clarification_agent.get_history()),
            "config": self.config,
        }


def create_agent_orchestrator(
    llm: BaseLLM,
    rag_engine: RAGEngine,
    session_manager: CallSessionManager,
    config: Optional[Dict[str, Any]] = None,
) -> AgentOrchestrator:
    """
    Factory function to create a fully configured AgentOrchestrator

    Args:
        llm: Language model for agents
        rag_engine: RAG engine for knowledge base queries
        session_manager: Call session manager
        config: Optional configuration

    Returns:
        Configured AgentOrchestrator instance
    """
    # Create agents
    context_agent = ContextAnalyzerAgent(llm=llm, config=config)
    query_agent = QueryFormulationAgent(llm=llm, config=config)
    clarification_agent = ClarificationAgent(llm=llm, config=config)

    # Create orchestrator
    orchestrator = AgentOrchestrator(
        context_agent=context_agent,
        query_agent=query_agent,
        clarification_agent=clarification_agent,
        rag_engine=rag_engine,
        session_manager=session_manager,
        config=config,
    )

    return orchestrator
