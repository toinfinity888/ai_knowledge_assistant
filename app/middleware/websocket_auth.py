"""
WebSocket Authentication

Handles authentication for WebSocket connections.
WebSocket connections can authenticate via:
1. Query parameter: ?token=<jwt_token>
2. First message: {"type": "auth", "token": "<jwt_token>"}
"""
from functools import wraps
from typing import Callable, Optional

from app.services.auth_service import get_auth_service
from app.middleware.tenant_context import TenantContext, set_tenant_context, clear_tenant_context
from app.logging.logger import logger


def authenticate_websocket(token: str) -> Optional[TenantContext]:
    """
    Authenticate a WebSocket connection using a JWT token.

    Args:
        token: JWT access token

    Returns:
        TenantContext if valid, None otherwise
    """
    if not token:
        logger.debug("WebSocket auth: No token provided")
        return None

    auth_service = get_auth_service()
    payload = auth_service.verify_access_token(token)

    if not payload:
        logger.debug("WebSocket auth: Invalid token")
        return None

    context = TenantContext(
        user_id=int(payload['sub']),
        email=payload['email'],
        company_id=payload['company_id'],
        company_slug=payload.get('company_slug', ''),
        role=payload['role'],
    )

    logger.debug(f"WebSocket auth: Authenticated user {context.user_id} for company {context.company_id}")
    return context


def authenticate_websocket_from_request(ws) -> Optional[TenantContext]:
    """
    Authenticate WebSocket from request query parameters.

    Args:
        ws: Flask-Sock WebSocket object

    Returns:
        TenantContext if valid, None otherwise
    """
    # Get token from query parameters
    from flask import request
    token = request.args.get('token')

    if token:
        return authenticate_websocket(token)

    return None


def websocket_auth_required(f: Callable) -> Callable:
    """
    Decorator for WebSocket handlers that require authentication.

    The decorated function will receive the TenantContext as first argument
    after the websocket object.

    Usage:
        @sock.route('/ws/protected')
        @websocket_auth_required
        def protected_ws(ws, tenant_context):
            # tenant_context is guaranteed to be valid
            company_id = tenant_context.company_id
            while True:
                data = ws.receive()
                ws.send(f"Received: {data}")
    """
    @wraps(f)
    def decorated_function(ws, *args, **kwargs):
        from flask import request

        # Try to authenticate from query parameter
        token = request.args.get('token')
        context = authenticate_websocket(token) if token else None

        if not context:
            # Close connection with error
            try:
                ws.send('{"error": "Authentication required", "code": 401}')
                ws.close()
            except Exception:
                pass
            logger.warning("WebSocket connection rejected: authentication required")
            return

        # Set tenant context
        set_tenant_context(context)

        try:
            # Call handler with tenant context
            return f(ws, context, *args, **kwargs)
        finally:
            clear_tenant_context()

    return decorated_function


def websocket_auth_optional(f: Callable) -> Callable:
    """
    Decorator for WebSocket handlers where authentication is optional.

    The decorated function will receive TenantContext or None as first argument.

    Usage:
        @sock.route('/ws/public')
        @websocket_auth_optional
        def public_ws(ws, tenant_context):
            if tenant_context:
                ws.send(f"Hello, {tenant_context.email}")
            else:
                ws.send("Hello, guest")
    """
    @wraps(f)
    def decorated_function(ws, *args, **kwargs):
        from flask import request

        # Try to authenticate from query parameter
        token = request.args.get('token')
        context = authenticate_websocket(token) if token else None

        if context:
            set_tenant_context(context)

        try:
            return f(ws, context, *args, **kwargs)
        finally:
            if context:
                clear_tenant_context()

    return decorated_function


class WebSocketAuthenticator:
    """
    Helper class for WebSocket handlers that need to authenticate
    after receiving the first message.

    Usage:
        @sock.route('/ws/stream')
        def stream_ws(ws):
            authenticator = WebSocketAuthenticator(ws)

            # Authenticate from first message
            context = authenticator.authenticate_from_message()
            if not context:
                return  # Connection closed by authenticator

            # Now handle authenticated messages
            while True:
                data = ws.receive()
                ws.send(f"Echo: {data}")
    """

    def __init__(self, ws):
        self.ws = ws
        self.context: Optional[TenantContext] = None

    def authenticate_from_message(self, timeout: int = 30) -> Optional[TenantContext]:
        """
        Wait for an authentication message and validate it.

        Expected message format:
        {"type": "auth", "token": "<jwt_token>"}

        Args:
            timeout: Timeout in seconds for receiving auth message

        Returns:
            TenantContext if authenticated, None otherwise
        """
        import json

        try:
            # Receive first message
            message = self.ws.receive(timeout=timeout)

            if not message:
                self._reject("No authentication message received")
                return None

            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                self._reject("Invalid JSON in authentication message")
                return None

            if data.get('type') != 'auth':
                self._reject("First message must be authentication")
                return None

            token = data.get('token')
            if not token:
                self._reject("Missing token in authentication message")
                return None

            context = authenticate_websocket(token)
            if not context:
                self._reject("Invalid authentication token")
                return None

            # Set tenant context
            set_tenant_context(context)
            self.context = context

            # Send success response
            self.ws.send(json.dumps({
                "type": "auth_success",
                "user_id": context.user_id,
                "company_id": context.company_id
            }))

            return context

        except Exception as e:
            logger.error(f"WebSocket authentication error: {e}")
            self._reject(f"Authentication error: {str(e)}")
            return None

    def _reject(self, message: str):
        """Send rejection message and close connection"""
        import json
        try:
            self.ws.send(json.dumps({
                "type": "auth_error",
                "error": message
            }))
            self.ws.close()
        except Exception:
            pass
        logger.warning(f"WebSocket auth rejected: {message}")

    def cleanup(self):
        """Clear tenant context - call when done with the connection"""
        if self.context:
            clear_tenant_context()
            self.context = None
