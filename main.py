from app import create_app
from app.api.realtime_routes import realtime_bp, setup_websocket, broadcast_to_session
from app.demo.web_demo_routes import demo_bp, register_demo_websocket_routes
from app.init_realtime_system import initialize_realtime_system
from flask_sock import Sock
import os

# Create Flask app
app = create_app()

# Initialize WebSocket support
sock = Sock(app)

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