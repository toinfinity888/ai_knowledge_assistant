"""
Context Analyzer Agent
Analyzes conversation context to determine if there's enough information to query the knowledge base
"""
from typing import Dict, Any, List, Optional
import re
from app.agents.base_agent import BaseAgent, AgentResponse, AgentStatus
from app.llm.base_llm import BaseLLM


class ContextAnalyzerAgent(BaseAgent):
    """
    Analyzes conversation context to determine:
    1. Is there enough information to search the knowledge base?
    2. What is the customer's main issue/question?
    3. What key entities have been mentioned? (products, error codes, features)
    4. Is clarification needed?
    """

    def __init__(self, llm: BaseLLM, config: Optional[Dict[str, Any]] = None):
        super().__init__(name="ContextAnalyzerAgent", config=config)
        self.llm = llm
        self.min_confidence = config.get("min_confidence", 0.6) if config else 0.6

    async def process(self, context: Dict[str, Any]) -> AgentResponse:
        """
        Analyze conversation context

        Expected context:
            - conversation_text: str (recent conversation history)
            - customer_last_message: str (most recent customer utterance)
            - detected_entities: List[str] (optional: previously detected entities)
            - session_metadata: Dict (optional: customer info, call history)

        Returns:
            AgentResponse with:
                - has_sufficient_context: bool
                - detected_issue: str
                - detected_entities: List[Dict] (name, type, value)
                - confidence: float
                - needs_clarification: bool
                - clarification_needed_for: List[str]
        """
        # Validate input
        if not self._validate_context(context, ["conversation_text"]):
            return AgentResponse(
                status=AgentStatus.ERROR,
                data={},
                message="Missing required field: conversation_text",
                confidence=0.0,
            )

        conversation_text = context["conversation_text"]
        customer_last_message = context.get("customer_last_message", "")

        # Quick heuristic check
        heuristic_result = self._heuristic_analysis(conversation_text, customer_last_message)

        # If heuristics are confident, skip LLM call
        if heuristic_result["confidence"] >= 0.8:
            return AgentResponse(
                status=AgentStatus.SUCCESS if heuristic_result["has_sufficient_context"] else AgentStatus.NEED_MORE_INFO,
                data=heuristic_result,
                confidence=heuristic_result["confidence"],
            )

        # Use LLM for deeper analysis
        llm_result = await self._llm_analysis(conversation_text, customer_last_message, context)

        # Combine heuristic and LLM results
        final_result = self._merge_results(heuristic_result, llm_result)

        # Add to history
        self.add_to_history({
            "conversation_text": conversation_text,
            "result": final_result,
            "timestamp": context.get("timestamp"),
        })

        status = AgentStatus.SUCCESS if final_result["has_sufficient_context"] else AgentStatus.NEED_MORE_INFO

        return AgentResponse(
            status=status,
            data=final_result,
            confidence=final_result["confidence"],
        )

    def _heuristic_analysis(self, conversation: str, last_message: str) -> Dict[str, Any]:
        """
        Fast rule-based analysis for common patterns
        """
        detected_entities = []
        needs_clarification = False
        clarification_needed_for = []
        detected_issue = ""
        confidence = 0.5

        # Detect common patterns
        patterns = {
            "error_code": r"error\s+(?:code\s+)?(\d+|[A-Z]+\d+)",
            "product_name": r"(?:using|with|on|for)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
            "version": r"version\s+(\d+\.\d+(?:\.\d+)?)",
            "feature": r"(?:feature|function|option|setting)\s+(?:called\s+)?([a-z_]+)",
        }

        for entity_type, pattern in patterns.items():
            matches = re.findall(pattern, conversation, re.IGNORECASE)
            for match in matches:
                detected_entities.append({
                    "type": entity_type,
                    "value": match,
                    "confidence": 0.8,
                })

        # Detect issue type
        issue_keywords = {
            "login_problem": ["can't log in", "login fail", "authentication", "password"],
            "performance_issue": ["slow", "lag", "freeze", "performance", "loading"],
            "error": ["error", "exception", "crash", "failure"],
            "feature_request": ["how to", "how can i", "is it possible", "can i"],
            "billing": ["charge", "bill", "payment", "invoice", "subscription"],
        }

        for issue_type, keywords in issue_keywords.items():
            if any(kw in conversation.lower() for kw in keywords):
                detected_issue = issue_type
                confidence = 0.7
                break

        # Check if sufficient context
        has_sufficient_context = False

        # Criteria for sufficient context:
        # Look at FULL CONVERSATION, not just last message
        # This prevents getting stuck in question loops

        conversation_word_count = len(conversation.split())
        last_message_word_count = len(last_message.split())
        has_entities = len(detected_entities) > 0
        has_issue = detected_issue != ""

        # If conversation has grown, we likely have enough context
        if conversation_word_count > 30:
            # Long conversation - definitely search
            has_sufficient_context = True
            confidence = 0.85
        elif conversation_word_count > 15 and (has_entities or has_issue):
            # Medium conversation with entities
            has_sufficient_context = True
            confidence = 0.80
        elif conversation_word_count > 10 and has_issue:
            # Some conversation with issue detected
            has_sufficient_context = True
            confidence = 0.75
        elif last_message_word_count < 3 and conversation_word_count < 10:
            # BOTH very short - need more info
            needs_clarification = True
            clarification_needed_for.append("problem_description")
            confidence = 0.6
        else:
            # Default: if there's ANY conversation, try searching
            has_sufficient_context = True
            confidence = 0.70

        # Check for vague questions - only if conversation is VERY short
        vague_patterns = ["help", "hi", "hello", "hey"]

        # Only ask for clarification if it's a greeting AND conversation is brand new
        if any(pattern in last_message.lower() for pattern in vague_patterns):
            if conversation_word_count < 5:
                needs_clarification = True
                clarification_needed_for.append("problem_description")
                has_sufficient_context = False
                confidence = 0.6

        return {
            "has_sufficient_context": has_sufficient_context,
            "detected_issue": detected_issue,
            "detected_entities": detected_entities,
            "confidence": confidence,
            "needs_clarification": needs_clarification,
            "clarification_needed_for": clarification_needed_for,
            "analysis_method": "heuristic",
        }

    async def _llm_analysis(
        self,
        conversation: str,
        last_message: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Use LLM for deeper semantic analysis
        """
        prompt = f"""You are analyzing a customer support conversation to determine if there's enough context to search a knowledge base.

Conversation history:
{conversation}

Customer's last message:
{last_message}

Analyze this conversation and provide:
1. Does the conversation contain enough specific information to search for solutions? (yes/no)
2. What is the customer's main issue or question? (one sentence)
3. What specific entities are mentioned? (products, features, error codes, versions)
4. Is clarification needed? What specific information is missing?

Respond in this exact format:
SUFFICIENT_CONTEXT: [yes/no]
MAIN_ISSUE: [brief description]
ENTITIES: [comma-separated list or "none"]
NEEDS_CLARIFICATION: [yes/no]
MISSING_INFO: [what's missing or "none"]
CONFIDENCE: [0.0-1.0]
"""

        try:
            response = self.llm.generate_answer("", prompt)  # Using prompt as context
            parsed = self._parse_llm_response(response)
            parsed["analysis_method"] = "llm"
            return parsed
        except Exception as e:
            # Fallback to low-confidence result
            return {
                "has_sufficient_context": False,
                "detected_issue": "",
                "detected_entities": [],
                "confidence": 0.3,
                "needs_clarification": True,
                "clarification_needed_for": ["llm_error"],
                "analysis_method": "llm_error",
                "error": str(e),
            }

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """Parse structured LLM response"""
        lines = response.strip().split("\n")
        result = {
            "has_sufficient_context": False,
            "detected_issue": "",
            "detected_entities": [],
            "confidence": 0.5,
            "needs_clarification": False,
            "clarification_needed_for": [],
        }

        for line in lines:
            if ":" not in line:
                continue

            key, value = line.split(":", 1)
            key = key.strip().upper()
            value = value.strip()

            if key == "SUFFICIENT_CONTEXT":
                result["has_sufficient_context"] = value.lower() in ["yes", "true"]
            elif key == "MAIN_ISSUE":
                result["detected_issue"] = value
            elif key == "ENTITIES":
                if value.lower() != "none":
                    entities = [e.strip() for e in value.split(",")]
                    result["detected_entities"] = [
                        {"type": "llm_detected", "value": e, "confidence": 0.7}
                        for e in entities if e
                    ]
            elif key == "NEEDS_CLARIFICATION":
                result["needs_clarification"] = value.lower() in ["yes", "true"]
            elif key == "MISSING_INFO":
                if value.lower() != "none":
                    result["clarification_needed_for"] = [e.strip() for e in value.split(",")]
            elif key == "CONFIDENCE":
                try:
                    result["confidence"] = float(value)
                except ValueError:
                    pass

        return result

    def _merge_results(self, heuristic: Dict[str, Any], llm: Dict[str, Any]) -> Dict[str, Any]:
        """
        Combine heuristic and LLM results, preferring LLM but keeping heuristic entities
        """
        # Merge entities (union of both)
        all_entities = heuristic.get("detected_entities", []) + llm.get("detected_entities", [])

        # Deduplicate by value
        seen_values = set()
        unique_entities = []
        for entity in all_entities:
            if entity["value"] not in seen_values:
                seen_values.add(entity["value"])
                unique_entities.append(entity)

        # Prefer LLM for issue detection if it found something
        detected_issue = llm.get("detected_issue", "") or heuristic.get("detected_issue", "")

        # Average confidence scores
        avg_confidence = (heuristic.get("confidence", 0.5) + llm.get("confidence", 0.5)) / 2

        # Combine clarification needs
        clarification_needed_for = list(set(
            heuristic.get("clarification_needed_for", []) +
            llm.get("clarification_needed_for", [])
        ))

        return {
            "has_sufficient_context": llm.get("has_sufficient_context", heuristic.get("has_sufficient_context", False)),
            "detected_issue": detected_issue,
            "detected_entities": unique_entities,
            "confidence": avg_confidence,
            "needs_clarification": llm.get("needs_clarification", heuristic.get("needs_clarification", False)),
            "clarification_needed_for": clarification_needed_for,
            "analysis_method": "hybrid",
        }
