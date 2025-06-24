import logging
import os
import time

from flask import Flask, g, request
from flask_cors import CORS

from . import db
from .routes import main as main_blueprint
from .routes.bike_logs import bp as bike_logs_bp
from .routes.news import bp as news_bp
from .routes.quizzes import bp as quizzes_bp
from .routes.users import bp as users_bp


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)

    # basic logging setup
    if not app.logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)

    @app.before_request
    def _log_request() -> None:
        g._start_time = time.perf_counter()
        app.logger.info("Received %s %s", request.method, request.path)

    @app.after_request
    def _log_response(response):
        duration = time.perf_counter() - g.get("_start_time", time.perf_counter())
        level = logging.WARNING if duration > 0.2 else logging.INFO
        app.logger.log(
            level,
            "Handled %s %s -> %s in %.3fs",
            request.method,
            request.path,
            response.status_code,
            duration,
        )
        return response

    CORS(
        app,
        resources={
            r"/*": {  # 모든 경로 허용
                "origins": [
                    "http://localhost:3000",
                    "http://127.0.0.1:3000",
                    "https://port-0-likebike-mc4iz1js1403f457.sel5.cloudtype.app",
                ],
                "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                "allow_headers": ["Content-Type", "Authorization", "X-Admin"],
            }
        },
    )

    # 환경별 설정
    if test_config:
        app.config.update(test_config)
    elif os.environ.get("FLASK_ENV") == "production":
        # 프로덕션: 환경변수 필수
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            raise ValueError(
                "DATABASE_URL environment variable is required in production"
            )
        app.config.from_mapping(DATABASE_URL=database_url)
    else:
        # 개발환경: 기본값 사용
        app.config.from_mapping(
            DATABASE_URL=os.environ.get(
                "DATABASE_URL", "postgresql://localhost/likebike"
            ),
        )

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
