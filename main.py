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

# Setup WebSocket routes
setup_websocket(sock)

# Initialize real-time system components
print("Initializing real-time support assistant system...")
components = initialize_realtime_system()
print("✓ System ready!")

if __name__ == "__main__":
    port = int(os.getenv('PORT', 8080))
    app.run(
        host='0.0.0.0',
        port=port,
        debug=True
    )