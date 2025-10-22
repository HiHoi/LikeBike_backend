import csv
import io
import json
from typing import Any, Dict, List

from flask import Blueprint, Response, request

from ..db import get_db
from ..utils.auth import admin_required, get_current_user_id, jwt_required
from ..utils.responses import make_response
from .storage import upload_file_to_ncp

bp = Blueprint("recommendations", __name__)


MAX_POINTS_PER_COURSE = 5
POINT_TYPES = {"start", "via", "finish"}


def _clean_optional_text(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else None
    return value


def _normalize_courses_payload(raw_payload: str) -> List[Dict[str, Any]]:
    try:
        payload = json.loads(raw_payload)
    except (TypeError, json.JSONDecodeError) as exc:  # pragma: no cover - defensive
        raise ValueError("courses must be a valid JSON array") from exc

    if not isinstance(payload, list) or not payload:
        raise ValueError("courses must be a non-empty array")

    normalized_courses: List[Dict[str, Any]] = []
    for course in payload:
        if not isinstance(course, dict):
            raise ValueError("each course must be an object")

        label = str(course.get("label") or course.get("course_label") or "").strip()
        if not label:
            raise ValueError("course label is required")

        points = course.get("points")
        if not isinstance(points, list) or not points:
            raise ValueError("each course must include at least a start and finish point")
        if len(points) > MAX_POINTS_PER_COURSE:
            raise ValueError(f"each course can include up to {MAX_POINTS_PER_COURSE} points")

        normalized_points: List[Dict[str, Any]] = []
        start_count = 0
        finish_count = 0
        for idx, point in enumerate(points, start=1):
            if not isinstance(point, dict):
                raise ValueError("each course point must be an object")
            point_type = str(point.get("type") or point.get("point_type") or "").strip().lower()
            if point_type not in POINT_TYPES:
                raise ValueError("point type must be one of start, via, finish")
            if point_type == "start":
                start_count += 1
            if point_type == "finish":
                finish_count += 1

            name = str(point.get("name") or "").strip()
            if not name:
                raise ValueError("point name is required")

            address = _clean_optional_text(
                point.get("address") or point.get("address_name")
            )

            description_value = point.get("description")
            if description_value is None:
                description_value = point.get("notes")
            notes = _clean_optional_text(description_value)

            photo_field_raw = point.get("photo_field") or point.get("photo_key")
            photo_field = None
            if photo_field_raw is not None:
                photo_field = str(photo_field_raw).strip()
                if not photo_field:
                    raise ValueError("point photo_field cannot be empty when provided")

            photo_url_raw = point.get("photo_url") or point.get("photo")
            photo_url = None
            if photo_url_raw is not None:
                photo_url = str(photo_url_raw).strip()
                if not photo_url:
                    photo_url = None

            normalized_points.append(
                {
                    "sequence_order": idx,
                    "point_type": point_type,
                    "name": name,
                    "address": address,
                    "latitude": point.get("latitude"),
                    "longitude": point.get("longitude"),
                    "notes": notes,
                    "photo_field": photo_field,
                    "photo_url": photo_url,
                }
            )

        if start_count != 1 or finish_count != 1:
            raise ValueError("each course must include exactly one start and one finish point")

        normalized_courses.append(
            {
                "course_label": label,
                "description": course.get("description"),
                "distance_km": course.get("distance_km"),
                "duration_minutes": course.get("duration_minutes"),
                "difficulty_level": course.get("difficulty_level"),
                "points": normalized_points,
            }
        )

    return normalized_courses


def _attach_courses(db, recommendations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not recommendations:
        return []

    recommendation_ids = [rec["id"] for rec in recommendations]
    courses: Dict[int, List[Dict[str, Any]]] = {rec_id: [] for rec_id in recommendation_ids}
    points: Dict[int, List[Dict[str, Any]]] = {}

    with db.cursor() as cur:
        cur.execute(
            """
            SELECT id, recommendation_id, course_label, description, distance_km, duration_minutes, difficulty_level, created_at
            FROM course_recommendation_courses
            WHERE recommendation_id = ANY(%s)
            ORDER BY created_at ASC, id ASC
            """,
            (recommendation_ids,),
        )
        course_rows = cur.fetchall()

        course_ids = [row["id"] for row in course_rows]
        for row in course_rows:
            courses[row["recommendation_id"]].append(dict(row))

        if course_ids:
            cur.execute(
                """
                SELECT id, course_id, sequence_order, point_type, name, address, latitude, longitude, notes, photo_url
                FROM course_recommendation_points
                WHERE course_id = ANY(%s)
                ORDER BY course_id ASC, sequence_order ASC
                """,
                (course_ids,),
            )
            for point_row in cur.fetchall():
                points.setdefault(point_row["course_id"], []).append(dict(point_row))

    for rec in recommendations:
        rec_courses = []
        for course in courses.get(rec["id"], []):
            course_dict = dict(course)
            course_dict["points"] = points.get(course_dict["id"], [])
            rec_courses.append(course_dict)
        rec["courses"] = rec_courses

    return recommendations


def _serialize_recommendation(rec: Dict[str, Any]) -> Dict[str, Any]:
    base = dict(rec)
    courses = base.pop("courses", [])

    summary_value = base.pop("summary", None)
    if summary_value is not None:
        base["description"] = summary_value
    else:
        base["description"] = base.get("description")

    flattened: List[Dict[str, Any]] = []
    point_index = 0
    for course in courses:
        points = sorted(
            course.get("points", []),
            key=lambda p: (p.get("sequence_order") or 0, p.get("id") or 0),
        )
        for point in points:
            flattened.append(
                {
                    "point_id": point_index,
                    "name": point.get("name"),
                    "address": point.get("address"),
                    "description": point.get("notes"),
                    "photo_url": point.get("photo_url"),
                }
            )
            point_index += 1

    base["courses"] = flattened
    return base


def _serialize_recommendations(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [_serialize_recommendation(record) for record in records]


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
        추천 묶음의 제목, 코스 요약, 최대 5개 지점을 포함한 루트 정보를 작성하고 사진을 업로드합니다.
        코스 추천은 **주당 두 번**까지만 등록할 수 있습니다.
    security:
      - JWT: []
    consumes:
      - multipart/form-data
    parameters:
        - in: formData
          name: title
          required: true
          type: string
          description: 추천 묶음의 제목
        - in: formData
          name: description
          required: false
          type: string
          description: 추천 요약. `summary`와 동일하게 처리됩니다.
        - in: formData
          name: summary
          required: false
          type: string
          description: 추천 코스 요약
        - in: formData
          name: review
          required: true
          type: string
          description: 코스 후기 내용
        - in: formData
          name: courses
          required: true
          type: string
          description: |
            JSON 배열 문자열. 각 코스는 label, description, points(출발/경유/도착 최대 5개)를 포함합니다.
            각 point에는 선택적으로 `address`(지번/도로명), `description`(지점 설명), `photo_field`를 지정해 해당 이름의 form-data 파일을 업로드할 수 있습니다.
          example: '[{"label": "A코스", "points": [{"type": "start", "name": "출발", "address": "서울시 영등포구", "description": "출발지", "photo_field": "point_photo_1"}, {"type": "finish", "name": "도착"}]}]'
        - in: formData
          name: photo
          required: true
          type: file
          description: 코스 사진 파일
        - in: formData
          name: point_photo_*
          required: false
          type: file
          description: 각 지점에 첨부할 사진 파일. `courses` JSON의 `photo_field` 이름과 일치해야 합니다.
    responses:
      201:
        description: 코스 추천 생성 성공
      400:
        description: 잘못된 요청
      401:
        description: 인증 실패
    """
    user_id = get_current_user_id()
    title = request.form.get("title") or request.form.get("location_name")
    summary = request.form.get("summary")
    if summary is None:
        summary = request.form.get("description")
    review = request.form.get("review")
    courses_raw = request.form.get("courses")

    if not title or not review:
        return make_response({"error": "title and review required"}, 400)

    if not courses_raw:
        return make_response({"error": "courses payload required"}, 400)

    try:
        courses = _normalize_courses_payload(courses_raw)
    except ValueError as exc:
        return make_response({"error": str(exc)}, 400)

    point_photo_fields = [
        point["photo_field"]
        for course in courses
        for point in course["points"]
        if point.get("photo_field")
    ]

    if "photo" not in request.files:
        return make_response({"error": "photo required"}, 400)

    missing_point_photos = [
        field for field in set(point_photo_fields) if field not in request.files
    ]
    if missing_point_photos:
        missing_list = ", ".join(sorted(missing_point_photos))
        return make_response(
            {"error": f"missing point photo files: {missing_list}"}, 400
        )

    # 주 2회 제한
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) as count FROM course_recommendations"
            " WHERE user_id = %s"
            " AND created_at >= date_trunc('week', CURRENT_DATE)"
            " AND status != 'rejected'",  # 반려된 것 제외
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

    point_photo_urls: Dict[str, str] = {}
    for field in sorted(set(point_photo_fields)):
        point_photo = request.files.get(field)
        if point_photo is None:  # pragma: no cover - guarded by earlier validation
            continue

        uploaded_url, upload_error = upload_file_to_ncp(
            point_photo, "course_recommendations/points"
        )
        if upload_error:
            return make_response(
                {"error": f"point photo upload failed: {upload_error}"}, 500
            )
        point_photo_urls[field] = uploaded_url

    prev_autocommit = db.autocommit
    db.autocommit = False
    try:
        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO course_recommendations
                    (user_id, title, summary, review, photo_url)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING *
                """,
                (user_id, title, summary, review, photo_url),
            )
            rec = dict(cur.fetchone())

            inserted_courses: List[Dict[str, Any]] = []
            for course in courses:
                cur.execute(
                    """
                    INSERT INTO course_recommendation_courses
                        (recommendation_id, course_label, description, distance_km, duration_minutes, difficulty_level)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    (
                        rec["id"],
                        course["course_label"],
                        course.get("description"),
                        course.get("distance_km"),
                        course.get("duration_minutes"),
                        course.get("difficulty_level"),
                    ),
                )
                course_row = dict(cur.fetchone())

                course_points: List[Dict[str, Any]] = []
                for point in course["points"]:
                    point_photo_url = point.get("photo_url")
                    point_photo_field = point.get("photo_field")
                    if point_photo_field:
                        point_photo_url = point_photo_urls.get(point_photo_field)

                    cur.execute(
                        """
                        INSERT INTO course_recommendation_points
                            (course_id, sequence_order, point_type, name, address, latitude, longitude, notes, photo_url)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING *
                        """,
                        (
                            course_row["id"],
                            point["sequence_order"],
                            point["point_type"],
                            point["name"],
                            point.get("address"),
                            point.get("latitude"),
                            point.get("longitude"),
                            point.get("notes"),
                            point_photo_url,
                        ),
                    )
                    course_points.append(dict(cur.fetchone()))

                course_row["points"] = course_points
                inserted_courses.append(course_row)

            if photo_url:
                cur.execute(
                    """
                    INSERT INTO course_recommendation_assets (recommendation_id, asset_type, url)
                    VALUES (%s, %s, %s)
                    """,
                    (rec["id"], "photo", photo_url),
                )

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.autocommit = prev_autocommit

    rec["courses"] = inserted_courses
    return make_response(_serialize_recommendation(rec), 201)


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
        rows = [dict(row) for row in cur.fetchall()]

    enriched = _attach_courses(db, rows)
    return make_response(_serialize_recommendations(enriched))


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
            "WHERE user_id = %s AND created_at >= date_trunc('week', CURRENT_DATE) "
            "AND status != 'rejected'",
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
            admin_notes:
              type: string
              description: 관리자 메모
              example: "좋은 코스 추천입니다"
    responses:
      200:
        description: 코스 추천 검토 성공
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
              type: object
              properties:
                id:
                  type: integer
                  example: 1
                user_id:
                  type: integer
                  example: 2
                status:
                  type: string
                  example: verified
                points_awarded:
                  type: integer
                  example: 5
                admin_notes:
                  type: string
                  example: "훌륭한 코스"
                reviewed_at:
                  type: string
                  example: "2024-01-01T10:00:00Z"
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
    admin_notes = data.get("admin_notes", "")

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
                admin_notes = %s,
                reviewed_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING id, status, points_awarded, admin_notes, reviewed_at
            """,
            (
                status,
                points if status == "verified" else 0,
                admin_id,
                admin_notes,
                rec_id,
            ),
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
    description: 관리자가 제출된 모든 코스 추천을 최신순으로 조회합니다. 각 추천에는 요청한 사용자의 username이 포함됩니다.
    security:
      - JWT: []
      - AdminHeader: []
    parameters:
      - in: query
        name: limit
        type: integer
        required: false
        description: 조회할 추천 개수 (기본값 50)
        default: 50
      - in: query
        name: offset
        type: integer
        required: false
        description: 건너뛸 추천 개수 (기본값 0)
        default: 0
    responses:
      200:
        description: 코스 추천 목록 조회 성공
      401:
        description: 인증 실패
      403:
        description: 관리자 권한 필요
    """
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))

    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT cr.*, u.username
            FROM course_recommendations AS cr
            JOIN users AS u ON cr.user_id = u.id
            ORDER BY cr.created_at DESC
            LIMIT %s OFFSET %s
            """,
            (limit, offset),
        )
        rows = [dict(row) for row in cur.fetchall()]

    enriched = _attach_courses(db, rows)
    return make_response(_serialize_recommendations(enriched))


@bp.route("/admin/course-recommendations/export", methods=["GET"])
@admin_required
def export_course_recommendations():
    """코스 추천 이력 CSV 다운로드 (관리자)
    ---
    tags:
      - Course Recommendations
    summary: 승인 또는 반려된 코스 추천 이력을 CSV 파일로 다운로드
    description: 관리자가 승인하거나 반려한 코스 추천 이력을 CSV 형식으로 제공합니다.
    security:
      - JWT: []
      - AdminHeader: []
    parameters:
      - in: query
        name: status
        type: string
        required: false
        description: 필터링할 상태 (verified 또는 rejected)
    responses:
      200:
        description: CSV 파일 반환
      400:
        description: 잘못된 요청
      401:
        description: 인증 실패
      403:
        description: 관리자 권한 필요
    """

    status = request.args.get("status")
    allowed_statuses = {"verified", "rejected"}
    if status and status not in allowed_statuses:
        return make_response({"error": "status must be 'verified' or 'rejected'"}, 400)

    db = get_db()
    with db.cursor() as cur:
        if status:
            cur.execute(
                """
                SELECT cr.*, u.username
                FROM course_recommendations cr
                JOIN users u ON cr.user_id = u.id
                WHERE cr.status = %s
                ORDER BY cr.created_at DESC
                """,
                (status,),
            )
        else:
            cur.execute(
                """
                SELECT cr.*, u.username
                FROM course_recommendations cr
                JOIN users u ON cr.user_id = u.id
                WHERE cr.status IN ('verified', 'rejected')
                ORDER BY cr.created_at DESC
                """,
            )

        rows = [dict(row) for row in cur.fetchall()]

    enriched_rows = _attach_courses(db, rows)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "id",
            "username",
            "title",
            "summary",
            "photo_url",
            "review",
            "courses",
            "status",
            "points_awarded",
            "reviewed_at",
            "created_at",
        ]
    )
    for row in enriched_rows:
        course_payload = []
        for course in row.get("courses", []):
            course_payload.append(
                {
                    "label": course.get("course_label"),
                    "points": [
                        {
                            "order": point.get("sequence_order"),
                            "type": point.get("point_type"),
                            "name": point.get("name"),
                        }
                        for point in course.get("points", [])
                    ],
                }
            )

        writer.writerow(
            [
                row["id"],
                row["username"],
                row.get("title"),
                row.get("summary"),
                row["photo_url"],
                row["review"],
                json.dumps(course_payload, ensure_ascii=False),
                row["status"],
                row["points_awarded"],
                row["reviewed_at"],
                row["created_at"],
            ]
        )

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=course_recommendations.csv"
        },
    )
