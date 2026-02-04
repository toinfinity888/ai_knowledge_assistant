"""
Groq LLM Client for Intelligence Gatekeeper

Uses Llama 3.1 8B via Groq API for fast, low-cost domain validation.
Does NOT extend BaseLLM because the validator needs structured JSON output,
not the simple generate_answer(question, context) interface.
"""
import os
import json
import logging
from typing import Optional

from groq import Groq

logger = logging.getLogger(__name__)


class GroqLLM:
    """Groq API client for Llama 8B inference with JSON mode."""

    def __init__(
        self,
        model_name: str = "llama-3.1-8b-instant",
        api_key: Optional[str] = None,
        timeout: float = 5.0,
    ):
        self.model_name = model_name
        self.timeout = timeout
        self.client = Groq(
            api_key=api_key or os.environ.get("GROQ_API_KEY"),
            timeout=timeout,
        )

    def validate_conversation(
        self,
        system_prompt: str,
        conversation_text: str,
    ) -> dict:
        """
        Send conversation to Llama 8B for domain validation.

        Args:
            system_prompt: System prompt with domain schemas and instructions
            conversation_text: Full conversation history to validate

        Returns:
            Parsed JSON dict with domain, fields, missing_fields, search_query

        Raises:
            GroqValidationError: If API call or JSON parsing fails
        """
        try:
            completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": conversation_text},
                ],
                temperature=0.1,
                max_tokens=1024,
                response_format={"type": "json_object"},
            )

            raw_content = completion.choices[0].message.content
            result = json.loads(raw_content)

            logger.info(
                f"Groq validation complete: domain={result.get('domain')}, "
                f"status={result.get('status')}"
            )
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Groq returned invalid JSON: {e}")
            raise GroqValidationError(f"Invalid JSON from Groq: {e}") from e
        except Exception as e:
            logger.error(f"Groq API error: {e}")
            raise GroqValidationError(f"Groq API call failed: {e}") from e


class GroqValidationError(Exception):
    """Raised when Groq validation fails (API error or invalid response)."""
    pass
