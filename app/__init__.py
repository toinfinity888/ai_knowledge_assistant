def create_app():
    import os
    from flask import Flask

    app = Flask(__name__)

    # Configure secret key for sessions
    app.secret_key = os.getenv('SECRET_KEY', os.getenv('JWT_SECRET_KEY', 'dev-secret-key-change-in-production'))

    from app.frontend.routes import front
    app.register_blueprint(front)

    return app
