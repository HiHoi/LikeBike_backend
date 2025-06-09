from flask import Flask
from .routes import main as main_blueprint

def create_app(test_config=None):
    app = Flask(__name__)

    app.register_blueprint(main_blueprint)

    if test_config:
        app.config.update(test_config)

    return app
