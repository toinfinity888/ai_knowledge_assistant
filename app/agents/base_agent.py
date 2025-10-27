from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum


class AgentStatus(Enum):
    SUCCESS = "success"
    NEED_MORE_INFO = "need_more_info"
    ERROR = "error"
    PENDING = "pending"


@dataclass
class AgentResponse:
    status: AgentStatus
    data: Dict[str, Any]
    message: Optional[str] = None
    confidence: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "data": self.data,
            "message": self.message,
            "confidence": self.confidence,
        }


class BaseAgent(ABC):
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        self.name = name
        self.config = config or {}
        self._history: List[Dict[str, Any]] = []

    @abstractmethod
    async def process(self, context: Dict[str, Any]) -> AgentResponse:
        """Main agent logic."""
        pass

    def add_to_history(self, entry: Dict[str, Any]) -> None:
        self._history.append(entry)

    def get_history(self) -> List[Dict[str, Any]]:
        return self._history

    def clear_history(self) -> None:
        self._history.clear()

    def _validate_context(self, context: Dict[str, Any], required_keys: list) -> bool:
        return all(key in context for key in required_keys)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name='{self.name}')>"