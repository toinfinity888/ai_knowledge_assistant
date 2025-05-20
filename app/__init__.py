from flask import Flask

def create_app():
    app = Flask(__name__)

    from app.frontend.routes import front
    app.register_blueprint(front)
    
    return app
