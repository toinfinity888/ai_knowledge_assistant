from abc import ABC, abstractmethod

class BaseLLM(ABC):
    @abstractmethod
    def generate_answer(self, question: str, context: str, source: str) -> str:
        ...