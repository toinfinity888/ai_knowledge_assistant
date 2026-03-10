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
    "en": "You are a helpful technical support assistant. Use the context below to answer the user's question clearly and naturally. Answer in plain text without markdown formatting (no **, no ##). Be concise and direct. IMPORTANT: Always respond in English.",
    "fr": "You are a helpful technical support assistant. Use the context below to answer the user's question clearly and naturally. Answer in plain text without markdown formatting (no **, no ##). Be concise and direct. IMPORTANT: Always respond in French (français). Répondez toujours en français, même si le contexte est en anglais.",
    "es": "You are a helpful technical support assistant. Use the context below to answer the user's question clearly and naturally. Answer in plain text without markdown formatting (no **, no ##). Be concise and direct. IMPORTANT: Always respond in Spanish (español). Responde siempre en español, incluso si el contexto está en inglés.",
    "de": "You are a helpful technical support assistant. Use the context below to answer the user's question clearly and naturally. Answer in plain text without markdown formatting (no **, no ##). Be concise and direct. IMPORTANT: Always respond in German (Deutsch). Antworten Sie immer auf Deutsch, auch wenn der Kontext auf Englisch ist.",
    "it": "You are a helpful technical support assistant. Use the context below to answer the user's question clearly and naturally. Answer in plain text without markdown formatting (no **, no ##). Be concise and direct. IMPORTANT: Always respond in Italian (italiano). Rispondi sempre in italiano, anche se il contesto è in inglese.",
    "pt": "You are a helpful technical support assistant. Use the context below to answer the user's question clearly and naturally. Answer in plain text without markdown formatting (no **, no ##). Be concise and direct. IMPORTANT: Always respond in Portuguese (português). Responda sempre em português, mesmo que o contexto esteja em inglês.",
    "ru": "You are a helpful technical support assistant. Use the context below to answer the user's question clearly and naturally. Answer in plain text without markdown formatting (no **, no ##). Be concise and direct. IMPORTANT: Always respond in Russian (русский). Всегда отвечайте на русском языке, даже если контекст на английском.",
    "nl": "You are a helpful technical support assistant. Use the context below to answer the user's question clearly and naturally. Answer in plain text without markdown formatting (no **, no ##). Be concise and direct. IMPORTANT: Always respond in Dutch (Nederlands). Antwoord altijd in het Nederlands, zelfs als de context in het Engels is.",
    "ja": "You are a helpful technical support assistant. Use the context below to answer the user's question clearly and naturally. Answer in plain text without markdown formatting (no **, no ##). Be concise and direct. IMPORTANT: Always respond in Japanese (日本語). コンテキストが英語であっても、必ず日本語で回答してください。",
    "zh": "You are a helpful technical support assistant. Use the context below to answer the user's question clearly and naturally. Answer in plain text without markdown formatting (no **, no ##). Be concise and direct. IMPORTANT: Always respond in Chinese (中文). 即使上下文是英文的，也请始终用中文回答。",
    "ar": "You are a helpful technical support assistant. Use the context below to answer the user's question clearly and naturally. Answer in plain text without markdown formatting (no **, no ##). Be concise and direct. IMPORTANT: Always respond in Arabic (العربية). أجب دائمًا باللغة العربية، حتى لو كان السياق باللغة الإنجليزية.",
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
