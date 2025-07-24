import logging
import os
import time

try:  # python-dotenv may not be installed in some test envs
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - fallback when dependency missing

    def load_dotenv():
        """Fallback no-op when python-dotenv is unavailable."""
        pass


try:
    from flasgger import Swagger
except Exception:  # pragma: no cover - fallback when flasgger is missing

    class Swagger:  # type: ignore[override]
        def __init__(self, *_, **__):
            pass


from flask import Flask, g, request
from flask_cors import CORS

from . import db
from .routes import main as main_blueprint
from .routes.bike_logs import bp as bike_logs_bp
from .routes.community import bp as community_bp
from .routes.news import bp as news_bp
from .routes.quizzes import bp as quizzes_bp
from .routes.recommendations import bp as recommendations_bp
from .routes.rewards import bp as rewards_bp
from .routes.storage import bp as storage_bp
from .routes.users import bp as users_bp

load_dotenv()


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
                    "http://localhost:3001",
                    "http://127.0.0.1:3000",
                    "http://127.0.0.1:3001",
                    "https://likebike-admin.vercel.app/",
                    "https://port-0-likebike-mc4iz1js1403f457.sel5.cloudtype.app",
                    "https://like-bike-front.vercel.app",
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
    elif os.environ.get("FLASK_ENV") == "firebase_studio":
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

    # 스키마 초기화 개선 - RealDictCursor 호환
    def ensure_schema():
        try:
            from .db import get_db, init_db

            print("Checking database schema...")
            db_conn = get_db()

            with db_conn.cursor() as cur:
                # 여러 테이블 확인
                tables_to_check = [
                    "users",
                    "quizzes",
                    "news",
                    "bike_logs",
                    "community_posts",
                ]
                missing_tables = []

                for table in tables_to_check:
                    cur.execute(
                        """
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_name = %s
                        )
                    """,
                        (table,),
                    )
                    result = cur.fetchone()

                    # RealDictCursor와 일반 커서 모두 호환
                    if isinstance(result, dict):
                        table_exists = result.get("exists", False)
                    else:
                        table_exists = result[0] if result else False

                    if not table_exists:
                        missing_tables.append(table)

                if missing_tables:
                    print(f"Missing tables: {missing_tables}")
                    print("Initializing database schema...")
                    init_db()
                    print("Database schema initialized successfully")
                else:
                    print("Database schema is up to date")
        except Exception as e:
            print(f"Schema initialization failed: {e}")
            # 스키마 초기화 실패 시에도 애플리케이션은 계속 실행
            import traceback

            traceback.print_exc()

    # Flask 2.2+ 호환 방식으로 첫 요청시 스키마 확인
    schema_initialized = False

    @app.before_request
    def check_schema_once():
        nonlocal schema_initialized
        if not schema_initialized and not test_config:
            schema_initialized = True
            ensure_schema()

    app.register_blueprint(main_blueprint)
    app.register_blueprint(quizzes_bp)
    app.register_blueprint(news_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(bike_logs_bp)
    app.register_blueprint(community_bp)
    app.register_blueprint(storage_bp)
    app.register_blueprint(recommendations_bp)
    app.register_blueprint(rewards_bp)

    # Swagger 설정
    swagger_config = {
        "headers": [],
        "specs": [
            {
                "endpoint": "apispec",
                "route": "/apispec.json",
                "rule_filter": lambda rule: True,
                "model_filter": lambda tag: True,
            }
        ],
        "static_url_path": "/flasgger_static",
        "swagger_ui": True,
        "specs_route": "/apidocs/",
        "title": "LikeBike API",
        "description": "자전거 이용 활성화를 위한 게이미피케이션 플랫폼 API",
        "version": "1.0.0",
        "host": "localhost:3000" if not test_config else "localhost:3000",
        "basePath": "/",
        "schemes": ["http", "https"],
        "securityDefinitions": {
            "JWT": {
                "type": "apiKey",
                "name": "Authorization",
                "in": "header",
                "description": 'JWT Authorization header using the Bearer scheme. Example: "Authorization: Bearer {token}"',
            },
            "AdminHeader": {
                "type": "apiKey",
                "name": "X-Admin",
                "in": "header",
                "description": "Admin header for admin-only endpoints. Use 'true' as value.",
            },
        },
        "security": [{"JWT": []}],
    }

    swagger_template = {
        "swagger": "2.0",
        "info": {
            "title": "LikeBike API",
            "description": "자전거 이용 활성화를 위한 게이미피케이션 플랫폼 API",
            "contact": {
                "name": "LikeBike Team",
                "url": "https://github.com/HiHoi/LikeBike_backend",
            },
            "version": "1.0.0",
        },
        "host": "localhost:3000",
        "basePath": "/",
        "schemes": ["http", "https"],
        "securityDefinitions": {
            "JWT": {
                "type": "apiKey",
                "name": "Authorization",
                "in": "header",
                "description": 'JWT Authorization header using the Bearer scheme. Example: "Authorization: Bearer {token}"',
            },
            "AdminHeader": {
                "type": "apiKey",
                "name": "X-Admin",
                "in": "header",
                "description": "Admin header for admin-only endpoints. Use 'true' as value.",
            },
        },
    }

    Swagger(app, config=swagger_config, template=swagger_template)

    return app
