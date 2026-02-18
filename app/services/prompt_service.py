"""
Prompt Service

Manages LLM prompts with company-specific customization and default fallbacks.
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.models.prompt_template import PromptTemplate, DEFAULT_PROMPTS
from app.database.postgresql_session import get_db_session


class PromptService:
    """Service for managing and retrieving LLM prompts."""

    def get_prompt(
        self,
        company_id: int,
        prompt_key: str,
        language: str = "en",
        db: Optional[Session] = None,
    ) -> str:
        """
        Get the prompt for a specific company, key, and language.

        Falls back to:
        1. Company's English prompt if language-specific not found
        2. Default prompt if company doesn't have custom prompt

        Args:
            company_id: Company ID
            prompt_key: Prompt identifier (e.g., "rag_answer", "validator")
            language: Language code
            db: Optional database session

        Returns:
            The system prompt string
        """
        def _get(session: Session) -> str:
            # Try exact match first
            prompt = session.query(PromptTemplate).filter(
                PromptTemplate.company_id == company_id,
                PromptTemplate.prompt_key == prompt_key,
                PromptTemplate.language == language,
                PromptTemplate.is_active == True,
            ).first()

            if prompt:
                return prompt.system_prompt

            # Fallback to English for this company
            if language != "en":
                prompt = session.query(PromptTemplate).filter(
                    PromptTemplate.company_id == company_id,
                    PromptTemplate.prompt_key == prompt_key,
                    PromptTemplate.language == "en",
                    PromptTemplate.is_active == True,
                ).first()

                if prompt:
                    return prompt.system_prompt

            # Fallback to default prompts
            return self._get_default_prompt(prompt_key, language)

        if db:
            return _get(db)
        else:
            with get_db_session() as session:
                return _get(session)

    def _get_default_prompt(self, prompt_key: str, language: str) -> str:
        """Get the default prompt from the DEFAULT_PROMPTS dict."""
        if prompt_key not in DEFAULT_PROMPTS:
            return ""

        prompts_for_key = DEFAULT_PROMPTS[prompt_key]

        if language in prompts_for_key:
            return prompts_for_key[language]["system_prompt"]

        # Fallback to English
        if "en" in prompts_for_key:
            return prompts_for_key["en"]["system_prompt"]

        return ""

    def get_all_prompts(
        self,
        company_id: int,
        db: Optional[Session] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get all prompts for a company, including defaults for missing ones.

        Returns list of prompt dicts with is_custom flag.
        """
        def _get(session: Session) -> List[Dict[str, Any]]:
            # Get custom prompts
            custom_prompts = session.query(PromptTemplate).filter(
                PromptTemplate.company_id == company_id,
            ).all()

            custom_map = {
                (p.prompt_key, p.language): p for p in custom_prompts
            }

            result = []

            # Include all default prompts
            for key, languages in DEFAULT_PROMPTS.items():
                for lang, defaults in languages.items():
                    if (key, lang) in custom_map:
                        # Use custom prompt
                        p = custom_map[(key, lang)]
                        result.append({
                            "id": p.id,
                            "prompt_key": p.prompt_key,
                            "language": p.language,
                            "name": p.name,
                            "description": p.description,
                            "system_prompt": p.system_prompt,
                            "is_active": p.is_active,
                            "is_custom": True,
                            "updated_at": p.updated_at,
                        })
                    else:
                        # Use default
                        result.append({
                            "id": None,
                            "prompt_key": key,
                            "language": lang,
                            "name": defaults["name"],
                            "description": defaults["description"],
                            "system_prompt": defaults["system_prompt"],
                            "is_active": True,
                            "is_custom": False,
                            "updated_at": None,
                        })

            # Sort by key, then language
            result.sort(key=lambda x: (x["prompt_key"], x["language"]))
            return result

        if db:
            return _get(db)
        else:
            with get_db_session() as session:
                return _get(session)

    def save_prompt(
        self,
        company_id: int,
        prompt_key: str,
        language: str,
        name: str,
        system_prompt: str,
        description: Optional[str] = None,
        user_id: Optional[int] = None,
        db: Optional[Session] = None,
    ) -> PromptTemplate:
        """
        Create or update a custom prompt for a company.
        """
        def _save(session: Session) -> PromptTemplate:
            prompt = session.query(PromptTemplate).filter(
                PromptTemplate.company_id == company_id,
                PromptTemplate.prompt_key == prompt_key,
                PromptTemplate.language == language,
            ).first()

            if prompt:
                # Update existing
                prompt.name = name
                prompt.description = description
                prompt.system_prompt = system_prompt
                prompt.updated_by = user_id
            else:
                # Create new
                prompt = PromptTemplate(
                    company_id=company_id,
                    prompt_key=prompt_key,
                    language=language,
                    name=name,
                    description=description,
                    system_prompt=system_prompt,
                    created_by=user_id,
                    updated_by=user_id,
                )
                session.add(prompt)

            session.commit()
            session.refresh(prompt)
            return prompt

        if db:
            return _save(db)
        else:
            with get_db_session() as session:
                return _save(session)

    def reset_to_default(
        self,
        company_id: int,
        prompt_key: str,
        language: str,
        db: Optional[Session] = None,
    ) -> bool:
        """
        Reset a prompt to default by deleting the custom version.
        """
        def _reset(session: Session) -> bool:
            prompt = session.query(PromptTemplate).filter(
                PromptTemplate.company_id == company_id,
                PromptTemplate.prompt_key == prompt_key,
                PromptTemplate.language == language,
            ).first()

            if prompt:
                session.delete(prompt)
                session.commit()
                return True
            return False

        if db:
            return _reset(db)
        else:
            with get_db_session() as session:
                return _reset(session)


# Singleton instance
_prompt_service: Optional[PromptService] = None


def get_prompt_service() -> PromptService:
    """Get the singleton PromptService instance."""
    global _prompt_service
    if _prompt_service is None:
        _prompt_service = PromptService()
    return _prompt_service
