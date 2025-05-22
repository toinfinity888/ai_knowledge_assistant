from app.llm.base_llm import BaseLLM
import requests
from app.logging.logger import logger
import os 
from openai import OpenAI

client = OpenAI(
    api_key=os.environ['OPENAI_API_KEY'],
)
class OpenAI(BaseLLM):
    def __init__(self, model_name: str = 'gpt-4o'):
        self.model_name = model_name

    def generate_answer(self, question: str, context: str) -> str:
        prompt = ("You are a helpful AI assistant. Use the context below to answer the user's question clearly and naturally. "
            "If the context contains enough information, give a concise and informative answer. "
            "If the context is insufficient or irrelevant, politely say that you don’t have enough data to answer.\n\n"
            f"Context:\n{context}\n\n"
            f"Question: {question}\n\n"
            "Answer:")
        
        completion = client.chat.completions.create(
            model=self.model_name,
            messages=[
                {'role': 'system', 'content': "You are a helpful AI assistant. Use the context below to answer the user's question clearly and naturally."},
                {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}
            ],
            temperature=0.2
        )
        return completion.choices[0].message.content