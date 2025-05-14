from ragas import EvaluationDataset, evaluate
from ragas.metrics import LLMContextRecall, Faithfulness, FactualCorrectness
from ragas.llms import LangchainLLMWrapper
from langchain_openai import ChatOpenAI
from app.search.search_engine import SemanticSearchEngine
from app.core.rag_engine import RAGEngine
from app.llm.llm_mistral import OllamaLlm
from app.llm.base_llm import BaseLLM
from app.vector_store.qdrant_vector_store import QdrantVectorStore
from app.config.app_config import config
from app.config.path_config import PROCESSED_DATA_DIR
from app.embedding.sentence_transformer_embedder import SentenceTransformerEmbedder
from app.query.query import Query
from app.core.logger import logger
from app.dashboard.log_history import upsert_logs_to_postgresql
from datetime import datetime
from dotenv import load_dotenv
from typing import List
from openai import OpenAI
import os
import json

load_dotenv()

llm_search = OllamaLlm()
llm_ragas = ChatOpenAI(model='gpt-4o',
                       openai_api_key=os.getenv('OPENAI_API_KEY'))
embedder = SentenceTransformerEmbedder()
vector_store = QdrantVectorStore(settings=config.qdrant)
search = SemanticSearchEngine(embedder=embedder, vector_store=vector_store)
rag = RAGEngine(search_engine=search, llm=llm_search)

sample_queries = [
    "What is impact of covid"
]

expected_responses = [
    'According to the provided context, COVID-19 has not had a material adverse impact on productivity or business as of December 31, 2022. However, the extent to which the pandemic may impact operational and financial performance remains uncertain due to factors such as the timing, severity, and duration of the pandemic, emergence of new variants, development and effectiveness of vaccines and treatments, imposition of protective public safety measures, and impact on the global economy and demand for products. The pandemic is also affecting the global supply chain, potentially causing disruptions to service providers, logistics, and product availability. These disruptions could negatively impact the ability to proceed with clinical trials, preclinical development, and other activities, delaying the ability to receive product approval and generate revenue. The continued spread of COVID-19 may lead to severe economic slowdown or recession or cause bankruptcy, which could adversely affect access to capital. In summary, while there has been no significant disruption or impairment as of December 31, 2022, the ongoing COVID-19 pandemic poses various risks and uncertainties that may impact the business, including operations, financial condition, cash flows, and prospects.'
]

dataset = []

for query, reference in zip(sample_queries, expected_responses):
    logger.info('Getting relevant docs...')
    relevant_docs: List[str] = rag.get_relevant_docs(query_text=query, engine=search)
    if relevant_docs:
        logger.info('Relevant docs recieved')
    else:
        logger.info('No relevant docs recieved')
        
    context = '\n\n'.join(text for text in relevant_docs)
    logger.info('Getting respons...')
    response = rag.ask(Query(text=query, user_id='demo'))

    if response:
        logger.info('Response recieved')
    else:
        logger.info('No response recieved')

    dataset.append({
        'user_input': query,
        'retrieved_contexts': relevant_docs,
        'response': response,
        'reference': reference
    })

evaluation_dataset = EvaluationDataset.from_list(dataset)
evaluator_llm = LangchainLLMWrapper(llm_ragas)

result = evaluate(dataset=evaluation_dataset,
                metrics=[LLMContextRecall(), Faithfulness(), FactualCorrectness()],
                llm=evaluator_llm)
                
print(result)
result_df = result.to_pandas()
result_df.rename(columns={
    'factual_correctness(mode=f1)': 'factual_correctness'
}, inplace=True)

timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
result_filename = f'evaluating_result_{timestamp_str}.json'
result_path = PROCESSED_DATA_DIR / result_filename
try:
    result_df.to_json(result_path, orient='records', indent=4)
except Exception as e:
    raise PermissionError(f'Error: {e}')
logger.info(f'Starting database upsert from {result_path}')
upsert_logs_to_postgresql(path=result_path)

