from app.llm.base_llm import BaseLLM
import requests
from app.logging.logger import logger
from typing import Optional

# Default prompt
DEFAULT_PROMPT = """You are a helpful technical support assistant. Use the context below to answer the user's question clearly and naturally.
Answer in plain text without markdown formatting (no **, no ##). Be concise and direct.
If the context is insufficient, politely say that you don't have enough data to answer."""


class OllamaLlm(BaseLLM):
    def __init__(self, model_name: str = 'mistral:instruct', base_url: str = 'http://localhost:11434'):
        self.model_name = model_name
        self.base_url = base_url

    def generate_answer(
        self,
        question: str,
        context: str,
        language: str = "en",
        company_id: Optional[int] = None,
    ) -> str:
        system_prompt = self._get_prompt(company_id, language)

        prompt = f"{system_prompt}\n\nContext:\n{context}\n\nQuestion: {question}\n\nAnswer:"

        response = requests.post(
            url=f'{self.base_url}/api/generate',
            json={
                'model': self.model_name,
                'prompt': prompt,
                'stream': False
            }
        )
        if response.status_code == 200:
            logger.info(f"[Ollama] Sending prompt:\n{prompt[:300]}...\n")
            return response.json().get('response', '').strip()
        else:
            raise RuntimeError(f'Ollama error {response.status_code}: {response.text}')

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

        return DEFAULT_PROMPT

        