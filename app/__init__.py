def create_app():
    from flask import Flask

    app = Flask(__name__)

    from app.frontend.routes import front
    app.register_blueprint(front)

    return app
