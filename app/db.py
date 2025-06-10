import os
import psycopg2
import psycopg2.extras
import click
from flask import current_app, g
from flask.cli import with_appcontext

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "schema.sql")


def get_db():
    if "db" not in g:
        if 'DATABASE_URL' in current_app.config:
            g.db = psycopg2.connect(
                current_app.config['DATABASE_URL'],
                cursor_factory=psycopg2.extras.RealDictCursor
            )
        else:
            g.db = psycopg2.connect(
                host=current_app.config.get('DB_HOST', 'localhost'),
                port=current_app.config.get('DB_PORT', 5432),
                database=current_app.config.get('DB_NAME', 'likebike'),
                user=current_app.config.get('DB_USER', os.environ.get('USER')),
                password=current_app.config.get('DB_PASSWORD', ''),
                cursor_factory=psycopg2.extras.RealDictCursor
            )
        g.db.autocommit = True
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


@click.command('init-db')
@with_appcontext
def init_db_command():
    """Clear the existing data and create new tables."""
    init_db()
    click.echo('Initialized the database.')


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    # 개발 환경에서만 자동 초기화
    if app.config.get('TESTING'):
        with app.app_context():
            init_db()