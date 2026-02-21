from app.models.query_logs import QueryLogs
from app.database.postgresql_session import SessionLocal
from app.logging.logger import logger
from typing import List, Optional


def user_query_logging(
    query_text: str,
    response_text: str,
    has_response: bool,
    response_status: str,
    response_time_ms: int,
    retriever_used: str,
    llm_model_used: str,
    retrieved_context: List[str],
    user_id: str = 'anonymous',
    company_id: Optional[int] = None,
    session_id: Optional[int] = None,
    agent_user_id: Optional[int] = None,
    search_type: Optional[str] = None,
):
    """
    Log a user query to the database for analytics.

    Args:
        query_text: The search query text
        response_text: The response/answer text
        has_response: Whether a response was returned
        response_status: Status of the response ('OK', 'NO_RESPONSE', etc.)
        response_time_ms: Response time in milliseconds
        retriever_used: Name of the retriever/search engine used
        llm_model_used: Name of the LLM model used
        retrieved_context: List of retrieved context chunks
        user_id: User ID string (legacy)
        company_id: Company ID for multi-tenancy analytics
        session_id: Call session ID (integer FK to call_sessions)
        agent_user_id: Agent user ID (integer FK to users)
        search_type: Type of search ('manual', 'automatic', 'force_search')
    """
    db_session = SessionLocal()
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
            company_id=company_id,
            session_id=session_id,
            agent_user_id=agent_user_id,
            search_type=search_type,
        )
        db_session.add(logs)
        db_session.commit()
        logger.debug(f"Logged query: company_id={company_id}, session_id={session_id}, has_response={has_response}")

    except Exception as e:
        db_session.rollback()
        logger.error(f'Error logging query: {e}')

    finally:
        db_session.close()