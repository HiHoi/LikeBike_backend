import os
import uuid

import boto3
from botocore.exceptions import ClientError
from flask import Blueprint, request
from werkzeug.utils import secure_filename

from ..db import get_db
from ..utils.auth import admin_required, get_current_user_id, jwt_required
from ..utils.responses import make_response

bp = Blueprint("bike_logs", __name__)

# NCP Object Storage 설정
NCP_ACCESS_KEY = os.environ.get("NCP_ACCESS_KEY")
NCP_SECRET_KEY = os.environ.get("NCP_SECRET_KEY")
NCP_REGION = os.environ.get("NCP_REGION", "kr-standard")
NCP_ENDPOINT = os.environ.get("NCP_ENDPOINT", "https://kr.object.ncloudstorage.com")
NCP_BUCKET_NAME = os.environ.get("NCP_BUCKET_NAME")

# S3 클라이언트 생성 (NCP Object Storage는 S3 호환)
s3_client = (
    boto3.client(
        "s3",
        aws_access_key_id=NCP_ACCESS_KEY,
        aws_secret_access_key=NCP_SECRET_KEY,
        region_name=NCP_REGION,
        endpoint_url=NCP_ENDPOINT,
    )
    if all([NCP_ACCESS_KEY, NCP_SECRET_KEY, NCP_BUCKET_NAME])
    else None
)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "bmp", "webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def allowed_file(filename):
    """허용된 파일 확장자인지 확인"""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def upload_file_to_ncp(file, folder_name="bike_logs"):
    """NCP Object Storage에 파일 업로드"""
    if not s3_client:
        return None, "NCP Object Storage 설정이 완료되지 않았습니다"

    if not file or file.filename == "":
        return None, "파일이 선택되지 않았습니다"

    if not allowed_file(file.filename):
        return (
            None,
            f"허용되지 않는 파일 형식입니다. 허용: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # 파일 크기 체크
    file.seek(0, 2)  # 파일 끝으로 이동
    file_size = file.tell()
    file.seek(0)  # 파일 처음으로 되돌아가기

    if file_size > MAX_FILE_SIZE:
        return None, f"파일 크기가 너무 큽니다. 최대 {MAX_FILE_SIZE // (1024*1024)}MB"

    # 안전한 파일명 생성
    filename = secure_filename(file.filename)
    file_extension = filename.rsplit(".", 1)[1].lower()
    unique_filename = f"{uuid.uuid4().hex}.{file_extension}"
    object_key = f"{folder_name}/{unique_filename}"

    try:
        # NCP Object Storage에 업로드
        s3_client.upload_fileobj(
            file,
            NCP_BUCKET_NAME,
            object_key,
            ExtraArgs={
                "ContentType": file.content_type or "application/octet-stream",
                'ACL': 'public-read'
            },
        )

        # 업로드된 파일의 URL 생성
        file_url = f"{NCP_ENDPOINT}/{NCP_BUCKET_NAME}/{object_key}"
        return file_url, None

    except ClientError as e:
        return None, f"파일 업로드 실패: {str(e)}"
    except Exception as e:
        return None, f"알 수 없는 오류: {str(e)}"


@bp.route("/users/bike-logs", methods=["POST"])
@jwt_required
def create_bike_log():
    """
    자전거 활동 기록 생성
    ---
    tags:
      - Bike Logs
    summary: 자전거 활동 시작 기록 및 사진 업로드
    description: |
      자전거 활동을 시작하고 자전거 사진과 안전 장비 사진을 업로드합니다.
      사용자는 하루 한 번만 활동 인증을 등록할 수 있습니다.
    security:
      - JWT: []
    consumes:
      - multipart/form-data
    parameters:
      - in: formData
        name: description
        type: string
        required: true
        description: 활동 설명
      - in: formData
        name: bike_photo
        type: file
        required: true
        description: 자전거 사진
      - in: formData
        name: safety_gear_photo
        type: file
        required: true
        description: 안전 장비 사진
    responses:
      201:
        description: 자전거 활동 기록 생성 성공
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
              type: object
              properties:
                id:
                  type: integer
                  example: 1
                user_id:
                  type: integer
                  example: 1
                description:
                  type: string
                  example: "한강 라이딩"
                bike_photo_url:
                  type: string
                  example: "https://kr.object.ncloudstorage.com/bucket/bike_logs/abc123.jpg"
                safety_gear_photo_url:
                  type: string
                  example: "https://kr.object.ncloudstorage.com/bucket/bike_logs/def456.jpg"
                verification_status:
                  type: string
                  example: "pending"
                started_at:
                  type: string
                  example: "2024-01-01T09:00:00Z"
      400:
        description: 잘못된 요청
      401:
        description: 인증 실패
      500:
        description: 파일 업로드 실패
    """
    user_id = get_current_user_id()

    # 폼 데이터에서 값 가져오기
    description = request.form.get("description")
    if not description:
        return make_response({"error": "description required"}, 400)

    # 파일 확인
    if "bike_photo" not in request.files or "safety_gear_photo" not in request.files:
        return make_response(
            {"error": "bike_photo and safety_gear_photo required"}, 400
        )

    # 하루 한 번만 인증 가능
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) as count FROM bike_usage_logs"
            " WHERE user_id = %s AND created_at::date = CURRENT_DATE",
            (user_id,),
        )
        result = cur.fetchone()
        if result and result["count"] >= 1:
            return make_response({"error": "daily bike log limit reached"}, 400)

    bike_photo = request.files["bike_photo"]
    safety_gear_photo = request.files["safety_gear_photo"]

    # 자전거 사진 업로드
    bike_photo_url, error = upload_file_to_ncp(bike_photo, "bike_logs/bike_photos")
    if error:
        return make_response({"error": f"자전거 사진 업로드 실패: {error}"}, 500)

    # 안전 장비 사진 업로드
    safety_gear_photo_url, error = upload_file_to_ncp(
        safety_gear_photo, "bike_logs/safety_gear"
    )
    if error:
        return make_response({"error": f"안전 장비 사진 업로드 실패: {error}"}, 500)

    # 데이터베이스에 기록 저장
    with db.cursor() as cur:
        cur.execute("SELECT id FROM users WHERE id = %s", (user_id,))
        if not cur.fetchone():
            return make_response({"error": "user not found"}, 404)

        cur.execute(
            """
            INSERT INTO bike_usage_logs
            (user_id, description, bike_photo_url, safety_gear_photo_url,
             verification_status, started_at)
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            RETURNING id, user_id, description, bike_photo_url, safety_gear_photo_url,
                      verification_status, started_at, created_at
        """,
            (user_id, description, bike_photo_url, safety_gear_photo_url, "pending"),
        )

        log = cur.fetchone()

    return make_response(dict(log), 201)


@bp.route("/users/bike-logs", methods=["GET"])
@jwt_required
def get_user_bike_logs():
    """
    사용자 자전거 활동 기록 조회
    ---
    tags:
      - Bike Logs
    summary: 사용자의 자전거 활동 기록 목록 조회
    description: 현재 로그인한 사용자의 자전거 활동 기록들을 조회합니다.
    security:
      - JWT: []
    parameters:
      - in: query
        name: status
        type: string
        required: false
        description: 검증 상태 필터 (pending, verified, rejected)
        enum: [pending, verified, rejected]
      - in: query
        name: limit
        type: integer
        required: false
        description: 조회할 기록 개수 (기본값 20)
        default: 20
      - in: query
        name: offset
        type: integer
        required: false
        description: 건너뛸 기록 개수 (기본값 0)
        default: 0
    responses:
      200:
        description: 자전거 활동 기록 조회 성공
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
                  description:
                    type: string
                    example: "한강 라이딩"
                  bike_photo_url:
                    type: string
                    example: "https://kr.object.ncloudstorage.com/bucket/bike_logs/abc123.jpg"
                  safety_gear_photo_url:
                    type: string
                    example: "https://kr.object.ncloudstorage.com/bucket/bike_logs/def456.jpg"
                  verification_status:
                    type: string
                    example: "verified"
                  points_awarded:
                    type: integer
                    example: 10
                  admin_notes:
                    type: string
                    example: "좋은 활동입니다!"
                  started_at:
                    type: string
                    example: "2024-01-01T09:00:00Z"
                  verified_at:
                    type: string
                    example: "2024-01-01T10:00:00Z"
      401:
        description: 인증 실패
    """
    user_id = get_current_user_id()
    status = request.args.get("status")
    limit = int(request.args.get("limit", 20))
    offset = int(request.args.get("offset", 0))

    db = get_db()
    with db.cursor() as cur:
        # WHERE 조건 구성
        where_clause = "WHERE user_id = %s"
        params = [user_id]

        if status:
            where_clause += " AND verification_status = %s"
            params.append(status)

        cur.execute(
            f"""
            SELECT id, description, bike_photo_url, safety_gear_photo_url, 
                   verification_status, points_awarded, admin_notes,
                   started_at, verified_at, created_at
            FROM bike_usage_logs 
            {where_clause}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """,
            params + [limit, offset],
        )

        logs = cur.fetchall()

    return make_response(logs)


@bp.route("/admin/bike-logs", methods=["GET"])
@admin_required
def get_pending_bike_logs():
    """
    관리자용 자전거 활동 기록 조회
    ---
    tags:
      - Bike Logs
    summary: 검증 대기 중인 자전거 활동 기록 조회 (관리자)
    description: 관리자가 검증해야 할 자전거 활동 기록들을 조회합니다.
    security:
      - JWT: []
      - AdminHeader: []
    parameters:
      - in: query
        name: status
        type: string
        required: false
        description: 검증 상태 필터 (기본값 pending)
        enum: [pending, verified, rejected]
        default: pending
      - in: query
        name: limit
        type: integer
        required: false
        description: 조회할 기록 개수 (기본값 50)
        default: 50
      - in: query
        name: offset
        type: integer
        required: false
        description: 건너뛸 기록 개수 (기본값 0)
        default: 0
    responses:
      200:
        description: 자전거 활동 기록 조회 성공
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
                  user_id:
                    type: integer
                    example: 1
                  username:
                    type: string
                    example: "user123"
                  description:
                    type: string
                    example: "한강 라이딩"
                  bike_photo_url:
                    type: string
                    example: "https://kr.object.ncloudstorage.com/bucket/bike_logs/abc123.jpg"
                  safety_gear_photo_url:
                    type: string
                    example: "https://kr.object.ncloudstorage.com/bucket/bike_logs/def456.jpg"
                  verification_status:
                    type: string
                    example: "pending"
                  started_at:
                    type: string
                    example: "2024-01-01T09:00:00Z"
                  created_at:
                    type: string
                    example: "2024-01-01T09:00:00Z"
      401:
        description: 인증 실패
      403:
        description: 관리자 권한 필요
    """
    status = request.args.get("status", "pending")
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))

    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT bl.id, bl.user_id, u.username, bl.description, 
                   bl.bike_photo_url, bl.safety_gear_photo_url, 
                   bl.verification_status, bl.points_awarded, bl.admin_notes,
                   bl.started_at, bl.verified_at, bl.created_at
            FROM bike_usage_logs bl
            JOIN users u ON bl.user_id = u.id
            WHERE bl.verification_status = %s
            ORDER BY bl.created_at ASC
            LIMIT %s OFFSET %s
        """,
            (status, limit, offset),
        )

        logs = cur.fetchall()

    return make_response(logs)


@bp.route("/admin/bike-logs/<int:log_id>/verify", methods=["POST"])
@admin_required
def verify_bike_log(log_id):
    """
    자전거 활동 기록 검증
    ---
    tags:
      - Bike Logs
    summary: 자전거 활동 기록 검증 및 경험치 지급 (관리자)
    description: 관리자가 자전거 활동 기록을 검증하고 경험치를 지급합니다.
    security:
      - JWT: []
      - AdminHeader: []
    parameters:
      - in: path
        name: log_id
        required: true
        type: integer
        description: 검증할 활동 기록 ID
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
              description: 검증 결과
              example: "verified"
            admin_notes:
              type: string
              description: 관리자 메모
              example: "안전 장비 착용 확인됨"
    responses:
      200:
        description: 검증 완료
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
                verification_status:
                  type: string
                  example: "verified"
                points_awarded:
                  type: integer
                  example: 10
                admin_notes:
                  type: string
                  example: "안전 장비 착용 확인됨"
                verified_at:
                  type: string
                  example: "2024-01-01T10:00:00Z"
      400:
        description: 잘못된 요청
      401:
        description: 인증 실패
      403:
        description: 관리자 권한 필요
      404:
        description: 활동 기록을 찾을 수 없음
    """
    data = request.get_json() or {}
    status = data.get("status")
    admin_notes = data.get("admin_notes", "")
    points = 10  # 자전거 활동 검증 시 지급할 경험치

    if status not in ["verified", "rejected"]:
        return make_response({"error": "status must be 'verified' or 'rejected'"}, 400)


    admin_id = get_current_user_id()

    db = get_db()
    with db.cursor() as cur:
        # 활동 기록 존재 및 상태 확인
        cur.execute(
            """
            SELECT user_id, verification_status 
            FROM bike_usage_logs 
            WHERE id = %s
        """,
            (log_id,),
        )

        log = cur.fetchone()
        if not log:
            return make_response({"error": "bike log not found"}, 404)

        if log["verification_status"] != "pending":
            return make_response({"error": "bike log already processed"}, 400)

        user_id = log["user_id"]

        # 활동 기록 업데이트
        cur.execute(
            """
            UPDATE bike_usage_logs 
            SET verification_status = %s, verified_by_admin_id = %s, 
                admin_notes = %s, points_awarded = %s, verified_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING id, verification_status, points_awarded, admin_notes, verified_at
        """,
            (status, admin_id, admin_notes, points, log_id),
        )

        updated_log = cur.fetchone()

        # 승인된 경우 경험치 지급
        if status == "verified" and points > 0:
            cur.execute(
                """
                UPDATE users
                SET experience_points = experience_points + %s
                WHERE id = %s
                """,
                (points, user_id),
            )

            # 보상 기록
            cur.execute(
                """
                INSERT INTO rewards 
                (user_id, source_type, source_id, points, experience_points, reward_reason, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
                (
                    user_id,
                    "bike_usage",
                    log_id,
                    0,
                    points,
                    "자전거 활동",
                    "completed",
                ),
            )

    return make_response(dict(updated_log))


@bp.route("/users/bike-logs/<int:log_id>", methods=["GET"])
@jwt_required
def get_bike_log_detail(log_id):
    """
    자전거 활동 기록 상세 조회
    ---
    tags:
      - Bike Logs
    summary: 특정 자전거 활동 기록 상세 정보 조회
    description: 특정 자전거 활동 기록의 상세 정보를 조회합니다.
    security:
      - JWT: []
    parameters:
      - in: path
        name: log_id
        required: true
        type: integer
        description: 조회할 활동 기록 ID
    responses:
      200:
        description: 활동 기록 상세 조회 성공
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
                  example: 1
                description:
                  type: string
                  example: "한강 라이딩"
                bike_photo_url:
                  type: string
                  example: "https://kr.object.ncloudstorage.com/bucket/bike_logs/abc123.jpg"
                safety_gear_photo_url:
                  type: string
                  example: "https://kr.object.ncloudstorage.com/bucket/bike_logs/def456.jpg"
                verification_status:
                  type: string
                  example: "verified"
                points_awarded:
                  type: integer
                  example: 10
                admin_notes:
                  type: string
                  example: "안전 장비 착용 확인됨"
                started_at:
                  type: string
                  example: "2024-01-01T09:00:00Z"
                verified_at:
                  type: string
                  example: "2024-01-01T10:00:00Z"
                created_at:
                  type: string
                  example: "2024-01-01T09:00:00Z"
      401:
        description: 인증 실패
      403:
        description: 접근 권한 없음
      404:
        description: 활동 기록을 찾을 수 없음
    """
    user_id = get_current_user_id()

    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT id, user_id, description, bike_photo_url, safety_gear_photo_url,
                   verification_status, verified_by_admin_id, admin_notes, points_awarded,
                   started_at, verified_at, created_at
            FROM bike_usage_logs 
            WHERE id = %s
        """,
            (log_id,),
        )

        log = cur.fetchone()
        if not log:
            return make_response({"error": "bike log not found"}, 404)

        # 본인의 기록이 아닌 경우 접근 거부
        if log["user_id"] != user_id:
            return make_response({"error": "access denied"}, 403)

    return make_response(dict(log))


@bp.route("/users/bike-logs/today/count", methods=["GET"])
@jwt_required
def get_today_bike_log_count():
    """
    오늘 자전거 활동 인증 횟수 조회
    ---
    tags:
      - Bike Logs
    summary: 오늘 사용자가 등록한 자전거 활동 인증 횟수 반환
    description: 로그인한 사용자가 오늘 몇 번 자전거 활동을 인증했는지 확인합니다.
    security:
      - JWT: []
    responses:
      200:
        description: 오늘 인증 횟수 조회 성공
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
            "SELECT COUNT(*) as count FROM bike_usage_logs WHERE user_id = %s AND created_at::date = CURRENT_DATE",
            (user_id,),
        )
        result = cur.fetchone()
        count = result["count"] if result else 0

    return make_response({"count": count})
