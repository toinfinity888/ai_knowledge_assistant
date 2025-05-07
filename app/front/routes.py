from flask import Blueprint, render_template, request
from app.core.rag_singelton import rag_engine
from app.query.query import Query
import os
from app.core.logger import logger

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
front = Blueprint("front", __name__, template_folder=template_dir)

@front.route("/", methods=['GET', 'POST'])
def index():
    answer = ''
    if request.method == 'POST':
        query_text = request.form['query']
        answer = rag_engine.ask(Query(text=query_text))
        if not answer:
            logger.info('RAG Engine no have an answer')
    return render_template('index.html', answer=answer)