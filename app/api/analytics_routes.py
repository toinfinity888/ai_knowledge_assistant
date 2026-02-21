"""
Analytics API Routes

Provides endpoints for:
- Submitting session feedback (star ratings)
- Recording field edits
- Retrieving dashboard analytics
- User search statistics
"""
from flask import Blueprint, request, jsonify
from datetime import datetime

from app.middleware.auth_middleware import require_auth
from app.middleware.tenant_context import get_current_tenant
from app.services.analytics_service import get_analytics_service
from app.models.call_session import CallSession
from app.database.postgresql_session import get_db_session
from app.logging.logger import logger

analytics_bp = Blueprint('analytics', __name__, url_prefix='/api/v1/analytics')


@analytics_bp.route('/sessions/<session_id>/feedback', methods=['POST'])
@require_auth
def submit_feedback(session_id: str):
    """
    Submit post-session feedback.

    Request body:
    {
        "solution_rating": 4,           // 1-5 stars, optional
        "speech_recognition_rating": 5, // 1-5 stars, optional
        "solution_found": true,         // boolean, optional
        "issue_resolved": true,         // boolean, optional
        "comments": "..."               // optional text
    }

    Returns:
        201: Feedback recorded
        400: Invalid request
        404: Session not found
    """
    tenant = get_current_tenant()
    data = request.get_json() or {}

    # Validate ratings if provided
    solution_rating = data.get('solution_rating')
    speech_rating = data.get('speech_recognition_rating')

    if solution_rating is not None and (solution_rating < 1 or solution_rating > 5):
        return jsonify({'error': 'solution_rating must be between 1 and 5'}), 400

    if speech_rating is not None and (speech_rating < 1 or speech_rating > 5):
        return jsonify({'error': 'speech_recognition_rating must be between 1 and 5'}), 400

    # Find session
    with get_db_session() as db:
        # Try to find by session_id string first, then by id
        session = db.query(CallSession).filter(
            CallSession.session_id == session_id,
            CallSession.company_id == tenant.company_id,
        ).first()

        if not session:
            # Try by integer ID
            try:
                session = db.query(CallSession).filter(
                    CallSession.id == int(session_id),
                    CallSession.company_id == tenant.company_id,
                ).first()
            except ValueError:
                pass

        if not session:
            return jsonify({'error': 'Session not found'}), 404

        # Check if feedback already exists
        if session.feedback:
            return jsonify({'error': 'Feedback already submitted for this session'}), 400

        session_db_id = session.id
        session_company_id = session.company_id

    # Record feedback (outside the db context since service handles its own)
    analytics_service = get_analytics_service()
    feedback = analytics_service.record_feedback(
        session_id=session_db_id,
        company_id=tenant.company_id,
        agent_user_id=tenant.user_id,
        solution_rating=solution_rating,
        speech_recognition_rating=speech_rating,
        solution_found=data.get('solution_found'),
        issue_resolved=data.get('issue_resolved'),
        comments=data.get('comments'),
    )

    logger.info(f"Feedback submitted for session {session_id} by user {tenant.user_id}")

    return jsonify({
        'message': 'Feedback submitted',
        'feedback_id': feedback.id,
    }), 201


@analytics_bp.route('/sessions/<session_id>/field-edits', methods=['POST'])
@require_auth
def track_field_edits(session_id: str):
    """
    Record field edits made during a session.

    Request body:
    {
        "edits": [
            {
                "field_slug": "error_code",
                "field_name": "Error Code",
                "original_value": "E123",
                "edited_value": "E124"
            }
        ]
    }

    Returns:
        201: Edits recorded
        400: Invalid request
        404: Session not found
    """
    tenant = get_current_tenant()
    data = request.get_json() or {}

    edits = data.get('edits', [])
    if not edits:
        return jsonify({'error': 'No edits provided'}), 400

    # Validate edits
    for edit in edits:
        if not edit.get('field_slug'):
            return jsonify({'error': 'field_slug is required for each edit'}), 400

    # Find session
    with get_db_session() as db:
        session = db.query(CallSession).filter(
            CallSession.session_id == session_id,
            CallSession.company_id == tenant.company_id,
        ).first()

        if not session:
            try:
                session = db.query(CallSession).filter(
                    CallSession.id == int(session_id),
                    CallSession.company_id == tenant.company_id,
                ).first()
            except ValueError:
                pass

        if not session:
            return jsonify({'error': 'Session not found'}), 404

        session_db_id = session.id

    # Record field edits (outside db context since service handles its own)
    analytics_service = get_analytics_service()
    count = analytics_service.record_field_edits(
        session_id=session_db_id,
        company_id=tenant.company_id,
        agent_user_id=tenant.user_id,
        edits=edits,
    )

    logger.info(f"Recorded {count} field edits for session {session_id}")

    return jsonify({
        'message': 'Field edits recorded',
        'count': count,
    }), 201


@analytics_bp.route('/dashboard', methods=['GET'])
@require_auth
def get_dashboard():
    """
    Get aggregated analytics data for dashboard.

    Query params:
        - period: 'day', 'week', 'month', 'year' (default: 'week')
        - start_date: ISO date string (optional)
        - end_date: ISO date string (optional)
        - user_id: filter by specific user (optional)

    Returns:
        Dashboard data with summary, trends, by_user, and top_edited_fields
    """
    tenant = get_current_tenant()

    period = request.args.get('period', 'week')
    if period not in ['day', 'week', 'month', 'year']:
        return jsonify({'error': 'Invalid period. Must be day, week, month, or year'}), 400

    # Parse optional dates
    start_date = None
    end_date = None

    if request.args.get('start_date'):
        try:
            start_date = datetime.fromisoformat(request.args.get('start_date')).date()
        except ValueError:
            return jsonify({'error': 'Invalid start_date format. Use ISO format (YYYY-MM-DD)'}), 400

    if request.args.get('end_date'):
        try:
            end_date = datetime.fromisoformat(request.args.get('end_date')).date()
        except ValueError:
            return jsonify({'error': 'Invalid end_date format. Use ISO format (YYYY-MM-DD)'}), 400

    # Optional user filter
    user_id = None
    if request.args.get('user_id'):
        try:
            user_id = int(request.args.get('user_id'))
        except ValueError:
            return jsonify({'error': 'Invalid user_id'}), 400

    analytics_service = get_analytics_service()
    data = analytics_service.get_dashboard_data(
        company_id=tenant.company_id,
        period=period,
        start_date=start_date,
        end_date=end_date,
        user_id=user_id,
    )

    return jsonify(data), 200


@analytics_bp.route('/users/<int:user_id>/search-stats', methods=['GET'])
@require_auth
def get_user_search_stats(user_id: int):
    """
    Get search statistics for a specific user.

    Returns:
        User's search statistics
    """
    tenant = get_current_tenant()

    # Only allow viewing own stats or if admin
    if user_id != tenant.user_id and not tenant.is_admin():
        return jsonify({'error': 'Not authorized to view other user stats'}), 403

    analytics_service = get_analytics_service()
    stats = analytics_service.get_user_search_stats(
        user_id=user_id,
        company_id=tenant.company_id,
    )

    return jsonify(stats), 200


@analytics_bp.route('/my-stats', methods=['GET'])
@require_auth
def get_my_stats():
    """
    Get current user's search statistics.

    Returns:
        Current user's search statistics
    """
    tenant = get_current_tenant()

    analytics_service = get_analytics_service()
    stats = analytics_service.get_user_search_stats(
        user_id=tenant.user_id,
        company_id=tenant.company_id,
    )

    return jsonify(stats), 200
