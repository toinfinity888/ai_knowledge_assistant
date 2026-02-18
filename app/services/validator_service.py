"""
Validator Service (Intelligence Gatekeeper - Stage 1)

Uses Groq Llama 8B to validate conversation context against the
Domain Schema Registry before triggering expensive RAG searches.
"""
import json
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from app.llm.llm_groq import GroqLLM, GroqValidationError
from app.services.domain_schema_service import DomainSchemaService
from app.database.postgresql_session import get_db_session

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Structured result from the Groq validator."""

    status: str  # "ready" | "missing_required" | "unknown_domain" | "error"
    domain: str = ""
    domain_name: str = ""
    domain_confidence: float = 0.0
    extracted_fields: Dict[str, Dict[str, str]] = field(default_factory=dict)
    missing_required: List[Dict[str, str]] = field(default_factory=list)
    missing_recommended: List[Dict[str, str]] = field(default_factory=list)
    optimized_query: str = ""
    reasoning: str = ""
    error_message: str = ""

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "domain": self.domain,
            "domain_name": self.domain_name,
            "domain_confidence": self.domain_confidence,
            "extracted_fields": self.extracted_fields,
            "missing_required": self.missing_required,
            "missing_recommended": self.missing_recommended,
            "optimized_query": self.optimized_query,
            "reasoning": self.reasoning,
            "error_message": self.error_message,
        }


class ValidatorService:
    """
    Stage 1 of the Intelligence Gatekeeper.
    Validates conversation context against domain schemas using Groq Llama 8B.
    """

    def __init__(
        self,
        groq_llm: GroqLLM,
        domain_schema_service: DomainSchemaService,
    ):
        self.groq_llm = groq_llm
        self.schema_service = domain_schema_service

    def validate(
        self,
        conversation_text: str,
        company_id: int,
        language: str = "en",
    ) -> ValidationResult:
        """
        Validate conversation against the company's domain schemas.

        Args:
            conversation_text: Full conversation history
            company_id: Company ID for loading schemas
            language: Language code for localized responses

        Returns:
            ValidationResult with status, fields, and optional search query
        """
        # Load domain schemas for this company
        print(f"[Validator] Loading domain schemas for company_id={company_id}")
        with get_db_session() as db:
            schemas = self.schema_service.get_schemas_for_validator(company_id, db)

        print(f"[Validator] Found {len(schemas) if schemas else 0} domain schemas")
        if schemas:
            for s in schemas:
                print(f"[Validator]   - Schema: {s.get('name')} (slug: {s.get('slug')})")

        if not schemas:
            logger.warning(f"No domain schemas found for company {company_id}")
            return ValidationResult(
                status="error",
                error_message="No domain schemas configured. Ask an admin to set up domain schemas.",
            )

        # Build system prompt
        system_prompt = self._build_system_prompt(schemas, language)

        # Call Groq Llama 8B
        print(f"[Validator] Calling Groq LLM for validation...")
        try:
            raw_result = self.groq_llm.validate_conversation(
                system_prompt=system_prompt,
                conversation_text=conversation_text,
            )
            print(f"[Validator] Groq raw result: {raw_result}")
        except GroqValidationError as e:
            logger.error(f"Groq validation failed: {e}")
            return ValidationResult(
                status="error",
                error_message=str(e),
            )

        # Parse and enrich the result
        parsed = self._parse_result(raw_result, schemas)
        print(f"[Validator] Parsed result: status={parsed.status}, domain={parsed.domain}")
        print(f"[Validator] Parsed missing_required: {parsed.missing_required}")
        print(f"[Validator] Parsed extracted_fields: {parsed.extracted_fields}")
        return parsed

    def _build_system_prompt(
        self, schemas: List[Dict[str, Any]], language: str
    ) -> str:
        """Build the system prompt dynamically from domain schemas."""
        domains_text = ""
        for schema in schemas:
            domains_text += f'\nDomain: "{schema["name"]}" (slug: "{schema["slug"]}")\n'
            if schema.get("description"):
                domains_text += f'  Description: {schema["description"]}\n'

            if schema["required_fields"]:
                domains_text += "  Required fields:\n"
                for f in schema["required_fields"]:
                    line = f'    - {f["name"]} ({f["field_type"]}): {f["description"]}'
                    if f.get("options"):
                        line += f' [Options: {", ".join(f["options"])}]'
                    domains_text += line + "\n"

            if schema["recommended_fields"]:
                domains_text += "  Recommended fields (not blocking):\n"
                for f in schema["recommended_fields"]:
                    line = f'    - {f["name"]} ({f["field_type"]}): {f["description"]}'
                    if f.get("options"):
                        line += f' [Options: {", ".join(f["options"])}]'
                    domains_text += line + "\n"

        return f"""You are a technical support conversation validator for a security and surveillance technology company.

TASK:
Analyze the following support conversation and:
1. Classify which technical domain the conversation belongs to
2. Extract all mentioned information fields from the conversation
3. Identify which required and recommended fields are still missing
4. If sufficient required information is present, generate an optimized search query for the knowledge base

AVAILABLE DOMAINS:
{domains_text}

RULES:
- If no domain matches, set domain to "unknown" and status to "unknown_domain"
- If required fields are missing, set status to "missing_required"
- If all required fields are present (even if recommended fields are missing), set status to "ready"
- The optimized_search_query should combine the detected domain, extracted field values, and the customer's core issue into a single focused search query suitable for semantic vector search
- Extract field values ONLY from what the customer explicitly stated — do not guess or infer
- For select fields, match to the closest option or use the exact value stated
- Respond in the following language for the reasoning field: {language}

OUTPUT FORMAT (respond with valid JSON only):
{{
  "domain": "domain_slug or unknown",
  "domain_confidence": 0.0,
  "extracted_fields": {{"field_slug": "extracted_value"}},
  "missing_required": ["field_slug"],
  "missing_recommended": ["field_slug"],
  "optimized_search_query": "search query string",
  "status": "ready | missing_required | unknown_domain",
  "reasoning": "brief explanation of classification and extraction"
}}"""

    def _parse_result(
        self, raw: dict, schemas: List[Dict[str, Any]]
    ) -> ValidationResult:
        """Parse raw Groq JSON into a ValidationResult with enriched field info."""
        status = raw.get("status", "error")
        domain_slug = raw.get("domain", "unknown")

        # Find the matching schema for human-readable names
        schema_match = None
        for s in schemas:
            if s["slug"] == domain_slug:
                schema_match = s
                break

        domain_name = schema_match["name"] if schema_match else domain_slug

        # Enrich extracted fields with human-readable names
        extracted = {}
        raw_extracted = raw.get("extracted_fields", {})
        if schema_match:
            all_fields = schema_match["required_fields"] + schema_match["recommended_fields"]
            field_name_map = {f["slug"]: f["name"] for f in all_fields}
            for slug, value in raw_extracted.items():
                if value and str(value).strip():
                    extracted[slug] = {
                        "value": str(value),
                        "field_name": field_name_map.get(slug, slug),
                    }

        # Enrich missing fields with names and descriptions
        missing_required = []
        missing_recommended = []

        # If no schema match, still show raw missing fields from Groq
        if not schema_match:
            print(f"[Validator] No schema match for domain '{domain_slug}', using raw missing fields")
            for slug in raw.get("missing_required", []):
                missing_required.append({
                    "slug": slug,
                    "name": slug.replace("_", " ").title(),
                    "description": "",
                })

        if schema_match:
            req_map = {f["slug"]: f for f in schema_match["required_fields"]}
            rec_map = {f["slug"]: f for f in schema_match["recommended_fields"]}

            print(f"[Validator] Schema required field slugs: {list(req_map.keys())}")
            print(f"[Validator] Groq returned missing_required: {raw.get('missing_required', [])}")

            for slug in raw.get("missing_required", []):
                if slug in req_map:
                    missing_required.append({
                        "slug": slug,
                        "name": req_map[slug]["name"],
                        "description": req_map[slug].get("description", ""),
                    })
                else:
                    # Slug not found in schema - add anyway with raw slug as name
                    print(f"[Validator] Missing field slug '{slug}' not found in schema, adding as-is")
                    missing_required.append({
                        "slug": slug,
                        "name": slug.replace("_", " ").title(),
                        "description": "",
                    })

            for slug in raw.get("missing_recommended", []):
                if slug in rec_map:
                    missing_recommended.append({
                        "slug": slug,
                        "name": rec_map[slug]["name"],
                        "description": rec_map[slug].get("description", ""),
                    })

        return ValidationResult(
            status=status,
            domain=domain_slug,
            domain_name=domain_name,
            domain_confidence=float(raw.get("domain_confidence", 0.0)),
            extracted_fields=extracted,
            missing_required=missing_required,
            missing_recommended=missing_recommended,
            optimized_query=raw.get("optimized_search_query", ""),
            reasoning=raw.get("reasoning", ""),
        )
