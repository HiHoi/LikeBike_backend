from flask import Blueprint, request

from ..utils.responses import make_response
from ..utils.auth import jwt_required, admin_required

from ..db import get_db

bp = Blueprint("news", __name__)


@bp.route("/admin/news", methods=["POST"])
@admin_required
def create_news():
    """
    뉴스 생성 (관리자)
    ---
    tags:
      - News
    summary: 새로운 뉴스 작성 (관리자 전용)
    description: 관리자 권한으로 새로운 뉴스를 작성합니다.
    security:
      - JWT: []
      - AdminHeader: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - title
            - content
          properties:
            title:
              type: string
              description: 뉴스 제목
              example: "새로운 자전거 도로 개통"
            content:
              type: string
              description: 뉴스 내용
              example: "한강변에 새로운 자전거 전용 도로가 개통되었습니다..."
    responses:
      201:
        description: 뉴스 생성 성공
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 201
            message:
              type: string
              example: "Created"
            data:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: integer
                    example: 1
                  title:
                    type: string
                    example: "새로운 자전거 도로 개통"
                  content:
                    type: string
                    example: "한강변에 새로운 자전거 전용 도로가 개통되었습니다..."
                  published_at:
                    type: string
                    format: date-time
                    example: "2024-01-01T00:00:00Z"
      400:
        description: 잘못된 요청
      401:
        description: 인증 실패
      403:
        description: 관리자 권한 필요
    """
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
@admin_required
def update_news(news_id):
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
@admin_required
def delete_news(news_id):
    db = get_db()
    with db.cursor() as cur:
        cur.execute("DELETE FROM news WHERE id = %s", (news_id,))
        if cur.rowcount == 0:
            return make_response({"error": "news not found"}, 404)
    return make_response(None, 204)


@bp.route("/news", methods=["GET"])
@jwt_required
def list_news():
    """
    뉴스 목록 조회
    ---
    tags:
      - News
    summary: 뉴스 목록 조회
    description: 등록된 뉴스들의 목록을 조회합니다.
    security:
      - JWT: []
    responses:
      200:
        description: 뉴스 목록 조회 성공
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 200
            message:
              type: string
              example: "OK"
            data:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: integer
                    example: 1
                  title:
                    type: string
                    example: "새로운 자전거 도로 개통"
                  content:
                    type: string
                    example: "한강변에 새로운 자전거 전용 도로가 개통되었습니다..."
                  published_at:
                    type: string
                    format: date-time
                    example: "2024-01-01T00:00:00Z"
      401:
        description: 인증 실패
    """
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "SELECT id, title, content, published_at FROM news ORDER BY published_at DESC"
        )
        rows = cur.fetchall()
    return make_response(rows)


@bp.route("/news/<int:news_id>", methods=["GET"])
@jwt_required
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
