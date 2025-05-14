from app.llm.base_llm import BaseLLM
import requests
from app.core.logger import logger

class OllamaLlm(BaseLLM):
    def __init__(self, model_name: str = 'mistral:instruct', base_url: str = 'http://localhost:11434'):
        self.model_name = model_name
        self.base_url = base_url

    def generate_answer(self, question: str, context: str) -> str:

        prompt = ("You are a helpful AI assistant. Use the context below to answer the user's question clearly and naturally. "
                "If the context contains enough information, give a concise and informative answer. "
                "If the context is insufficient or irrelevant, politely say that you don’t have enough data to answer.\n\n"
                f"Context:\n{context}\n\n"
                f"Question: {question}\n\n"
                "Answer:")
        
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

        