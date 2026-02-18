from abc import ABC, abstractmethod
from typing import Optional


class BaseLLM(ABC):
    @abstractmethod
    def generate_answer(
        self,
        question: str,
        context: str,
        language: str = "en",
        company_id: Optional[int] = None,
    ) -> str:
        ...