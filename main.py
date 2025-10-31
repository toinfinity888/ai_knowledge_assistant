from app import create_app
from app.api.realtime_routes import realtime_bp, setup_websocket, broadcast_to_session
from app.demo.web_demo_routes import demo_bp
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

# Register Twilio routes
try:
    from app.api.twilio_routes import twilio_bp, register_websocket_routes
    app.register_blueprint(twilio_bp)
    register_websocket_routes(sock)
    print("✓ Twilio routes registered")
except ImportError as e:
    print(f"⚠ Twilio routes not available: {e}")

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