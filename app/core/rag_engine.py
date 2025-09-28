from app.models.query import Query
from app.llm.base_llm import BaseLLM
from app.retriever.base_search_engine import BaseSearchEngine
from app.logging.logger import logger
from app.retriever.semantic_search_engine import SemanticSearchEngine
from typing import List

class RAGEngine:
    def __init__(self, search_engine: BaseSearchEngine, llm: BaseLLM):
        self.search_engine = search_engine
        self.llm = llm

    def ask(self, query: Query) -> tuple[str, List[str]]:
        chunks = self.search_engine.search(query)
        if not chunks:
            logger.info("Search engine no have an answer")
        source = []
        for chunk in chunks:
            source.append(chunk.source)
        context = '\n\n'.join(chunk.content for chunk in chunks)
        answer = self.llm.generate_answer(query.text, context, source)
        return answer, [chunk.text for chunk in chunks]

    def get_llm_model_name(self):
        return self.llm.model_name
    
    def get_search_engine_name(self):
        return self.search_engine.retriever_name