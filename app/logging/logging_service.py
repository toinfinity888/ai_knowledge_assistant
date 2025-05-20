from app.models.query_logs import QueryLogs
from app.database.postgresql_session import SessionLocal
from app.logging.logger import logger
from typing import List

def user_query_logging(
                    query_text: str,
                    response_text: str,
                    has_response: bool,
                    response_status: str,
                    response_time_ms: int,
                    retriever_used: str,
                    llm_model_used: str,
                    retrieved_context: List[str],
                    user_id: str = 'anonymous'
                    ):
    session = SessionLocal()
    try:
        logs = QueryLogs(
            query_text=query_text,
            response_text=response_text,
            has_response=has_response,
            response_status=response_status,
            response_time_ms=response_time_ms,
            retriever_used=retriever_used,
            llm_model_used=llm_model_used,
            retrieved_context=retrieved_context,
            user_id=user_id,
        )
        session.add(logs)
        session.commit()
        
    except Exception as e:
        session.rollback()
        logger.info(f'Error: {e}')

    finally:
        session.close()