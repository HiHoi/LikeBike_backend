import os

from flask import Flask

from . import db
from .routes import main as main_blueprint
from .routes.bike_logs import bp as bike_logs_bp
from .routes.quizzes import bp as quizzes_bp


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)

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
    app.register_blueprint(bike_logs_bp)

    return app
