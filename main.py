# Load environment variables from .env file FIRST (before any imports that need them)
from dotenv import load_dotenv
load_dotenv()

from app import create_app
from app.api.realtime_routes import realtime_bp, setup_websocket, broadcast_to_session
from app.demo.web_demo_routes import demo_bp, register_demo_websocket_routes
from app.init_realtime_system import initialize_realtime_system
from flask_sock import Sock
import os

# Create Flask app
app = create_app()

# Ensure secret key is set for sessions
if not app.secret_key or app.secret_key == 'dev-secret-key-change-in-production':
    app.secret_key = os.getenv('JWT_SECRET_KEY') or os.getenv('SECRET_KEY') or os.urandom(32).hex()
    print(f"✓ Secret key configured")

# Initialize WebSocket support
sock = Sock(app)

# Register authentication routes
try:
    from app.api.auth_routes import auth_bp
    app.register_blueprint(auth_bp)
    print("✓ Authentication routes registered")
except ImportError as e:
    print(f"⚠ Authentication routes not available: {e}")

# Register company management routes
try:
    from app.api.company_routes import company_bp
    app.register_blueprint(company_bp)
    print("✓ Company routes registered")
except ImportError as e:
    print(f"⚠ Company routes not available: {e}")

# Register super admin routes (platform administration)
try:
    from app.api.super_admin_routes import super_bp
    app.register_blueprint(super_bp)
    print("✓ Super admin routes registered (/api/v1/super/*)")
except ImportError as e:
    print(f"⚠ Super admin routes not available: {e}")

# Register admin routes (company-scoped administration)
try:
    from app.api.admin_routes import admin_bp
    app.register_blueprint(admin_bp)
    print("✓ Admin routes registered (/api/v1/admin/*)")
except ImportError as e:
    print(f"⚠ Admin routes not available: {e}")

# Register admin panel web routes
try:
    from app.frontend.routes_admin import admin_panel_bp
    app.register_blueprint(admin_panel_bp)
    print("✓ Admin panel routes registered (/admin/*)")
except ImportError as e:
    print(f"⚠ Admin panel routes not available: {e}")

# Register real-time API routes
app.register_blueprint(realtime_bp)

# Register demo routes
app.register_blueprint(demo_bp)

# Register demo WebSocket routes
register_demo_websocket_routes(sock)
print("✓ Demo WebSocket routes registered")

# Register Twilio routes
try:
    from app.api.twilio_routes import twilio_bp, register_websocket_routes
    app.register_blueprint(twilio_bp)
    register_websocket_routes(sock)
    print("✓ Twilio routes registered")
except ImportError as e:
    print(f"⚠ Twilio routes not available: {e}")

# Register configuration routes
try:
    from app.api.config_routes import config_bp
    app.register_blueprint(config_bp)
    print("✓ Configuration routes registered")
except ImportError as e:
    print(f"⚠ Configuration routes not available: {e}")

# Register configuration test routes and WebSocket
try:
    from app.api.config_test_routes import config_test_bp, register_config_websocket_routes
    app.register_blueprint(config_test_bp)
    register_config_websocket_routes(sock)
    print("✓ Configuration test routes registered")
except ImportError as e:
    print(f"⚠ Configuration test routes not available: {e}")

# Setup WebSocket routes
setup_websocket(sock)

# Initialize real-time system components
print("Initializing real-time support assistant system...")
components = initialize_realtime_system()
print("✓ System ready!")

if __name__ == "__main__":
    port = int(os.getenv('PORT', 8000))  # Changed default to 8000 for ngrok
    app.run(
        host='0.0.0.0',
        port=port,
        debug=True
    )
