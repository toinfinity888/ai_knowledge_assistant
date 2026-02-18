from app.llm.base_llm import BaseLLM
import requests
from app.logging.logger import logger
import os
from typing import Optional
from dotenv import load_dotenv
load_dotenv()
from openai import OpenAI as OpenAIClient

client = OpenAIClient(
    api_key=os.environ['OPENAI_API_KEY'],
)

# Default prompts (used when no custom prompt is configured)
DEFAULT_RAG_PROMPTS = {
    "en": "You are a helpful technical support assistant. Use the context below to answer the user's question clearly and naturally. Answer in plain text without markdown formatting (no **, no ##). Be concise and direct.",
    "fr": "Vous êtes un assistant de support technique utile. Utilisez le contexte ci-dessous pour répondre de manière claire et naturelle. Répondez en texte brut sans formatage markdown.",
    "es": "Eres un asistente de soporte técnico útil. Usa el contexto a continuación para responder de manera clara y natural. Responde en texto plano sin formato markdown.",
}


class OpenAILLM(BaseLLM):
    def __init__(self, model_name: str = 'gpt-4o'):
        self.model_name = model_name

    def generate_answer(
        self,
        question: str,
        context: str,
        language: str = "en",
        company_id: Optional[int] = None,
    ) -> str:
        # Try to get custom prompt from database
        system_prompt = self._get_prompt(company_id, language)

        completion = client.chat.completions.create(
            model=self.model_name,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}
            ],
            temperature=0.2
        )
        return completion.choices[0].message.content

    def _get_prompt(self, company_id: Optional[int], language: str) -> str:
        """Get the prompt from database or fallback to default."""
        if company_id:
            try:
                from app.services.prompt_service import get_prompt_service
                prompt_service = get_prompt_service()
                prompt = prompt_service.get_prompt(company_id, "rag_answer", language)
                if prompt:
                    return prompt
            except Exception as e:
                logger.debug(f"Could not load custom prompt: {e}")

        # Fallback to default
        return DEFAULT_RAG_PROMPTS.get(language, DEFAULT_RAG_PROMPTS["en"])
