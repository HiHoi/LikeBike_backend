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

COURSE_RECOMMENDATION_FIELD_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "name": "places",
        "type": "array",
        "required": True,
        "location": "formData",
        "description": "방문한 장소 목록을 담은 JSON 배열 문자열.",
        "example": '[{"name": "카카오프렌즈 코엑스", "address_name": "서울 강남구 영동대로 513", "x": "127.05902969025047", "y": "37.51207393248871", "photo": "https://example.com/photo.jpg", "description": "코엑스에 있는 카카오프렌즈샵"}]',
    },
    {
        "name": "photo",
        "type": "file",
        "required": True,
        "location": "formData",
        "description": "코스 대표 사진 파일.",
    },
]

COURSE_RECOMMENDATION_PLACE_ITEM_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["name", "address_name", "x", "y"],
    "properties": {
        "name": {
            "type": "string",
            "description": "장소 이름",
            "example": "카카오프렌즈 코엑스",
        },
        "address_name": {
            "type": "string",
            "description": "장소 주소",
            "example": "서울 강남구 영동대로 513",
        },
        "x": {
            "type": "string",
            "description": "경도(longitude)",
            "example": "127.05902969025047",
        },
        "y": {
            "type": "string",
            "description": "위도(latitude)",
            "example": "37.51207393248871",
        },
        "photo": {
            "type": "string",
            "description": "장소 사진 URL.",
            "example": "https://example.com/place_photo.jpg",
        },
        "description": {
            "type": "string",
            "description": "장소에 대한 간단한 설명",
            "example": "코엑스에 있는 카카오프렌즈샵",
        },
    },
}


@bp.route("/users/course-recommendations/request-fields", methods=["GET"])
@jwt_required
def get_course_recommendation_request_fields():
    """코스 추천 생성 시 필요한 폼 필드 정보를 제공합니다."""

    return make_response(
        {
            "content_type": "multipart/form-data",
            "fields": COURSE_RECOMMENDATION_FIELD_DEFINITIONS,
            "place_item_schema": COURSE_RECOMMENDATION_PLACE_ITEM_SCHEMA,
        }
    )


def _normalize_places_payload(raw_payload: Any) -> List[Dict[str, Any]]:
    if raw_payload is None:
        raise ValueError("places payload required")

    if isinstance(raw_payload, str):
        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive
            raise ValueError("places must be provided as a JSON array") from exc
    else:
        payload = raw_payload

    if not isinstance(payload, list) or not payload:
        raise ValueError("places must be a non-empty array")

    normalized_places: List[Dict[str, Any]] = []
    for idx, place in enumerate(payload, start=1):
        if not isinstance(place, dict):
            raise ValueError("each place must be an object")

        name = str(place.get("name") or "").strip()
        if not name:
            raise ValueError("place name is required")

        address_name = str(place.get("address_name") or "").strip()
        description = str(place.get("description") or "").strip()

        latitude_raw = place.get("y")  # y 좌표를 위도로 사용
        longitude_raw = place.get("x")  # x 좌표를 경도로 사용
        try:
            latitude = float(latitude_raw)
            longitude = float(longitude_raw)
        except (TypeError, ValueError):
            raise ValueError("x(longitude) and y(latitude) must be numeric values")

        photo_value = place.get("photo")
        photo_url: str | None = None
        if isinstance(photo_value, str):
            trimmed = photo_value.strip()
            if trimmed:
                if trimmed.lower().startswith(("http://", "https://")):
                    photo_url = trimmed
                else:
                    # 이제 파일 필드는 지원하지 않으므로 URL이 아니면 오류 발생
                    raise ValueError(
                        f"place photo must be a valid URL: received '{trimmed}'"
                    )
        elif photo_value is not None:
            raise ValueError("place photo must be a URL string")

        normalized_places.append(
            {
                "sequence_order": idx,
                "name": name,
                "address_name": address_name,
                "description": description,
                "latitude": latitude,
                "longitude": longitude,
                "photo_field": None,  # 항상 None
                "photo_url": photo_url,
            }
        )

    return normalized_places


def _attach_places(db, recommendations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not recommendations:
        return []

    recommendation_ids = [rec["id"] for rec in recommendations]
    places_map: Dict[int, List[Dict[str, Any]]] = {rec_id: [] for rec_id in recommendation_ids}

    with db.cursor() as cur:
        cur.execute(
            """
            SELECT id, recommendation_id, sequence_order, name, latitude, longitude, photo_url, created_at, address_name, description
            FROM course_recommendation_places
            WHERE recommendation_id = ANY(%s)
            ORDER BY recommendation_id ASC, sequence_order ASC, id ASC
            """,
            (recommendation_ids,),
        )
        for row in cur.fetchall():
            places_map.setdefault(row["recommendation_id"], []).append(dict(row))

    for rec in recommendations:
        rec["places"] = places_map.get(rec["id"], [])

    return recommendations


def _serialize_recommendation(rec: Dict[str, Any]) -> Dict[str, Any]:
    base = dict(rec)
    places = base.pop("places", [])

    summary_value = base.pop("summary", None)
    if summary_value is not None:
        base["description"] = summary_value
    else:
        base["description"] = base.get("description")

    title = base.get("title")
    if title is not None:
        base["course_name"] = title

    if base.get("description") is not None:
        base["course_description"] = base["description"]

    sorted_places = sorted(
        places,
        key=lambda p: (p.get("sequence_order") or 0, p.get("id") or 0),
    )
    serialized_places: List[Dict[str, Any]] = []
    for idx, place in enumerate(sorted_places):
        latitude = place.get("latitude")
        longitude = place.get("longitude")
        serialized_places.append(
            {
                "place_id": idx,
                "sequence_order": place.get("sequence_order"),
                "name": place.get("name"),
                "address_name": place.get("address_name"),
                "description": place.get("description"),
                "x": str(longitude) if longitude is not None else None,
                "y": str(latitude) if latitude is not None else None,
                "latitude": float(latitude) if latitude is not None else None,
                "longitude": float(longitude) if longitude is not None else None,
                "photo_url": place.get("photo_url"),
            }
        )

    base["places"] = serialized_places
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
      방문한 장소 목록을 간단한 JSON 구조로 전달하여 추천 코스를 등록합니다.
      장소 배열에는 이름, 주소, 좌표(x, y), 사진(파일 필드명 또는 URL), 설명을 포함할 수 있습니다.
      코스 추천은 **주당 두 번**까지만 등록할 수 있습니다.
    security:
      - JWT: []
    consumes:
      - multipart/form-data
      - application/json
    parameters:
      - in: formData
        name: places
        required: true
        type: string
        description: |
          JSON 배열 문자열. 각 장소 객체는 name, address_name, x, y, photo(URL), description을 포함합니다.
        example: '[{"name": "카카오프렌즈 코엑스", "address_name": "서울 강남구 영동대로 513", "x": "127.05902969025047", "y": "37.51207393248871", "photo": "https://example.com/photo.jpg", "description": "코엑스에 있는 카카오프렌즈샵"}]'
      - in: formData
        name: photo
        required: true
        type: file
        description: 코스 대표 사진 파일 (`cover_photo`와 동일)
    responses:
      201:
        description: 코스 추천 생성 성공
      400:
        description: 잘못된 요청
      401:
        description: 인증 실패
    """
    user_id = get_current_user_id()

    if request.is_json:
        payload = request.get_json() or {}
        places_raw = payload.get("places")
    else:
        places_raw = request.form.get("places")

    try:
        places = _normalize_places_payload(places_raw)
    except ValueError as exc:
        return make_response({"error": str(exc)}, 400)

    course_photo = request.files.get("cover_photo") or request.files.get("photo")
    if course_photo is None:
        return make_response({"error": "photo required"}, 400)

    # 주 2회 제한
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) as count FROM course_recommendations"
            " WHERE user_id = %s"
            " AND created_at >= date_trunc('week', CURRENT_DATE)"
            " AND status != 'rejected'",
            (user_id,),
        )
        result = cur.fetchone()
        if result and result["count"] >= 2:
            return make_response(
                {"error": "weekly course recommendation limit reached"}, 400
            )

    photo_url, error = upload_file_to_ncp(course_photo, "course_recommendations")
    if error:
        return make_response({"error": f"photo upload failed: {error}"}, 500)

    # 코스 이름과 설명을 첫 번째 장소의 정보로 설정
    course_name = places[0]["name"] if places else "이름 없는 코스"
    course_description = places[0]["address_name"] if places else ""

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
                (user_id, course_name, course_description, "", photo_url),
            )
            rec = dict(cur.fetchone())

            inserted_places: List[Dict[str, Any]] = []
            for place in places:
                cur.execute(
                    """
                    INSERT INTO course_recommendation_places
                        (recommendation_id, sequence_order, name, latitude, longitude, photo_url, address_name, description)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    (
                        rec["id"],
                        place["sequence_order"],
                        place["name"],
                        place["latitude"],
                        place["longitude"],
                        place.get("photo_url"),
                        place.get("address_name"),
                        place.get("description"),
                    ),
                )
                inserted_places.append(dict(cur.fetchone()))

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

    rec["places"] = inserted_places
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

    enriched = _attach_places(db, rows)
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

    enriched = _attach_places(db, rows)
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

    enriched_rows = _attach_places(db, rows)

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
            "places",
            "status",
            "points_awarded",
            "reviewed_at",
            "created_at",
        ]
    )
    for row in enriched_rows:
        places_payload = [
            {
                "order": place.get("sequence_order"),
                "name": place.get("name"),
                "latitude": float(place["latitude"]) if place.get("latitude") is not None else None,
                "longitude": float(place["longitude"]) if place.get("longitude") is not None else None,
            }
            for place in row.get("places", [])
        ]

        writer.writerow(
            [
                row["id"],
                row["username"],
                row.get("title"),
                row.get("summary"),
                row["photo_url"],
                row["review"],
                json.dumps(places_payload, ensure_ascii=False),
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
