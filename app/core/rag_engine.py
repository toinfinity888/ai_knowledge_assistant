from app.query.query import Query
from app.llm.base_llm import BaseLLM
from app.core.base_search_engine import BaseSearchEngine
from app.core.logger import logger

class RAGEngine:
    def __init__(self, search_engine: BaseSearchEngine, llm: BaseLLM):
        self.search_engine = search_engine
        self.llm = llm

    def ask(self, query: Query) -> str:
        chunks = self.search_engine.search(query)
        if not chunks:
            logger.info("Search engine no have an answer")
        context = '\n\n'.join(chunk.text for chunk in chunks)
        return self.llm.generate_answer(query.text, context)
