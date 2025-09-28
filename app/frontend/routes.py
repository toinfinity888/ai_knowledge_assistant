from flask import Blueprint, render_template, request
from app.core.rag_singelton import rag_engine
from app.models.query import Query
import os
from app.logging.logger import logger
from app.logging.logging_service import user_query_logging
import time

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
front = Blueprint("front", __name__, template_folder=template_dir)

@front.route("/", methods=['GET', 'POST'])
def index():
    answer = ''
    if request.method == 'POST':
        query_text = request.form['query']
        
        start = time.time()
        answer, retrieved_context = rag_engine.ask(Query(text=query_text))
        if not answer:
            logger.info('RAG Engine no have an answer')
        end = time.time()
        response_time_ms = (end - start) * 1000
            
        has_response = bool(answer and answer.strip())
        llm_model_used = rag_engine.get_llm_model_name()
        retriever_used = rag_engine.get_search_engine_name()
        
        user_query_logging(
            query_text=query_text,
            response_text=answer,
            has_response=has_response,
            response_status='OK', # May be extended in future
            response_time_ms=response_time_ms,
            retriever_used=retriever_used,
            llm_model_used=llm_model_used,
            retrieved_context=retrieved_context,
        )
        
    return render_template('index.html', answer=answer, retrieved_context=retrieved_context)