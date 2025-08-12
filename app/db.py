import os

import click
import psycopg2
import psycopg2.extras
from flask import current_app, g
from flask.cli import with_appcontext

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "schema.sql")

def get_db():
    if "db" not in g:
        try:
            # DATABASE_URL 우선 사용
            database_url = current_app.config.get("DATABASE_URL") or os.environ.get("DATABASE_URL")
            
            if database_url and database_url.startswith('postgresql://'):
                g.db = psycopg2.connect(
                    database_url,
                    cursor_factory=psycopg2.extras.RealDictCursor,
                )
            else:
                # 개별 환경변수로 연결
                connection_params = {
                    'host': os.environ.get("DB_HOST", current_app.config.get("DB_HOST", "localhost")),
                    'port': int(os.environ.get("DB_PORT", current_app.config.get("DB_PORT", 5432))),
                    'database': os.environ.get("DB_NAME", current_app.config.get("DB_NAME", "postgres")),  # 기본값을 postgres로 변경
                    'user': os.environ.get("DB_USER", current_app.config.get("DB_USER", os.environ.get("USER"))),
                    'password': os.environ.get("DB_PASSWORD", current_app.config.get("DB_PASSWORD", "")),
                    'cursor_factory': psycopg2.extras.RealDictCursor
                }
                
                print(f"Connecting to database: {connection_params['host']}:{connection_params['port']}/{connection_params['database']}")
                
                try:
                    g.db = psycopg2.connect(**connection_params)
                except psycopg2.OperationalError as e:
                    if "database" in str(e) and "does not exist" in str(e):
                        # likebike 데이터베이스가 없으면 생성 시도
                        temp_params = connection_params.copy()
                        temp_params['database'] = 'postgres'  # 기본 데이터베이스로 연결
                        
                        temp_conn = psycopg2.connect(**temp_params)
                        temp_conn.autocommit = True
                        
                        with temp_conn.cursor() as cur:
                            target_db = os.environ.get("DB_NAME", "likebike")
                            cur.execute(f'CREATE DATABASE "{target_db}"')
                            print(f"Created database: {target_db}")
                        
                        temp_conn.close()
                        
                        # 새로 생성된 데이터베이스로 다시 연결
                        connection_params['database'] = target_db
                        g.db = psycopg2.connect(**connection_params)
                    else:
                        raise
            
            g.db.autocommit = True
            
        except Exception as e:
            print(f"Database connection failed: {e}")
            raise
            
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        with db.cursor() as cur:
            cur.execute(f.read())


@click.command("init-db")
@with_appcontext
def init_db_command():
    """Clear the existing data and create new tables."""
    init_db()
    click.echo("Initialized the database.")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    # 개발 환경에서만 자동 초기화
    if app.config.get("TESTING"):
        with app.app_context():
            init_db()
