"""
Query Formulation Agent
Transforms conversation context into precise, optimized queries for the knowledge base
"""
from typing import Dict, Any, List, Optional
from app.agents.base_agent import BaseAgent, AgentResponse, AgentStatus
from app.llm.base_llm import BaseLLM


class QueryFormulationAgent(BaseAgent):
    """
    Formulates optimized search queries based on:
    1. Detected issue/problem
    2. Extracted entities (products, features, error codes)
    3. Conversation context
    4. Previous query results (if any)
    """

    def __init__(self, llm: BaseLLM, config: Optional[Dict[str, Any]] = None):
        super().__init__(name="QueryFormulationAgent", config=config)
        self.llm = llm
        self.max_queries = config.get("max_queries", 3) if config else 3

    async def process(self, context: Dict[str, Any]) -> AgentResponse:
        """
        Generate optimized queries for knowledge base search

        Expected context:
            - detected_issue: str
            - detected_entities: List[Dict] (from ContextAnalyzerAgent)
            - conversation_text: str
            - customer_last_message: str
            - previous_queries: List[str] (optional: to avoid repetition)
            - previous_results_empty: bool (optional: if last query had no results)

        Returns:
            AgentResponse with:
                - queries: List[Dict] with 'text', 'type', 'confidence'
                - query_strategy: str (entity_based, semantic, hybrid)
                - suggested_filters: Dict (optional metadata filters)
        """
        # Validate input
        required = ["detected_issue", "detected_entities"]
        if not self._validate_context(context, required):
            return AgentResponse(
                status=AgentStatus.ERROR,
                data={},
                message=f"Missing required fields: {required}",
                confidence=0.0,
            )

        detected_issue = context["detected_issue"]
        detected_entities = context["detected_entities"]
        conversation = context.get("conversation_text", "")
        customer_message = context.get("customer_last_message", "")
        previous_queries = context.get("previous_queries", [])
        previous_results_empty = context.get("previous_results_empty", False)

        # Generate queries using multiple strategies
        queries = []

        # Strategy 1: Entity-based queries
        entity_queries = self._generate_entity_queries(detected_issue, detected_entities)
        queries.extend(entity_queries)

        # Strategy 2: Semantic/conversational query
        semantic_query = self._generate_semantic_query(detected_issue, customer_message, detected_entities)
        queries.append(semantic_query)

        # Strategy 3: LLM-enhanced query reformulation
        if previous_results_empty or len(previous_queries) > 0:
            llm_queries = await self._generate_llm_queries(
                conversation,
                customer_message,
                detected_issue,
                detected_entities,
                previous_queries,
            )
            queries.extend(llm_queries)

        # Deduplicate and rank
        unique_queries = self._deduplicate_queries(queries, previous_queries)
        ranked_queries = self._rank_queries(unique_queries)

        # Limit to max_queries
        final_queries = ranked_queries[:self.max_queries]

        # Determine query strategy
        strategy = self._determine_strategy(final_queries)

        # Generate suggested filters
        filters = self._generate_filters(detected_entities)

        result = {
            "queries": final_queries,
            "query_strategy": strategy,
            "suggested_filters": filters,
            "total_candidates": len(queries),
            "final_count": len(final_queries),
        }

        # Add to history
        self.add_to_history({
            "context": context,
            "result": result,
        })

        return AgentResponse(
            status=AgentStatus.SUCCESS,
            data=result,
            confidence=self._calculate_confidence(final_queries),
        )

    def _generate_entity_queries(
        self,
        issue: str,
        entities: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Generate queries based on detected entities
        Example: "login error" + entity "OAuth" -> "OAuth login error"
        """
        queries = []

        if not entities:
            return queries

        # Group entities by type
        entity_groups = {}
        for entity in entities:
            entity_type = entity.get("type", "unknown")
            if entity_type not in entity_groups:
                entity_groups[entity_type] = []
            entity_groups[entity_type].append(entity["value"])

        # Generate queries combining issue + entities
        for entity_type, values in entity_groups.items():
            for value in values:
                # Combine entity with issue
                if issue:
                    query_text = f"{value} {issue}"
                else:
                    query_text = value

                queries.append({
                    "text": query_text,
                    "type": f"entity_based_{entity_type}",
                    "confidence": entity.get("confidence", 0.7),
                    "entities_used": [value],
                })

        # Also try entity combinations
        if len(entities) >= 2:
            values = [e["value"] for e in entities[:2]]  # Top 2 entities
            combined = " ".join(values)
            if issue:
                combined += f" {issue}"

            queries.append({
                "text": combined,
                "type": "entity_combination",
                "confidence": 0.75,
                "entities_used": values,
            })

        return queries

    def _generate_semantic_query(
        self,
        issue: str,
        customer_message: str,
        entities: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate a natural language semantic query
        Uses the customer's own words for better semantic matching
        """
        # Start with customer's message
        query_parts = []

        # Add main issue
        if issue:
            query_parts.append(issue)

        # Add customer's actual words (truncated)
        if customer_message:
            # Take up to 15 words from customer message
            words = customer_message.split()[:15]
            customer_excerpt = " ".join(words)
            query_parts.append(customer_excerpt)

        # Combine
        query_text = " ".join(query_parts)

        return {
            "text": query_text,
            "type": "semantic_conversational",
            "confidence": 0.8,
            "entities_used": [e["value"] for e in entities[:3]],
        }

    async def _generate_llm_queries(
        self,
        conversation: str,
        customer_message: str,
        issue: str,
        entities: List[Dict[str, Any]],
        previous_queries: List[str],
    ) -> List[Dict[str, Any]]:
        """
        Use LLM to reformulate or expand queries
        Especially useful when previous queries had no results
        """
        entity_list = ", ".join([e["value"] for e in entities[:5]])
        previous_list = "\n".join([f"- {q}" for q in previous_queries]) if previous_queries else "None"

        prompt = f"""You are helping to search a technical knowledge base for customer support.

Customer's issue: {issue}
Detected entities: {entity_list}
Customer's message: {customer_message}

Previous queries tried (if any):
{previous_list}

Generate 2-3 alternative search queries that would help find relevant documentation or solutions.
Each query should be specific and focused on the technical problem.

Format:
QUERY_1: [query text]
QUERY_2: [query text]
QUERY_3: [query text]
"""

        try:
            response = self.llm.generate_answer("", prompt)
            parsed_queries = self._parse_llm_queries(response)
            return parsed_queries
        except Exception as e:
            # Return empty list on error
            return []

    def _parse_llm_queries(self, response: str) -> List[Dict[str, Any]]:
        """Parse LLM-generated queries"""
        queries = []
        lines = response.strip().split("\n")

        for line in lines:
            if ":" not in line:
                continue

            parts = line.split(":", 1)
            if len(parts) == 2 and parts[0].strip().startswith("QUERY_"):
                query_text = parts[1].strip()
                if query_text:
                    queries.append({
                        "text": query_text,
                        "type": "llm_reformulated",
                        "confidence": 0.7,
                        "entities_used": [],
                    })

        return queries

    def _deduplicate_queries(
        self,
        queries: List[Dict[str, Any]],
        previous_queries: List[str]
    ) -> List[Dict[str, Any]]:
        """Remove duplicate or very similar queries"""
        seen_texts = set(previous_queries)  # Exclude previous queries
        unique = []

        for query in queries:
            text = query["text"].lower().strip()

            # Skip if too similar to already seen
            if text in seen_texts:
                continue

            # Simple similarity check (avoid near-duplicates)
            is_duplicate = False
            for seen in seen_texts:
                if self._text_similarity(text, seen) > 0.9:
                    is_duplicate = True
                    break

            if not is_duplicate:
                unique.append(query)
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

    def _rank_queries(self, queries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Rank queries by expected effectiveness
        Priority: entity_based > semantic > llm
        Also consider confidence scores
        """
        def score_query(q: Dict[str, Any]) -> float:
            base_confidence = q.get("confidence", 0.5)

            # Type-based boost
            type_boost = {
                "entity_based_error_code": 1.0,
                "entity_based_product_name": 0.9,
                "entity_combination": 0.85,
                "semantic_conversational": 0.8,
                "llm_reformulated": 0.7,
            }

            boost = type_boost.get(q.get("type", ""), 0.6)

            # Entity count boost
            entity_count = len(q.get("entities_used", []))
            entity_boost = min(entity_count * 0.05, 0.2)

            return base_confidence * boost + entity_boost

        # Sort by score descending
        ranked = sorted(queries, key=score_query, reverse=True)
        return ranked

    def _determine_strategy(self, queries: List[Dict[str, Any]]) -> str:
        """Determine overall query strategy based on selected queries"""
        if not queries:
            return "none"

        types = [q.get("type", "") for q in queries]

        entity_count = sum(1 for t in types if "entity" in t)
        semantic_count = sum(1 for t in types if "semantic" in t)
        llm_count = sum(1 for t in types if "llm" in t)

        if entity_count > len(queries) / 2:
            return "entity_based"
        elif semantic_count > 0 and entity_count > 0:
            return "hybrid"
        elif llm_count > 0:
            return "llm_enhanced"
        else:
            return "semantic"

    def _generate_filters(self, entities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate metadata filters for vector search
        Example: filter by product, version, document type
        """
        filters = {}

        for entity in entities:
            entity_type = entity.get("type", "")
            value = entity.get("value", "")

            if entity_type == "product_name":
                filters["product"] = value
            elif entity_type == "version":
                filters["version"] = value
            elif entity_type == "error_code":
                filters["error_code"] = value

        return filters

    def _calculate_confidence(self, queries: List[Dict[str, Any]]) -> float:
        """Calculate overall confidence based on query quality"""
        if not queries:
            return 0.0

        # Average confidence of top queries
        avg_confidence = sum(q.get("confidence", 0.5) for q in queries) / len(queries)
        return min(avg_confidence, 1.0)
