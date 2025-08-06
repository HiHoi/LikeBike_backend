from flask import Blueprint, request

from ..db import get_db
from ..utils.auth import admin_required, get_current_user_id, jwt_required
from ..utils.responses import make_response
from .storage import upload_file_to_ncp

bp = Blueprint("recommendations", __name__)


@bp.route("/users/course-recommendations", methods=["POST"])
@jwt_required
def create_course_recommendation():
    """
    코스 추천 생성
    ---
    tags:
      - Course Recommendations
    summary: 새로운 코스 추천 등록
    description: |
      코스 위치 이름과 후기를 입력하고 사진을 업로드하여 코스를 추천합니다.
      코스 추천은 **주당 두 번**까지만 등록할 수 있습니다.
    security:
      - JWT: []
    consumes:
      - multipart/form-data
    parameters:
      - in: formData
        name: location_name
        required: true
        type: string
        description: 코스 위치 이름
      - in: formData
        name: review
        required: true
        type: string
        description: 코스 후기 내용
      - in: formData
        name: photo
        required: true
        type: file
        description: 코스 사진 파일
    responses:
      201:
        description: 코스 추천 생성 성공
      400:
        description: 잘못된 요청
      401:
        description: 인증 실패
    """
    user_id = get_current_user_id()
    location_name = request.form.get("location_name")
    review = request.form.get("review")

    if not location_name or not review:
        return make_response({"error": "location_name and review required"}, 400)

    if "photo" not in request.files:
        return make_response({"error": "photo required"}, 400)

    # 주 2회 제한
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) as count FROM course_recommendations"
            " WHERE user_id = %s"
            " AND created_at >= date_trunc('week', CURRENT_DATE)",
            (user_id,),
        )
        result = cur.fetchone()
        if result and result["count"] >= 2:
            return make_response(
                {"error": "weekly course recommendation limit reached"}, 400
            )

    photo = request.files["photo"]
    photo_url, error = upload_file_to_ncp(photo, "course_recommendations")
    if error:
        return make_response({"error": f"photo upload failed: {error}"}, 500)

    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO course_recommendations
                (user_id, location_name, photo_url, review)
            VALUES (%s, %s, %s, %s)
            RETURNING *
            """,
            (user_id, location_name, photo_url, review),
        )
        rec = cur.fetchone()

    return make_response(dict(rec), 201)


@bp.route("/users/course-recommendations", methods=["GET"])
@jwt_required
def list_course_recommendations():
    """
    자신의 코스 추천 내역 조회
    ---
    tags:
      - Course Recommendations
    summary: 내가 추천한 코스 목록 조회
    description: 현재 로그인한 사용자가 등록한 코스 추천 내역을 최신순으로 조회합니다.
    security:
      - JWT: []
    responses:
      200:
        description: 코스 추천 목록 조회 성공
      401:
        description: 인증 실패
    """
    user_id = get_current_user_id()
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT * FROM course_recommendations
            WHERE user_id = %s
            ORDER BY created_at DESC
            """,
            (user_id,),
        )
        rows = cur.fetchall()
    return make_response([dict(row) for row in rows])


@bp.route("/users/course-recommendations/week/count", methods=["GET"])
@jwt_required
def week_course_recommendation_count():
    """이번 주 코스 추천 생성 횟수 조회
    ---
    tags:
      - Course Recommendations
    summary: 사용자가 이번 주에 생성한 코스 추천 횟수 조회
    security:
      - JWT: []
    responses:
      200:
        description: 생성 횟수 조회 성공
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
                  count:
                    type: integer
                    example: 1
      401:
        description: 인증 실패
    """
    user_id = get_current_user_id()
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) as count FROM course_recommendations "
            "WHERE user_id = %s AND created_at >= date_trunc('week', CURRENT_DATE)",
            (user_id,),
        )
        result = cur.fetchone()
        count = result["count"] if result else 0

    return make_response({"count": count})


@bp.route("/admin/course-recommendations/<int:rec_id>/verify", methods=["POST"])
@admin_required
def verify_course_recommendation(rec_id: int):
    """
    코스 추천 검토 및 포인트 지급
    ---
    tags:
      - Course Recommendations
    summary: 추천된 코스 검토
    description: 관리자가 사용자의 코스 추천을 승인하거나 거절하고 포인트를 지급합니다.
    security:
      - JWT: []
      - AdminHeader: []
    parameters:
      - in: path
        name: rec_id
        required: true
        type: integer
        description: 검토할 코스 추천 ID
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - status
          properties:
            status:
              type: string
              enum: [verified, rejected]
              description: 승인 여부
              example: verified
            points:
              type: integer
              description: 승인 시 지급할 포인트
              example: 5
    responses:
      200:
        description: 코스 추천 검토 성공
      400:
        description: 잘못된 요청
      401:
        description: 인증 실패
      403:
        description: 관리자 권한 필요
      404:
        description: 코스 추천을 찾을 수 없음
    """
    data = request.get_json() or {}
    status = data.get("status")
    points = data.get("points", 0)

    if status not in ["verified", "rejected"]:
        return make_response({"error": "status must be 'verified' or 'rejected'"}, 400)

    if status == "verified" and points <= 0:
        return make_response({"error": "points must be greater than 0"}, 400)

    admin_id = get_current_user_id()
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "SELECT user_id, status FROM course_recommendations WHERE id = %s",
            (rec_id,),
        )
        rec = cur.fetchone()
        if not rec:
            return make_response({"error": "course recommendation not found"}, 404)
        if rec["status"] != "pending":
            return make_response(
                {"error": "course recommendation already processed"}, 400
            )

        user_id = rec["user_id"]
        cur.execute(
            """
            UPDATE course_recommendations
            SET status = %s,
                points_awarded = %s,
                reviewed_by_admin_id = %s,
                reviewed_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING id, status, points_awarded, reviewed_at
            """,
            (status, points if status == "verified" else 0, admin_id, rec_id),
        )
        updated = cur.fetchone()

        if status == "verified" and points > 0:
            cur.execute(
                """
                UPDATE users
                SET experience_points = experience_points + %s
                WHERE id = %s
                """,
                (points, user_id),
            )
            cur.execute(
                """
                INSERT INTO rewards
                    (user_id, source_type, source_id, points, experience_points, reward_reason)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    user_id,
                    "course_recommendation",
                    rec_id,
                    0,
                    points,
                    "자전거 코스 추천",
                ),
            )

    return make_response(dict(updated))


@bp.route("/admin/course-recommendations", methods=["GET"])
@admin_required
def list_all_course_recommendations():
    """모든 코스 추천 목록 조회 (관리자)
    ---
    tags:
      - Course Recommendations
    summary: 모든 코스 추천 목록 조회
    description: 관리자가 제출된 모든 코스 추천을 최신순으로 조회합니다.
    security:
      - JWT: []
      - AdminHeader: []
    responses:
      200:
        description: 코스 추천 목록 조회 성공
      401:
        description: 인증 실패
      403:
        description: 관리자 권한 필요
    """
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT * FROM course_recommendations ORDER BY created_at DESC")
        rows = cur.fetchall()
    return make_response([dict(row) for row in rows])
