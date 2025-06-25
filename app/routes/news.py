from flask import Blueprint, request

from ..utils.responses import make_response

from ..db import get_db

bp = Blueprint("news", __name__)


def _require_admin():
    if request.headers.get("X-Admin") != "true":
        return make_response({"error": "admin only"}, 403)
    return None


@bp.route("/admin/news", methods=["POST"])
def create_news():
    admin_check = _require_admin()
    if admin_check:
        return admin_check
    data = request.get_json() or {}
    title = data.get("title")
    content = data.get("content")
    if not title or not content:
        return make_response({"error": "title and content required"}, 400)

    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO news (title, content) VALUES (%s, %s) RETURNING id, published_at",
            (title, content),
        )
        row = cur.fetchone()
    return make_response(
        {
            "id": row["id"],
            "title": title,
            "content": content,
            "published_at": row["published_at"],
        },
        201,
    )


@bp.route("/admin/news/<int:news_id>", methods=["PUT"])
def update_news(news_id):
    admin_check = _require_admin()
    if admin_check:
        return admin_check
    data = request.get_json() or {}
    title = data.get("title")
    content = data.get("content")
    if not title or not content:
        return make_response({"error": "title and content required"}, 400)

    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "UPDATE news SET title = %s, content = %s WHERE id = %s RETURNING id, title, content, published_at",
            (title, content, news_id),
        )
        result = cur.fetchone()
        if not result:
            return make_response({"error": "news not found"}, 404)
    return make_response(dict(result))


@bp.route("/admin/news/<int:news_id>", methods=["DELETE"])
def delete_news(news_id):
    admin_check = _require_admin()
    if admin_check:
        return admin_check
    db = get_db()
    with db.cursor() as cur:
        cur.execute("DELETE FROM news WHERE id = %s", (news_id,))
        if cur.rowcount == 0:
            return make_response({"error": "news not found"}, 404)
    return make_response(None, 204)


@bp.route("/news", methods=["GET"])
def list_news():
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "SELECT id, title, content, published_at FROM news ORDER BY published_at DESC"
        )
        rows = cur.fetchall()
    return make_response(rows)


@bp.route("/news/<int:news_id>", methods=["GET"])
def get_news(news_id):
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "SELECT id, title, content, published_at FROM news WHERE id = %s",
            (news_id,),
        )
        row = cur.fetchone()
        if not row:
            return make_response({"error": "news not found"}, 404)
    return make_response(dict(row))
