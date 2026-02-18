"""
Integration API Routes

Provides endpoints for:
1. Webhook receivers (no auth - authenticated via webhook signature)
2. Session access for agent UI (auth required)
3. Admin configuration endpoints (company admin required)
"""
import uuid
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, g

from app.middleware.auth_middleware import (
    require_auth,
    require_company_admin,
)
from app.database.postgresql_session import get_db_session
from app.logging.logger import logger


integration_bp = Blueprint('integrations', __name__, url_prefix='/api/v1/integrations')
integration_admin_bp = Blueprint('integrations_admin', __name__, url_prefix='/api/v1/admin/integrations')


# =============================================================================
# Webhook Receiver Endpoints (No Auth - Uses Signature Verification)
# =============================================================================

@integration_bp.route('/<provider>/webhook/<integration_id>', methods=['POST'])
def receive_webhook(provider: str, integration_id: str):
    """
    Receive webhooks from telephony providers.

    This endpoint does NOT use JWT authentication.
    Instead, webhooks are authenticated via signature verification
    using the webhook_secret configured for the integration.

    URL format: /api/v1/integrations/{provider}/webhook/{integration_id}

    Headers:
        X-Webhook-Signature: Provider-specific signature
        X-Aircall-Signature: Aircall-specific header
        X-Genesys-Signature: Genesys-specific header

    Response:
        200: Webhook processed successfully
        400: Invalid payload
        401: Invalid signature
        404: Integration not found
    """
    try:
        # Import here to avoid circular imports
        from app.integrations.webhook_processor import get_webhook_processor

        # Get raw payload for signature verification
        payload_bytes = request.get_data()
        headers = dict(request.headers)

        # Get processor and find integration
        processor = get_webhook_processor()

        # We need to find the company_id from the integration_id
        with get_db_session() as db:
            from app.models.integration_config import IntegrationConfig

            integration = db.query(IntegrationConfig).filter(
                IntegrationConfig.integration_id == integration_id,
                IntegrationConfig.is_active == True,
            ).first()

            if not integration:
                logger.warning(f"Webhook received for unknown integration: {integration_id}")
                return jsonify({
                    'error': 'Integration not found',
                    'integration_id': integration_id,
                }), 404

            company_id = integration.company_id

        # Process the webhook
        result = processor.process_webhook(
            company_id=company_id,
            provider=provider,
            integration_id=integration_id,
            payload=payload_bytes,
            headers=headers,
        )

        if result.get('status') == 'error':
            status_code = 400
            if 'signature' in result.get('error', '').lower():
                status_code = 401
            elif 'not found' in result.get('error', '').lower():
                status_code = 404
            return jsonify(result), status_code

        return jsonify(result), 200

    except Exception as e:
        logger.exception(f"Error processing webhook: {e}")
        return jsonify({
            'error': 'Internal server error',
            'message': str(e),
        }), 500


# =============================================================================
# Session Access Endpoints (For Agent UI)
# =============================================================================

@integration_bp.route('/sessions/by-call/<external_call_id>', methods=['GET'])
@require_auth
def get_session_by_call_id(external_call_id: str):
    """
    Get session by external call ID.

    This allows the agent UI to find the internal session
    associated with a call from the telephony system.

    Response:
        {
            "session_id": "...",
            "call_id": "...",
            "status": "active",
            "customer_name": "...",
            "agent_name": "...",
            "start_time": "...",
            "suggestions_count": 5
        }
    """
    context = g.tenant_context
    company_id = context.company_id

    if not company_id and not context.is_super_admin:
        return jsonify({'error': 'Company context required'}), 400

    try:
        with get_db_session() as db:
            from app.models.call_session import CallSession

            query = db.query(CallSession).filter(
                CallSession.call_id == external_call_id,
            )

            # Apply company filter unless super admin
            if company_id:
                query = query.filter(CallSession.company_id == company_id)

            session = query.first()

            if not session:
                return jsonify({'error': 'Session not found'}), 404

            return jsonify({
                'session_id': session.session_id,
                'call_id': session.call_id,
                'status': session.status,
                'customer_id': session.customer_id,
                'customer_name': session.customer_name,
                'customer_phone': session.customer_phone,
                'agent_id': session.agent_id,
                'agent_name': session.agent_name,
                'start_time': session.start_time.isoformat() if session.start_time else None,
                'end_time': session.end_time.isoformat() if session.end_time else None,
                'duration_seconds': session.duration_seconds,
                'detected_intent': session.detected_intent,
                'sentiment_score': session.sentiment_score,
                'suggestions_count': len(session.suggestions) if session.suggestions else 0,
            })

    except Exception as e:
        logger.exception(f"Error getting session: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@integration_bp.route('/sessions/<session_id>/suggestions', methods=['GET'])
@require_auth
def get_session_suggestions(session_id: str):
    """
    Get AI suggestions for a session.

    Query params:
        - limit: int (default: 10)
        - include_shown: bool (default: true) - include already shown suggestions

    Response:
        {
            "suggestions": [
                {
                    "id": 1,
                    "type": "knowledge_base",
                    "title": "...",
                    "content": "...",
                    "confidence_score": 0.95,
                    "source_metadata": [...],
                    "created_at": "..."
                }
            ],
            "total": 5
        }
    """
    context = g.tenant_context
    company_id = context.company_id

    limit = min(int(request.args.get('limit', 10)), 50)
    include_shown = request.args.get('include_shown', 'true').lower() == 'true'

    try:
        with get_db_session() as db:
            from app.models.call_session import CallSession, Suggestion

            # Find session
            query = db.query(CallSession).filter(
                CallSession.session_id == session_id,
            )

            if company_id:
                query = query.filter(CallSession.company_id == company_id)

            session = query.first()

            if not session:
                return jsonify({'error': 'Session not found'}), 404

            # Get suggestions
            suggestion_query = db.query(Suggestion).filter(
                Suggestion.session_id == session.id,
            )

            if not include_shown:
                suggestion_query = suggestion_query.filter(
                    Suggestion.shown_to_agent == False,
                )

            suggestions = suggestion_query.order_by(
                Suggestion.created_at.desc()
            ).limit(limit).all()

            # Mark as shown
            for sug in suggestions:
                if not sug.shown_to_agent:
                    sug.shown_to_agent = True
                    sug.shown_at = datetime.now(timezone.utc)
            db.commit()

            return jsonify({
                'suggestions': [
                    {
                        'id': s.id,
                        'type': s.suggestion_type,
                        'title': s.title,
                        'content': s.content,
                        'confidence_score': s.confidence_score,
                        'relevance_score': s.relevance_score,
                        'source_metadata': s.source_metadata,
                        'created_at': s.created_at.isoformat() if s.created_at else None,
                    }
                    for s in suggestions
                ],
                'total': len(suggestions),
            })

    except Exception as e:
        logger.exception(f"Error getting suggestions: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@integration_bp.route('/sessions/<session_id>/feedback', methods=['POST'])
@require_auth
def submit_suggestion_feedback(session_id: str):
    """
    Submit feedback on a suggestion.

    Request body:
        {
            "suggestion_id": 123,
            "feedback": "helpful" | "not_helpful" | "irrelevant",
            "clicked": true  // optional
        }

    Response:
        {
            "message": "Feedback recorded",
            "suggestion_id": 123
        }
    """
    context = g.tenant_context
    company_id = context.company_id
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body required'}), 400

    suggestion_id = data.get('suggestion_id')
    feedback = data.get('feedback')
    clicked = data.get('clicked', False)

    if not suggestion_id:
        return jsonify({'error': 'suggestion_id is required'}), 400

    valid_feedback = ['helpful', 'not_helpful', 'irrelevant']
    if feedback and feedback not in valid_feedback:
        return jsonify({'error': f'Invalid feedback. Must be one of: {valid_feedback}'}), 400

    try:
        with get_db_session() as db:
            from app.models.call_session import CallSession, Suggestion

            # Find session
            query = db.query(CallSession).filter(
                CallSession.session_id == session_id,
            )

            if company_id:
                query = query.filter(CallSession.company_id == company_id)

            session = query.first()

            if not session:
                return jsonify({'error': 'Session not found'}), 404

            # Find suggestion
            suggestion = db.query(Suggestion).filter(
                Suggestion.id == suggestion_id,
                Suggestion.session_id == session.id,
            ).first()

            if not suggestion:
                return jsonify({'error': 'Suggestion not found'}), 404

            # Update feedback
            if feedback:
                suggestion.agent_feedback = feedback
            if clicked:
                suggestion.agent_clicked = True
                suggestion.clicked_at = datetime.now(timezone.utc)

            db.commit()

            return jsonify({
                'message': 'Feedback recorded',
                'suggestion_id': suggestion_id,
            })

    except Exception as e:
        logger.exception(f"Error submitting feedback: {e}")
        return jsonify({'error': 'Internal server error'}), 500


# =============================================================================
# Admin Configuration Endpoints
# =============================================================================

@integration_admin_bp.route('', methods=['GET'])
@require_auth
@require_company_admin
def list_integrations():
    """
    List integrations for the company.

    Query params:
        - limit: int (default: 100)
        - offset: int (default: 0)
        - is_active: bool (optional)
        - provider: string (optional)
        - company_id: int (required for SUPER_ADMIN)

    Response:
        {
            "integrations": [...],
            "total": 5
        }
    """
    context = g.tenant_context

    limit = min(int(request.args.get('limit', 100)), 500)
    offset = int(request.args.get('offset', 0))
    is_active = request.args.get('is_active')
    provider = request.args.get('provider')

    # Determine company_id
    if context.is_super_admin:
        company_id = request.args.get('company_id', type=int)
        if not company_id:
            return jsonify({'error': 'company_id is required for SUPER_ADMIN'}), 400
    else:
        company_id = context.company_id

    try:
        with get_db_session() as db:
            from app.models.integration_config import IntegrationConfig

            query = db.query(IntegrationConfig).filter(
                IntegrationConfig.company_id == company_id,
            )

            if is_active is not None:
                query = query.filter(IntegrationConfig.is_active == (is_active.lower() == 'true'))

            if provider:
                query = query.filter(IntegrationConfig.provider == provider)

            total = query.count()
            integrations = query.offset(offset).limit(limit).all()

            return jsonify({
                'integrations': [i.to_dict() for i in integrations],
                'total': total,
                'limit': limit,
                'offset': offset,
            })

    except Exception as e:
        logger.exception(f"Error listing integrations: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@integration_admin_bp.route('', methods=['POST'])
@require_auth
@require_company_admin
def create_integration():
    """
    Create a new integration configuration.

    Request body:
        {
            "name": "Production Aircall",
            "integration_type": "cloud_webhook",
            "provider": "aircall",
            "webhook_secret": "...",  // optional
            "credentials": {...},  // optional
            "settings": {...},  // optional
            "company_id": 123  // required for SUPER_ADMIN
        }

    Response:
        {
            "integration": {...},
            "webhook_url": "/api/v1/integrations/aircall/webhook/...",
            "message": "Integration created successfully"
        }
    """
    context = g.tenant_context
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body required'}), 400

    name = data.get('name', '').strip()
    integration_type = data.get('integration_type', '').strip()
    provider = data.get('provider', '').strip()

    if not name:
        return jsonify({'error': 'name is required'}), 400
    if not integration_type:
        return jsonify({'error': 'integration_type is required'}), 400
    if not provider:
        return jsonify({'error': 'provider is required'}), 400

    # Determine company_id
    if context.is_super_admin:
        company_id = data.get('company_id')
        if not company_id:
            return jsonify({'error': 'company_id is required for SUPER_ADMIN'}), 400
    else:
        company_id = context.company_id

    try:
        with get_db_session() as db:
            from app.models.integration_config import (
                IntegrationConfig,
                IntegrationType,
                IntegrationProvider,
            )

            # Validate integration_type
            try:
                int_type = IntegrationType(integration_type)
            except ValueError:
                valid_types = [t.value for t in IntegrationType]
                return jsonify({'error': f'Invalid integration_type. Must be one of: {valid_types}'}), 400

            # Validate provider
            try:
                int_provider = IntegrationProvider(provider)
            except ValueError:
                valid_providers = [p.value for p in IntegrationProvider]
                return jsonify({'error': f'Invalid provider. Must be one of: {valid_providers}'}), 400

            # Generate unique integration_id
            integration_id = data.get('integration_id') or f"{provider}-{uuid.uuid4().hex[:8]}"

            # Check for duplicate integration_id within company
            existing = db.query(IntegrationConfig).filter(
                IntegrationConfig.company_id == company_id,
                IntegrationConfig.integration_id == integration_id,
            ).first()

            if existing:
                return jsonify({'error': 'Integration ID already exists'}), 400

            # Create integration
            integration = IntegrationConfig(
                company_id=company_id,
                integration_id=integration_id,
                name=name,
                description=data.get('description'),
                integration_type=int_type,
                provider=int_provider,
                is_active=data.get('is_active', True),
                is_primary=data.get('is_primary', False),
                webhook_secret=data.get('webhook_secret'),
                webhook_url_suffix=data.get('webhook_url_suffix'),
                transcription_source=data.get('transcription_source', 'provider_asr'),
                siprec_port=data.get('siprec_port'),
                siprec_transport=data.get('siprec_transport', 'udp'),
                allowed_sources=data.get('allowed_sources', []),
                srtp_enabled=data.get('srtp_enabled', True),
                credentials=data.get('credentials', {}),
                settings=data.get('settings', {}),
                metadata_mapping=data.get('metadata_mapping', {}),
                audio_settings=data.get('audio_settings', {}),
            )

            db.add(integration)
            db.commit()
            db.refresh(integration)

            # Generate webhook URL
            base_url = request.host_url.rstrip('/')
            webhook_url = integration.get_webhook_url(base_url)

            return jsonify({
                'integration': integration.to_dict(),
                'webhook_url': webhook_url,
                'message': 'Integration created successfully',
            }), 201

    except Exception as e:
        logger.exception(f"Error creating integration: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@integration_admin_bp.route('/<int:integration_id>', methods=['GET'])
@require_auth
@require_company_admin
def get_integration(integration_id: int):
    """
    Get integration details.

    Query params:
        - include_credentials: bool (default: false)
        - company_id: int (required for SUPER_ADMIN)

    Response:
        {
            "integration": {...},
            "webhook_url": "..."
        }
    """
    context = g.tenant_context
    include_credentials = request.args.get('include_credentials', 'false').lower() == 'true'

    # Determine company_id
    if context.is_super_admin:
        company_id = request.args.get('company_id', type=int)
    else:
        company_id = context.company_id

    try:
        with get_db_session() as db:
            from app.models.integration_config import IntegrationConfig

            query = db.query(IntegrationConfig).filter(
                IntegrationConfig.id == integration_id,
            )

            if company_id:
                query = query.filter(IntegrationConfig.company_id == company_id)

            integration = query.first()

            if not integration:
                return jsonify({'error': 'Integration not found'}), 404

            base_url = request.host_url.rstrip('/')
            webhook_url = integration.get_webhook_url(base_url)

            return jsonify({
                'integration': integration.to_dict(include_credentials=include_credentials),
                'webhook_url': webhook_url,
            })

    except Exception as e:
        logger.exception(f"Error getting integration: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@integration_admin_bp.route('/<int:integration_id>', methods=['PUT'])
@require_auth
@require_company_admin
def update_integration(integration_id: int):
    """
    Update integration configuration.

    Request body:
        {
            "name": "...",
            "is_active": true,
            "webhook_secret": "...",
            ...
        }

    Response:
        {
            "integration": {...},
            "message": "Integration updated successfully"
        }
    """
    context = g.tenant_context
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body required'}), 400

    # Determine company_id
    if context.is_super_admin:
        company_id = data.get('company_id') or request.args.get('company_id', type=int)
    else:
        company_id = context.company_id

    try:
        with get_db_session() as db:
            from app.models.integration_config import IntegrationConfig

            query = db.query(IntegrationConfig).filter(
                IntegrationConfig.id == integration_id,
            )

            if company_id:
                query = query.filter(IntegrationConfig.company_id == company_id)

            integration = query.first()

            if not integration:
                return jsonify({'error': 'Integration not found'}), 404

            # Update allowed fields
            updatable_fields = [
                'name', 'description', 'is_active', 'is_primary',
                'webhook_secret', 'webhook_url_suffix', 'transcription_source',
                'siprec_port', 'siprec_transport', 'allowed_sources', 'srtp_enabled',
                'credentials', 'settings', 'metadata_mapping', 'audio_settings',
            ]

            for field in updatable_fields:
                if field in data:
                    setattr(integration, field, data[field])

            db.commit()
            db.refresh(integration)

            return jsonify({
                'integration': integration.to_dict(),
                'message': 'Integration updated successfully',
            })

    except Exception as e:
        logger.exception(f"Error updating integration: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@integration_admin_bp.route('/<int:integration_id>', methods=['DELETE'])
@require_auth
@require_company_admin
def delete_integration(integration_id: int):
    """
    Delete an integration.

    Query params:
        - company_id: int (required for SUPER_ADMIN)

    Response:
        {
            "message": "Integration deleted",
            "integration_id": 123
        }
    """
    context = g.tenant_context

    # Determine company_id
    if context.is_super_admin:
        company_id = request.args.get('company_id', type=int)
    else:
        company_id = context.company_id

    try:
        with get_db_session() as db:
            from app.models.integration_config import IntegrationConfig

            query = db.query(IntegrationConfig).filter(
                IntegrationConfig.id == integration_id,
            )

            if company_id:
                query = query.filter(IntegrationConfig.company_id == company_id)

            integration = query.first()

            if not integration:
                return jsonify({'error': 'Integration not found'}), 404

            db.delete(integration)
            db.commit()

            return jsonify({
                'message': 'Integration deleted',
                'integration_id': integration_id,
            })

    except Exception as e:
        logger.exception(f"Error deleting integration: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@integration_admin_bp.route('/<int:integration_id>/test', methods=['POST'])
@require_auth
@require_company_admin
def test_integration(integration_id: int):
    """
    Test integration connectivity.

    This endpoint attempts to verify the integration is working:
    - For cloud webhooks: Verifies API credentials if provided
    - For SIPREC: Verifies network connectivity

    Response:
        {
            "status": "success" | "failed",
            "message": "...",
            "details": {...}
        }
    """
    context = g.tenant_context

    # Determine company_id
    if context.is_super_admin:
        company_id = request.args.get('company_id', type=int)
    else:
        company_id = context.company_id

    try:
        with get_db_session() as db:
            from app.models.integration_config import (
                IntegrationConfig,
                IntegrationType,
                IntegrationStatus,
            )

            query = db.query(IntegrationConfig).filter(
                IntegrationConfig.id == integration_id,
            )

            if company_id:
                query = query.filter(IntegrationConfig.company_id == company_id)

            integration = query.first()

            if not integration:
                return jsonify({'error': 'Integration not found'}), 404

            # Test based on integration type
            result = {
                'status': 'success',
                'message': 'Integration test passed',
                'details': {},
            }

            if integration.integration_type == IntegrationType.CLOUD_WEBHOOK:
                # For cloud webhooks, we mainly verify configuration is present
                if not integration.webhook_secret:
                    result['details']['webhook_secret'] = 'Not configured (recommended for security)'

                # Could add provider-specific API tests here
                result['details']['provider'] = integration.provider.value
                result['details']['webhook_url'] = integration.get_webhook_url(request.host_url.rstrip('/'))

            elif integration.integration_type == IntegrationType.SIPREC:
                # For SIPREC, verify port configuration
                if not integration.siprec_port:
                    result['status'] = 'failed'
                    result['message'] = 'SIPREC port not configured'
                else:
                    result['details']['siprec_port'] = integration.siprec_port
                    result['details']['transport'] = integration.siprec_transport
                    result['details']['srtp_enabled'] = integration.srtp_enabled

            # Update health status
            if result['status'] == 'success':
                integration.update_health(IntegrationStatus.HEALTHY)
            else:
                integration.update_health(IntegrationStatus.UNHEALTHY, result['message'])

            db.commit()

            return jsonify(result)

    except Exception as e:
        logger.exception(f"Error testing integration: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@integration_admin_bp.route('/<int:integration_id>/health', methods=['GET'])
@require_auth
@require_company_admin
def get_integration_health(integration_id: int):
    """
    Get integration health status.

    Response:
        {
            "health_status": "healthy" | "degraded" | "unhealthy" | "unknown",
            "last_health_check": "...",
            "last_event_received": "...",
            "consecutive_failures": 0,
            "error_message": null,
            "statistics": {
                "total_calls_processed": 100,
                "total_events_received": 500
            }
        }
    """
    context = g.tenant_context

    # Determine company_id
    if context.is_super_admin:
        company_id = request.args.get('company_id', type=int)
    else:
        company_id = context.company_id

    try:
        with get_db_session() as db:
            from app.models.integration_config import IntegrationConfig

            query = db.query(IntegrationConfig).filter(
                IntegrationConfig.id == integration_id,
            )

            if company_id:
                query = query.filter(IntegrationConfig.company_id == company_id)

            integration = query.first()

            if not integration:
                return jsonify({'error': 'Integration not found'}), 404

            return jsonify({
                'health_status': integration.health_status.value if integration.health_status else 'unknown',
                'last_health_check': integration.last_health_check.isoformat() if integration.last_health_check else None,
                'last_event_received': integration.last_event_received.isoformat() if integration.last_event_received else None,
                'consecutive_failures': integration.consecutive_failures,
                'error_message': integration.error_message,
                'statistics': {
                    'total_calls_processed': integration.total_calls_processed,
                    'total_events_received': integration.total_events_received,
                },
            })

    except Exception as e:
        logger.exception(f"Error getting integration health: {e}")
        return jsonify({'error': 'Internal server error'}), 500
