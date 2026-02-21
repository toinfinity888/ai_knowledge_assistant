"""
Analytics Service

Handles analytics data aggregation and retrieval for the dashboard.
"""
import logging
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy import func, and_, case
from sqlalchemy.orm import Session

from app.models.session_feedback import SessionFeedback
from app.models.field_edit_log import FieldEditLog
from app.models.analytics_summary import AnalyticsDailySummary
from app.models.call_session import CallSession, Suggestion
from app.models.query_logs import QueryLogs
from app.models.user import User
from app.database.postgresql_session import get_db_session

logger = logging.getLogger(__name__)


class AnalyticsService:
    """
    Service for managing analytics data.

    Handles:
    - Recording feedback and field edits
    - Aggregating metrics for dashboard
    - Per-user statistics
    """

    def record_feedback(
        self,
        session_id: int,
        company_id: int,
        agent_user_id: Optional[int],
        solution_rating: Optional[int],
        speech_recognition_rating: Optional[int],
        solution_found: Optional[bool],
        issue_resolved: Optional[bool],
        comments: Optional[str] = None,
    ) -> SessionFeedback:
        """
        Record post-session feedback.

        Args:
            session_id: Call session ID
            company_id: Company ID
            agent_user_id: User ID of the agent
            solution_rating: 1-5 star rating for solution
            speech_recognition_rating: 1-5 star rating for transcription
            solution_found: Whether correct solution was found
            issue_resolved: Whether issue was resolved
            comments: Optional feedback comments

        Returns:
            Created SessionFeedback record
        """
        with get_db_session() as db:
            feedback = SessionFeedback(
                session_id=session_id,
                company_id=company_id,
                agent_user_id=agent_user_id,
                solution_rating=solution_rating,
                speech_recognition_rating=speech_recognition_rating,
                solution_found=solution_found,
                issue_resolved=issue_resolved,
                comments=comments,
                created_at=datetime.utcnow(),
            )
            db.add(feedback)
            db.commit()
            db.refresh(feedback)

            logger.info(f"Recorded feedback for session {session_id}")
            return feedback

    def record_field_edits(
        self,
        session_id: int,
        company_id: int,
        agent_user_id: Optional[int],
        edits: List[Dict[str, Any]],
    ) -> int:
        """
        Record field edit events.

        Args:
            session_id: Call session ID
            company_id: Company ID
            agent_user_id: User ID of the agent
            edits: List of edit dictionaries with field_slug, field_name, original_value, edited_value

        Returns:
            Number of edits recorded
        """
        with get_db_session() as db:
            count = 0
            for edit in edits:
                field_edit = FieldEditLog(
                    session_id=session_id,
                    company_id=company_id,
                    agent_user_id=agent_user_id,
                    field_slug=edit.get('field_slug'),
                    field_name=edit.get('field_name'),
                    original_value=edit.get('original_value'),
                    edited_value=edit.get('edited_value'),
                    edited_at=datetime.utcnow(),
                )
                db.add(field_edit)
                count += 1

            db.commit()
            logger.info(f"Recorded {count} field edits for session {session_id}")
            return count

    def get_dashboard_data(
        self,
        company_id: int,
        period: str = 'week',
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Get aggregated dashboard analytics.

        Args:
            company_id: Company ID
            period: 'day', 'week', 'month', 'year'
            start_date: Optional start date
            end_date: Optional end date
            user_id: Optional user ID filter

        Returns:
            Dashboard data dictionary
        """
        with get_db_session() as db:
            # Calculate date range
            if not end_date:
                end_date = date.today()
            if not start_date:
                if period == 'day':
                    start_date = end_date
                elif period == 'week':
                    start_date = end_date - timedelta(days=7)
                elif period == 'month':
                    start_date = end_date - timedelta(days=30)
                elif period == 'year':
                    start_date = end_date - timedelta(days=365)
                else:
                    start_date = end_date - timedelta(days=7)

            # Convert dates to datetime for querying
            start_dt = datetime.combine(start_date, datetime.min.time())
            end_dt = datetime.combine(end_date, datetime.max.time())

            summary = self._get_summary(db, company_id, start_dt, end_dt, user_id)
            trends = self._get_trends(db, company_id, start_dt, end_dt)
            by_user = self._get_by_user(db, company_id, start_dt, end_dt)
            top_edited_fields = self._get_top_edited_fields(db, company_id, start_dt, end_dt)
            top_sources = self._get_top_sources(db, company_id, start_dt, end_dt)

            return {
                'summary': summary,
                'trends': trends,
                'by_user': by_user,
                'top_edited_fields': top_edited_fields,
                'top_sources': top_sources,
            }

    def _get_summary(
        self,
        db: Session,
        company_id: int,
        start_dt: datetime,
        end_dt: datetime,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get summary statistics."""
        # Base filters
        session_filter = and_(
            CallSession.company_id == company_id,
            CallSession.start_time >= start_dt,
            CallSession.start_time <= end_dt,
        )
        if user_id:
            session_filter = and_(session_filter, CallSession.agent_user_id == user_id)

        # Session counts
        total_sessions = db.query(func.count(CallSession.id)).filter(session_filter).scalar() or 0

        # Feedback stats
        feedback_filter = and_(
            SessionFeedback.company_id == company_id,
            SessionFeedback.created_at >= start_dt,
            SessionFeedback.created_at <= end_dt,
        )
        if user_id:
            feedback_filter = and_(feedback_filter, SessionFeedback.agent_user_id == user_id)

        feedback_stats = db.query(
            func.count(SessionFeedback.id).label('count'),
            func.avg(SessionFeedback.solution_rating).label('avg_solution'),
            func.avg(SessionFeedback.speech_recognition_rating).label('avg_speech'),
            func.sum(case((SessionFeedback.solution_found == True, 1), else_=0)).label('solutions_found'),
            func.sum(case((SessionFeedback.issue_resolved == True, 1), else_=0)).label('issues_resolved'),
        ).filter(feedback_filter).first()

        sessions_with_feedback = feedback_stats.count or 0
        avg_solution_rating = float(feedback_stats.avg_solution) if feedback_stats.avg_solution else None
        avg_speech_rating = float(feedback_stats.avg_speech) if feedback_stats.avg_speech else None
        solutions_found = feedback_stats.solutions_found or 0
        issues_resolved = feedback_stats.issues_resolved or 0

        # Search stats
        search_filter = and_(
            QueryLogs.company_id == company_id,
            QueryLogs.timestamp >= start_dt,
            QueryLogs.timestamp <= end_dt,
        )
        if user_id:
            search_filter = and_(search_filter, QueryLogs.agent_user_id == user_id)

        search_stats = db.query(
            func.count(QueryLogs.id).label('total'),
            func.sum(case((QueryLogs.has_response == False, 1), else_=0)).label('zero_results'),
            func.avg(QueryLogs.response_time_ms).label('avg_response_time'),
        ).filter(search_filter).first()

        total_searches = search_stats.total or 0
        zero_result_searches = search_stats.zero_results or 0
        avg_response_time = float(search_stats.avg_response_time) if search_stats.avg_response_time else None

        # Field edits
        edit_filter = and_(
            FieldEditLog.company_id == company_id,
            FieldEditLog.edited_at >= start_dt,
            FieldEditLog.edited_at <= end_dt,
        )
        if user_id:
            edit_filter = and_(edit_filter, FieldEditLog.agent_user_id == user_id)

        total_field_edits = db.query(func.count(FieldEditLog.id)).filter(edit_filter).scalar() or 0

        # Suggestion stats
        suggestion_filter = and_(
            Suggestion.session.has(CallSession.company_id == company_id),
            Suggestion.created_at >= start_dt,
            Suggestion.created_at <= end_dt,
        )

        suggestion_stats = db.query(
            func.sum(case((Suggestion.shown_to_agent == True, 1), else_=0)).label('shown'),
            func.sum(case((Suggestion.agent_clicked == True, 1), else_=0)).label('clicked'),
        ).filter(suggestion_filter).first()

        suggestions_shown = suggestion_stats.shown or 0
        suggestions_clicked = suggestion_stats.clicked or 0

        # Session duration
        duration_stats = db.query(
            func.avg(CallSession.duration_seconds).label('avg_duration')
        ).filter(
            session_filter,
            CallSession.duration_seconds.isnot(None)
        ).first()

        avg_session_duration = float(duration_stats.avg_duration) if duration_stats.avg_duration else None

        return {
            'total_sessions': total_sessions,
            'sessions_with_feedback': sessions_with_feedback,
            'avg_solution_rating': round(avg_solution_rating, 2) if avg_solution_rating else None,
            'avg_speech_rating': round(avg_speech_rating, 2) if avg_speech_rating else None,
            'solution_found_rate': round(solutions_found / sessions_with_feedback, 2) if sessions_with_feedback > 0 else None,
            'issue_resolved_rate': round(issues_resolved / sessions_with_feedback, 2) if sessions_with_feedback > 0 else None,
            'total_searches': total_searches,
            'zero_result_searches': zero_result_searches,
            'zero_result_rate': round(zero_result_searches / total_searches, 2) if total_searches > 0 else None,
            'avg_response_time_ms': round(avg_response_time, 0) if avg_response_time else None,
            'avg_searches_per_session': round(total_searches / total_sessions, 1) if total_sessions > 0 else None,
            'total_field_edits': total_field_edits,
            'suggestions_shown': suggestions_shown,
            'suggestions_clicked': suggestions_clicked,
            'suggestion_click_rate': round(suggestions_clicked / suggestions_shown, 2) if suggestions_shown > 0 else None,
            'avg_session_duration_seconds': round(avg_session_duration, 0) if avg_session_duration else None,
        }

    def _get_trends(
        self,
        db: Session,
        company_id: int,
        start_dt: datetime,
        end_dt: datetime,
    ) -> Dict[str, List]:
        """Get daily trends data."""
        # Group sessions by date
        session_trends = db.query(
            func.date(CallSession.start_time).label('date'),
            func.count(CallSession.id).label('sessions'),
        ).filter(
            CallSession.company_id == company_id,
            CallSession.start_time >= start_dt,
            CallSession.start_time <= end_dt,
        ).group_by(func.date(CallSession.start_time)).order_by('date').all()

        # Group searches by date
        search_trends = db.query(
            func.date(QueryLogs.timestamp).label('date'),
            func.count(QueryLogs.id).label('searches'),
        ).filter(
            QueryLogs.company_id == company_id,
            QueryLogs.timestamp >= start_dt,
            QueryLogs.timestamp <= end_dt,
        ).group_by(func.date(QueryLogs.timestamp)).order_by('date').all()

        # Group ratings by date
        rating_trends = db.query(
            func.date(SessionFeedback.created_at).label('date'),
            func.avg(SessionFeedback.solution_rating).label('avg_rating'),
        ).filter(
            SessionFeedback.company_id == company_id,
            SessionFeedback.created_at >= start_dt,
            SessionFeedback.created_at <= end_dt,
            SessionFeedback.solution_rating.isnot(None),
        ).group_by(func.date(SessionFeedback.created_at)).order_by('date').all()

        # Convert to lists
        session_dict = {str(row.date): row.sessions for row in session_trends}
        search_dict = {str(row.date): row.searches for row in search_trends}
        rating_dict = {str(row.date): round(float(row.avg_rating), 2) for row in rating_trends}

        # Generate date range
        dates = []
        current = start_dt.date()
        while current <= end_dt.date():
            dates.append(str(current))
            current += timedelta(days=1)

        return {
            'dates': dates,
            'sessions': [session_dict.get(d, 0) for d in dates],
            'searches': [search_dict.get(d, 0) for d in dates],
            'solution_rating_avg': [rating_dict.get(d, None) for d in dates],
        }

    def _get_by_user(
        self,
        db: Session,
        company_id: int,
        start_dt: datetime,
        end_dt: datetime,
    ) -> List[Dict[str, Any]]:
        """Get per-user statistics."""
        # Get session counts by user
        user_stats = db.query(
            User.id.label('user_id'),
            User.full_name.label('user_name'),
            func.count(CallSession.id).label('sessions'),
            func.avg(CallSession.duration_seconds).label('avg_duration'),
        ).join(
            CallSession, CallSession.agent_user_id == User.id
        ).filter(
            User.company_id == company_id,
            CallSession.start_time >= start_dt,
            CallSession.start_time <= end_dt,
        ).group_by(User.id, User.full_name).all()

        result = []
        for row in user_stats:
            # Get search count
            search_count = db.query(func.count(QueryLogs.id)).filter(
                QueryLogs.agent_user_id == row.user_id,
                QueryLogs.timestamp >= start_dt,
                QueryLogs.timestamp <= end_dt,
            ).scalar() or 0

            # Get feedback stats
            feedback = db.query(
                func.avg(SessionFeedback.solution_rating).label('avg_rating'),
                func.sum(case((SessionFeedback.issue_resolved == True, 1), else_=0)).label('resolved'),
                func.count(SessionFeedback.id).label('feedback_count'),
            ).filter(
                SessionFeedback.agent_user_id == row.user_id,
                SessionFeedback.created_at >= start_dt,
                SessionFeedback.created_at <= end_dt,
            ).first()

            # Get field edits
            edit_count = db.query(func.count(FieldEditLog.id)).filter(
                FieldEditLog.agent_user_id == row.user_id,
                FieldEditLog.edited_at >= start_dt,
                FieldEditLog.edited_at <= end_dt,
            ).scalar() or 0

            result.append({
                'user_id': row.user_id,
                'user_name': row.user_name or f'User {row.user_id}',
                'sessions': row.sessions,
                'searches': search_count,
                'avg_rating': round(float(feedback.avg_rating), 2) if feedback.avg_rating else None,
                'resolved_rate': round(feedback.resolved / feedback.feedback_count, 2) if feedback.feedback_count > 0 else None,
                'field_edits': edit_count,
                'avg_duration_seconds': round(float(row.avg_duration), 0) if row.avg_duration else None,
            })

        # Sort by sessions descending
        result.sort(key=lambda x: x['sessions'], reverse=True)
        return result

    def _get_top_edited_fields(
        self,
        db: Session,
        company_id: int,
        start_dt: datetime,
        end_dt: datetime,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get most frequently edited fields."""
        field_counts = db.query(
            FieldEditLog.field_slug,
            FieldEditLog.field_name,
            func.count(FieldEditLog.id).label('edit_count'),
        ).filter(
            FieldEditLog.company_id == company_id,
            FieldEditLog.edited_at >= start_dt,
            FieldEditLog.edited_at <= end_dt,
        ).group_by(
            FieldEditLog.field_slug,
            FieldEditLog.field_name,
        ).order_by(func.count(FieldEditLog.id).desc()).limit(limit).all()

        return [
            {
                'field_slug': row.field_slug,
                'field_name': row.field_name or row.field_slug,
                'edit_count': row.edit_count,
            }
            for row in field_counts
        ]

    def _get_top_sources(
        self,
        db: Session,
        company_id: int,
        start_dt: datetime,
        end_dt: datetime,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get most clicked knowledge base sources."""
        # This would need parsing of source_metadata JSON
        # For now, return placeholder
        return []

    def get_user_search_stats(
        self,
        user_id: int,
        company_id: int,
    ) -> Dict[str, Any]:
        """Get search statistics for a specific user."""
        with get_db_session() as db:
            today = date.today()
            week_ago = today - timedelta(days=7)
            month_ago = today - timedelta(days=30)

            # Total searches
            total = db.query(func.count(QueryLogs.id)).filter(
                QueryLogs.agent_user_id == user_id,
                QueryLogs.company_id == company_id,
            ).scalar() or 0

            # Today
            today_count = db.query(func.count(QueryLogs.id)).filter(
                QueryLogs.agent_user_id == user_id,
                QueryLogs.company_id == company_id,
                func.date(QueryLogs.timestamp) == today,
            ).scalar() or 0

            # This week
            week_count = db.query(func.count(QueryLogs.id)).filter(
                QueryLogs.agent_user_id == user_id,
                QueryLogs.company_id == company_id,
                QueryLogs.timestamp >= datetime.combine(week_ago, datetime.min.time()),
            ).scalar() or 0

            # This month
            month_count = db.query(func.count(QueryLogs.id)).filter(
                QueryLogs.agent_user_id == user_id,
                QueryLogs.company_id == company_id,
                QueryLogs.timestamp >= datetime.combine(month_ago, datetime.min.time()),
            ).scalar() or 0

            # Sessions count for average
            session_count = db.query(func.count(CallSession.id)).filter(
                CallSession.agent_user_id == user_id,
                CallSession.company_id == company_id,
            ).scalar() or 0

            return {
                'user_id': user_id,
                'total_searches': total,
                'searches_by_period': {
                    'today': today_count,
                    'this_week': week_count,
                    'this_month': month_count,
                },
                'avg_searches_per_session': round(total / session_count, 1) if session_count > 0 else None,
            }


# Singleton instance
_analytics_service: Optional[AnalyticsService] = None


def get_analytics_service() -> AnalyticsService:
    """Get the analytics service singleton."""
    global _analytics_service
    if _analytics_service is None:
        _analytics_service = AnalyticsService()
    return _analytics_service
