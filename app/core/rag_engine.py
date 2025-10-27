from app.models.query import Query
from app.llm.base_llm import BaseLLM
from app.retriever.base_search_engine import BaseSearchEngine
from app.logging.logger import logger
from app.retriever.semantic_search_engine import SemanticSearchEngine, create_query
from typing import List, Union, Dict

class RAGEngine:
    def __init__(self, search_engine: BaseSearchEngine, llm: BaseLLM):
        self.search_engine = search_engine
        self.llm = llm

    def ask(self, query: Union[str, Query], language: str = "en") -> Dict:
        """
        Ask a question and get an answer with context

        Args:
            query: Either a string or a Query object
            language: Language code for response (e.g., 'en', 'fr', 'es')

        Returns:
            Dictionary with 'answer' and 'context_chunks'
        """
        # Convert string to Query object if needed
        if isinstance(query, str):
            query = create_query(query)

        chunks = self.search_engine.search(query)
        if not chunks:
            logger.info("Search engine has no answer")

            # No results message in requested language
            no_results_messages = {
                "en": "No relevant information found in the knowledge base.",
                "fr": "Aucune information pertinente trouvée dans la base de connaissances.",
                "es": "No se encontró información relevante en la base de conocimientos.",
                "de": "Keine relevanten Informationen in der Wissensdatenbank gefunden.",
                "it": "Nessuna informazione rilevante trovata nella base di conoscenza.",
                "pt": "Nenhuma informação relevante encontrada na base de conhecimento.",
                "ru": "В базе знаний не найдено релевантной информации.",
                "ja": "ナレッジベースに関連情報が見つかりませんでした。",
                "zh": "在知识库中未找到相关信息。",
                "ar": "لم يتم العثور على معلومات ذات صلة في قاعدة المعرفة.",
                "nl": "Geen relevante informatie gevonden in de kennisbank.",
            }

            return {
                "answer": no_results_messages.get(language, no_results_messages["en"]),
                "context_chunks": []
            }

        context = '\n\n'.join(chunk.text for chunk in chunks)
        answer = self.llm.generate_answer(query.text, context, language=language)

        return {
            "answer": answer,
            "context_chunks": [chunk.text for chunk in chunks]
        }

    def get_llm_model_name(self):
        return self.llm.model_name
    
    def get_search_engine_name(self):
        return self.search_engine.retriever_name