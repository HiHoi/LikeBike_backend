import os

from flask import Flask
from flask_cors import CORS

from . import db
from .routes import main as main_blueprint
from .routes.news import bp as news_bp
from .routes.bike_logs import bp as bike_logs_bp
from .routes.quizzes import bp as quizzes_bp
from .routes.users import bp as users_bp


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)

    CORS(app, resources={
        r"/api/*": {
            "origins": ["http://localhost:3000", "http://127.0.0.1:3000", "https://port-0-likebike-mc4iz1js1403f457.sel5.cloudtype.app"],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization", "X-Admin"]
        }
    })

    # PostgreSQL 연결 설정
    app.config.from_mapping(
        DATABASE_URL=os.environ.get("DATABASE_URL", "postgresql://localhost/likebike"),
    )

    if test_config:
        app.config.update(test_config)

    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:
        pass

    db.init_app(app)

    app.register_blueprint(main_blueprint)
    app.register_blueprint(quizzes_bp)
    app.register_blueprint(news_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(bike_logs_bp)

    return app
