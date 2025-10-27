"""
Clarification Agent
Generates intelligent clarifying questions when context is insufficient
"""
from typing import Dict, Any, List, Optional
from app.agents.base_agent import BaseAgent, AgentResponse, AgentStatus
from app.llm.base_llm import BaseLLM


class ClarificationAgent(BaseAgent):
    """
    Generates clarifying questions to gather missing information

    Activates when:
    1. ContextAnalyzerAgent indicates insufficient context
    2. Query results are poor/empty
    3. Multiple possible interpretations exist
    """

    def __init__(self, llm: BaseLLM, config: Optional[Dict[str, Any]] = None):
        super().__init__(name="ClarificationAgent", config=config)
        self.llm = llm
        self.max_questions = config.get("max_questions", 2) if config else 2

    async def process(self, context: Dict[str, Any]) -> AgentResponse:
        """
        Generate clarifying questions

        Expected context:
            - conversation_text: str
            - detected_issue: str
            - detected_entities: List[Dict]
            - clarification_needed_for: List[str] (what's missing)
            - customer_last_message: str
            - query_results_count: int (optional: number of results from previous query)

        Returns:
            AgentResponse with:
                - questions: List[Dict] with 'text', 'purpose', 'priority'
                - suggestion_type: str (specific_detail, disambiguation, confirmation)
                - display_to_agent: bool (should show to support agent)
        """
        # Validate input
        required = ["conversation_text", "clarification_needed_for"]
        if not self._validate_context(context, required):
            return AgentResponse(
                status=AgentStatus.ERROR,
                data={},
                message=f"Missing required fields: {required}",
                confidence=0.0,
            )

        conversation = context["conversation_text"]
        clarification_needed_for = context["clarification_needed_for"]
        detected_issue = context.get("detected_issue", "")
        detected_entities = context.get("detected_entities", [])
        customer_message = context.get("customer_last_message", "")
        query_results_count = context.get("query_results_count", -1)

        # Generate questions based on what's missing
        questions = []

        # Rule-based questions for common scenarios
        template_questions = self._generate_template_questions(
            clarification_needed_for,
            detected_issue,
            detected_entities,
        )
        questions.extend(template_questions)

        # LLM-generated contextual questions
        if len(questions) < self.max_questions or query_results_count == 0:
            llm_questions = await self._generate_llm_questions(
                conversation,
                customer_message,
                detected_issue,
                clarification_needed_for,
            )
            questions.extend(llm_questions)

        # Deduplicate and prioritize
        unique_questions = self._deduplicate_questions(questions)
        prioritized = self._prioritize_questions(unique_questions)

        # Limit to max_questions
        final_questions = prioritized[:self.max_questions]

        # Determine suggestion type
        suggestion_type = self._determine_suggestion_type(clarification_needed_for)

        # Should we show this to the agent? (Only if questions are high quality)
        display_to_agent = self._should_display(final_questions, context)

        result = {
            "questions": final_questions,
            "suggestion_type": suggestion_type,
            "display_to_agent": display_to_agent,
            "clarification_reasons": clarification_needed_for,
        }

        # Add to history
        self.add_to_history({
            "context": context,
            "result": result,
        })

        return AgentResponse(
            status=AgentStatus.SUCCESS,
            data=result,
            confidence=self._calculate_confidence(final_questions),
        )

    def _generate_template_questions(
        self,
        needed_for: List[str],
        issue: str,
        entities: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Generate questions from templates based on common missing info patterns
        """
        questions = []

        # Template mapping
        templates = {
            "problem_description": [
                {
                    "text": "Can you describe what exactly happens when you encounter this issue?",
                    "purpose": "get_detailed_description",
                    "priority": 1,
                },
                {
                    "text": "What are you trying to do when this problem occurs?",
                    "purpose": "understand_context",
                    "priority": 2,
                },
            ],
            "specific_details": [
                {
                    "text": "Could you provide more specific details about what's not working?",
                    "purpose": "get_specifics",
                    "priority": 1,
                },
            ],
            "error_details": [
                {
                    "text": "Do you see any error message or error code?",
                    "purpose": "get_error_code",
                    "priority": 1,
                },
            ],
            "product_version": [
                {
                    "text": "Which version of the product are you using?",
                    "purpose": "get_version",
                    "priority": 2,
                },
            ],
            "feature_name": [
                {
                    "text": "Which specific feature or function are you trying to use?",
                    "purpose": "identify_feature",
                    "priority": 1,
                },
            ],
            "reproduction_steps": [
                {
                    "text": "Can you walk me through the steps you took before this happened?",
                    "purpose": "get_reproduction_steps",
                    "priority": 2,
                },
            ],
            "when_started": [
                {
                    "text": "When did you first notice this issue?",
                    "purpose": "timeline",
                    "priority": 3,
                },
            ],
        }

        # Add questions based on what's needed
        for need in needed_for:
            if need in templates:
                questions.extend(templates[need])

        # If issue is vague, add clarification
        vague_terms = ["doesn't work", "not working", "broken", "problem", "issue"]
        if any(term in issue.lower() for term in vague_terms):
            questions.append({
                "text": "What specifically isn't working as expected?",
                "purpose": "clarify_vague_issue",
                "priority": 1,
            })

        # If no entities, try to get product/feature
        if not entities:
            questions.append({
                "text": "Which product or feature does this concern?",
                "purpose": "identify_product",
                "priority": 1,
            })

        return questions

    async def _generate_llm_questions(
        self,
        conversation: str,
        customer_message: str,
        issue: str,
        needed_for: List[str],
    ) -> List[Dict[str, Any]]:
        """
        Use LLM to generate contextually appropriate clarifying questions
        """
        needed_str = ", ".join(needed_for)

        prompt = f"""You are a support agent assistant. Based on this conversation, generate 1-2 specific clarifying questions to ask the customer.

Conversation:
{conversation}

Customer's last message:
{customer_message}

Detected issue: {issue if issue else "unclear"}
Missing information: {needed_str}

Generate questions that are:
1. Specific and actionable
2. Natural and conversational
3. Focused on getting the missing technical details

Format:
QUESTION_1: [question text] | PURPOSE: [why asking]
QUESTION_2: [question text] | PURPOSE: [why asking]
"""

        try:
            response = self.llm.generate_answer("", prompt)
            parsed = self._parse_llm_questions(response)
            return parsed
        except Exception as e:
            return []

    def _parse_llm_questions(self, response: str) -> List[Dict[str, Any]]:
        """Parse LLM-generated questions"""
        questions = []
        lines = response.strip().split("\n")

        for line in lines:
            if ":" not in line:
                continue

            # Parse format: QUESTION_1: text | PURPOSE: purpose
            if line.startswith("QUESTION_"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    content = parts[1].strip()

                    # Split text and purpose
                    if "|" in content:
                        text_part, purpose_part = content.split("|", 1)
                        text = text_part.strip()
                        purpose = purpose_part.replace("PURPOSE:", "").strip()
                    else:
                        text = content
                        purpose = "llm_generated"

                    if text:
                        questions.append({
                            "text": text,
                            "purpose": purpose,
                            "priority": 2,  # LLM questions get medium priority
                        })

        return questions

    def _deduplicate_questions(self, questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate or very similar questions"""
        seen_texts = set()
        unique = []

        for question in questions:
            text = question["text"].lower().strip()

            # Skip exact duplicates
            if text in seen_texts:
                continue

            # Check similarity to existing
            is_similar = False
            for seen in seen_texts:
                if self._text_similarity(text, seen) > 0.8:
                    is_similar = True
                    break

            if not is_similar:
                unique.append(question)
                seen_texts.add(text)

        return unique

    def _text_similarity(self, text1: str, text2: str) -> float:
        """Simple Jaccard similarity"""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        return len(intersection) / len(union)

    def _prioritize_questions(self, questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Sort questions by priority
        Priority 1 = most important (error codes, specific details)
        Priority 3 = least important (timeline, when started)
        """
        return sorted(questions, key=lambda q: q.get("priority", 2))

    def _determine_suggestion_type(self, needed_for: List[str]) -> str:
        """Determine the type of clarification needed"""
        if not needed_for:
            return "general"

        # Check for specific patterns
        if "error_details" in needed_for or "error_code" in needed_for:
            return "error_clarification"
        elif "product_version" in needed_for or "feature_name" in needed_for:
            return "product_clarification"
        elif "problem_description" in needed_for or "specific_details" in needed_for:
            return "detail_clarification"
        else:
            return "general_clarification"

    def _should_display(self, questions: List[Dict[str, Any]], context: Dict[str, Any]) -> bool:
        """
        Decide if questions should be shown to the support agent

        Show if:
        1. We have high-quality questions
        2. Previous query had no results
        3. Context is very unclear
        """
        if not questions:
            return False

        # Always show if previous query had no results
        query_results_count = context.get("query_results_count", -1)
        if query_results_count == 0:
            return True

        # Show if we have priority 1 questions
        has_high_priority = any(q.get("priority", 3) == 1 for q in questions)
        if has_high_priority:
            return True

        # Show if clarification is critical
        critical_needs = ["error_details", "problem_description", "specific_details"]
        clarification_needed_for = context.get("clarification_needed_for", [])
        has_critical_need = any(need in critical_needs for need in clarification_needed_for)

        return has_critical_need

    def _calculate_confidence(self, questions: List[Dict[str, Any]]) -> float:
        """Calculate confidence based on question quality"""
        if not questions:
            return 0.0

        # Higher confidence for higher priority questions
        priority_scores = {1: 0.9, 2: 0.75, 3: 0.6}

        total_score = sum(priority_scores.get(q.get("priority", 2), 0.7) for q in questions)
        avg_score = total_score / len(questions)

        return min(avg_score, 1.0)
