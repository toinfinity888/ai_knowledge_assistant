from llm.base_llm import BaseLLM
import requests

class OllamaLLM(BaseLLM):
    def __init__(self, model_name: str = 'mistral', base_url: str = 'http://localhost:11434')
        self.model_name = model_name
        self.base_url = base_url

    def generate_answer(self, question: str, context: str) -> str:
        prompt = f'{context}\n\n Question: {question}'
        response = requests.post(
            url=f'{self.base_url}/api/generate',
            json={
                'model': self.model_name,
                'promt': prompt,
                'stream': False
            }
        )
        if response.status_code == 200:
            return response.json().get('response', '').strip()
        else:
            raise RuntimeError(f'Ollama error {response.status_code}: {response.text}')

        