from __future__ import annotations

import asyncio
import os
from typing import Any, Dict

import aiohttp
from flask import Blueprint, request

from ..db import get_db
from ..utils.auth import (
    generate_jwt_token,
    get_current_user_id,
    get_token_from_header,
    jwt_required,
    refresh_jwt_token,
)
from ..utils.responses import make_response

bp = Blueprint("users", __name__)

KAKAO_REST_API_KEY = os.environ.get("KAKAO_REST_API_KEY")
KAKAO_REDIRECT_URI = os.environ.get("KAKAO_REDIRECT_URI")


async def fetch_kakao_tokens(code: str) -> dict:
    """Exchange authorization code for access and refresh tokens."""
    url = "https://kauth.kakao.com/oauth/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded;charset=utf-8"}
    data = {
        "grant_type": "authorization_code",
        "client_id": KAKAO_REST_API_KEY,
        "redirect_uri": KAKAO_REDIRECT_URI,
        "code": code,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, data=data) as resp:
            resp.raise_for_status()
            return await resp.json()


async def fetch_kakao_user_info(access_token: str) -> dict:
    """Retrieve user info from Kakao API."""
    url = "https://kapi.kakao.com/v2/user/me"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
        "Authorization": f"Bearer {access_token}",
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            resp.raise_for_status()
            return await resp.json()


@bp.route("/users", methods=["POST"])
def register_user():
    """
    사용자 등록/로그인
    ---
    tags:
      - Users
    summary: 카카오 Oauth를 사용하여 사용자 등록 또는 로그인
    description: 카카오 Oauth를 사용하여 새 사용자를 등록합니다.
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - code
          properties:
            code:
              type: string
              description: 카카오 액세스 코드
              example: "kakao_oauth_code_example"
    responses:
      201:
        description: 사용자 등록/로그인 성공
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
                  username:
                    type: string
                    example: "사용자명"
                  email:
                    type: string
                    example: "user@kakao.com"
                  profile_image_url:
                    type: string
                    example: "https://k.kakaocdn.net/dn/profile.jpg"
                  access_token:
                    type: string
                    example: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
      400:
        description: 잘못된 요청
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 400
            message:
              type: string
              example: "Bad Request"
            data:
              type: array
              items:
                type: object
                properties:
                  error:
                    type: string
                    example: "access_token required"
    """
    data = request.get_json() or {}
    code = data.get("code")
    if not code:
        return make_response({"error": "authorization code missing"}, 400)

    try:
        token_info = asyncio.run(fetch_kakao_tokens(code))
        access_token = token_info.get("access_token")
        if not access_token:
            return make_response({"error": "failed to get kakao access token"}, 400)

        kakao_user_info = asyncio.run(fetch_kakao_user_info(access_token))

        kakao_id = str(kakao_user_info.get("id"))
        kakao_account = kakao_user_info.get("kakao_account", {})
        profile = kakao_account.get("profile", {})
        username = profile.get("nickname") or "user"
        email = kakao_account.get("email") or f"{kakao_id}@kakao"
        profile_image_url = profile.get("profile_image_url") or profile.get(
            "thumbnail_image_url"
        )

        db = get_db()
        with db.cursor() as cur:
            cur.execute(
                "SELECT id FROM users WHERE kakao_id = %s",
                (kakao_id,),
            )
            existing = cur.fetchone()
            if existing:
                user_id = existing["id"]
                # 기존 사용자의 프로필 정보 업데이트 (프로필 이미지 포함)
                cur.execute(
                    "UPDATE users SET username = %s, email = %s, profile_image_url = %s WHERE id = %s",
                    (username, email, profile_image_url, user_id),
                )
            else:
                cur.execute(
                    "INSERT INTO users (kakao_id, username, email, profile_image_url) VALUES (%s, %s, %s, %s) RETURNING id",
                    (kakao_id, username, email, profile_image_url),
                )
                user_id = cur.fetchone()["id"]

                # 기본 설정 생성
                cur.execute(
                    "INSERT INTO user_settings (user_id) VALUES (%s)", (user_id,)
                )

            # JWT 토큰 생성
            jwt_token = generate_jwt_token(user_id, username, email)

        return make_response(
            {
                "id": user_id,
                "username": username,
                "email": email,
                "profile_image_url": profile_image_url,
                "access_token": jwt_token,
            },
            201,
        )

    except Exception as e:
        # TODO: Log the error properly
        return make_response({"error": f"kakao login failed: {str(e)}"}, 500)


@bp.route("/users/profile", methods=["PUT"])
@jwt_required
def update_user():
    """
    사용자 정보 수정
    ---
    tags:
      - Users
    summary: 사용자 프로필 정보 수정
    description: 현재 로그인한 사용자의 프로필 정보를 수정합니다.
    security:
      - JWT: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            username:
              type: string
              description: 새로운 사용자명
              example: "새로운사용자명"
            email:
              type: string
              description: 새로운 이메일
              example: "newemail@example.com"
            profile_image_url:
              type: string
              description: 새로운 프로필 이미지 URL
              example: "https://k.kakaocdn.net/dn/newprofile.jpg"
    responses:
      200:
        description: 사용자 정보 수정 성공
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
                  username:
                    type: string
                    example: "새로운사용자명"
                  email:
                    type: string
                    example: "newemail@example.com"
                  profile_image_url:
                    type: string
                    example: "https://k.kakaocdn.net/dn/newprofile.jpg"
      400:
        description: 잘못된 요청
      401:
        description: 인증 실패
    """
    user_id = get_current_user_id()
    data = request.get_json() or {}
    username = data.get("username")
    email = data.get("email")
    profile_image_url = data.get("profile_image_url")
    if not username and not email and not profile_image_url:
        return make_response({"error": "nothing to update"}, 400)

    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """UPDATE users SET 
               username = COALESCE(%s, username), 
               email = COALESCE(%s, email),
               profile_image_url = COALESCE(%s, profile_image_url)
               WHERE id = %s 
               RETURNING id, username, email, profile_image_url""",
            (username, email, profile_image_url, user_id),
        )
        updated = cur.fetchone()
        if not updated:
            return make_response({"error": "user not found"}, 404)

    return make_response(dict(updated))


def _remove_user(user_id: int) -> int:
    db = get_db()
    with db.cursor() as cur:
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        return cur.rowcount


@bp.route("/users/profile", methods=["DELETE"])
@jwt_required
def delete_user():
    user_id = get_current_user_id()
    deleted = _remove_user(user_id)
    if deleted == 0:
        return make_response({"error": "user not found"}, 404)

    return make_response(None, 204)


@bp.route("/users/withdraw", methods=["DELETE"])
@jwt_required
def withdraw_user():
    """사용자가 자신의 계정을 완전히 삭제합니다."""
    user_id = get_current_user_id()
    deleted = _remove_user(user_id)
    if deleted == 0:
        return make_response({"error": "user not found"}, 404)

    return make_response(None, 204)


# 로그아웃 엔드포인트 추가
@bp.route("/users/logout", methods=["POST"])
@jwt_required
def logout_user():
    """
    로그아웃
    ---
    tags:
      - Users
    summary: 사용자 로그아웃
    description: 현재 세션을 종료합니다. 클라이언트에서 토큰을 삭제해야 합니다.
    security:
      - JWT: []
    responses:
      200:
        description: 로그아웃 성공
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
                  message:
                    type: string
                    example: "Successfully logged out"
      401:
        description: 인증 실패
    """
    # JWT는 stateless이므로 클라이언트에서 토큰을 삭제하도록 안내
    return make_response({"message": "Successfully logged out"}, 200)


# 토큰 새로고침 엔드포인트 추가
@bp.route("/users/refresh", methods=["POST"])
@jwt_required
def refresh_token():
    """
    토큰 새로고침
    ---
    tags:
      - Users
    summary: JWT 토큰 새로고침
    description: 기존 토큰을 새로운 토큰으로 갱신합니다.
    security:
      - JWT: []
    responses:
      200:
        description: 토큰 새로고침 성공
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
                  access_token:
                    type: string
                    example: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
      401:
        description: 인증 실패
    """
    current_token = get_token_from_header()
    new_token = refresh_jwt_token(current_token)

    if not new_token:
        return make_response({"error": "Failed to refresh token"}, 400)

    return make_response({"access_token": new_token}, 200)


@bp.route("/users/profile", methods=["GET"])
@jwt_required
def get_user_profile():
    """
    사용자 프로필 조회
    ---
    tags:
      - Users
    summary: 현재 로그인한 사용자의 프로필 정보 조회
    description: JWT 토큰을 통해 인증된 사용자의 상세 프로필 정보를 조회합니다.
    security:
      - JWT: []
    responses:
      200:
        description: 사용자 프로필 조회 성공
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
                  username:
                    type: string
                    example: "사용자명"
                  email:
                    type: string
                    example: "user@example.com"
                  profile_image_url:
                    type: string
                    example: "https://k.kakaocdn.net/dn/profile.jpg"
                  points:
                    type: integer
                    example: 150
                  level:
                    type: integer
                    example: 2
                  experience_points:
                    type: integer
                    example: 250
                  level_name:
                    type: string
                    example: "중급자"
                  description:
                    type: string
                    example: "레벨 설명"
                  benefits:
                    type: string
                    example: "혜택 정보"
                  created_at:
                    type: string
                    format: date-time
                    example: "2024-01-01T00:00:00Z"
      401:
        description: 인증 실패
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 401
            message:
              type: string
              example: "Unauthorized"
            data:
              type: array
              items:
                type: object
                properties:
                  error:
                    type: string
                    example: "Token required"
    """
    user_id = get_current_user_id()
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT u.id, u.username, u.email, u.profile_image_url, u.points, u.level, u.experience_points,
                   ul.level_name, ul.description, ul.benefits, u.created_at
            FROM users u
            LEFT JOIN user_levels ul ON u.level = ul.level
            WHERE u.id = %s
        """,
            (user_id,),
        )
        user = cur.fetchone()
        if not user:
            return make_response({"error": "user not found"}, 404)

    return make_response(dict(user))


@bp.route("/users/level", methods=["PUT"])
@jwt_required
def update_user_level():
    """사용자 경험치 업데이트 및 레벨 확인"""
    user_id = get_current_user_id()
    data = request.get_json() or {}
    experience_points = data.get("experience_points", 0)

    db = get_db()
    with db.cursor() as cur:
        # 현재 사용자 정보 조회
        cur.execute(
            "SELECT level, experience_points FROM users WHERE id = %s", (user_id,)
        )
        user = cur.fetchone()
        if not user:
            return make_response({"error": "user not found"}, 404)

        new_exp = user["experience_points"] + experience_points

        # 새로운 레벨 계산
        cur.execute(
            """
            SELECT level FROM user_levels 
            WHERE required_exp <= %s 
            ORDER BY level DESC LIMIT 1
        """,
            (new_exp,),
        )
        level_result = cur.fetchone()
        new_level = level_result["level"] if level_result else 1

        # 사용자 정보 업데이트
        cur.execute(
            """
            UPDATE users 
            SET experience_points = %s, level = %s 
            WHERE id = %s 
            RETURNING level, experience_points
        """,
            (new_exp, new_level, user_id),
        )
        updated = cur.fetchone()

        level_up = new_level > user["level"]

    return make_response(
        {
            "level": updated["level"],
            "experience_points": updated["experience_points"],
            "level_up": level_up,
        }
    )


@bp.route("/users/score", methods=["PUT"])
@jwt_required
def update_user_score():
    """
    사용자 점수 업데이트
    ---
    tags:
      - Users
    summary: 사용자 점수 증감
    description: 현재 로그인한 사용자의 점수를 입력된 값만큼 증감합니다. 음수 입력 시 점수는 0 미만으로 내려가지 않습니다.
    security:
      - JWT: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
            properties:
                experience_points:
                  type: integer
                  description: 점수 변화량 (양수 또는 음수). 기본값은 0입니다.
                  example: 10
                  default: 0
            reward_reason:
              type: string
              description: 점수 변동 사유 (보상 기록용)
              example: "테스트 보상"
    responses:
      200:
        description: 사용자 점수 업데이트 성공
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
                experience_points:
                  type: integer
                  example: 160`
      401:
        description: 인증 실패
    """
    user_id = get_current_user_id()
    data = request.get_json() or {}
    exp_change = data.get("experience_points", 0)
    reward_reason = data.get("reward_reason")

    db = get_db()
    with db.cursor() as cur:
        # 경험치 업데이트 (0 미만으로 내려가지 않도록 GREATEST 사용)
        cur.execute(
            """
            UPDATE users
            SET experience_points = GREATEST(0, experience_points + %s)
            WHERE id = %s
            RETURNING experience_points
            """,
            (exp_change, user_id),
        )

        updated_user = cur.fetchone()
        if updated_user is None:
            return make_response({"error": "User not found"}, 404)

        updated_exp = updated_user["experience_points"]

        if exp_change > 0:
            cur.execute(
                """
                INSERT INTO rewards
                    (user_id, source_type, points, experience_points, reward_reason, status)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    user_id,
                    "score_update",
                    0,
                    exp_change,
                    reward_reason,
                    "completed",
                ),
            )

    return make_response({"experience_points": updated_exp})


@bp.route("/users/settings", methods=["GET"])
@jwt_required
def get_user_settings():
    """
    사용자 설정 조회
    ---
    tags:
      - Users
    summary: 사용자 설정 조회
    description: 현재 로그인한 사용자의 설정 정보를 조회합니다.
    security:
      - JWT: []
    responses:
      200:
        description: 사용자 설정 조회 성공
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
                notification_enabled:
                  type: boolean
                  example: true
                location_sharing:
                  type: boolean
                  example: false
                privacy_level:
                  type: string
                  enum: ["public", "friends", "private"]
                  example: "public"
                preferences:
                  type: object
                  example: {"theme": "light", "language": "ko"}
                created_at:
                  type: string
                  format: date-time
                  example: "2024-01-01T00:00:00Z"
                updated_at:
                  type: string
                  format: date-time
                  example: "2024-01-01T00:00:00Z"
      401:
        description: 인증 실패
    """
    user_id = get_current_user_id()
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT * FROM user_settings WHERE user_id = %s", (user_id,))
        settings = cur.fetchone()
        if not settings:
            # 기본 설정 생성
            cur.execute(
                """
                INSERT INTO user_settings (user_id) 
                VALUES (%s) 
                RETURNING *
            """,
                (user_id,),
            )
            settings = cur.fetchone()

    return make_response(dict(settings))


@bp.route("/users/settings", methods=["PUT"])
@jwt_required
def update_user_settings():
    """
    사용자 설정 업데이트
    ---
    tags:
      - Users
    summary: 사용자 설정 업데이트
    description: 현재 로그인한 사용자의 설정 정보를 업데이트합니다.
    security:
      - JWT: []
    parameters:
      - in: body
        name: body
        schema:
          type: object
          properties:
            notification_enabled:
              type: boolean
              description: 알림 활성화 여부
              example: true
            location_sharing:
              type: boolean
              description: 위치 공유 여부
              example: false
            privacy_level:
              type: string
              enum: ["public", "friends", "private"]
              description: 개인정보 공개 수준
              example: "public"
            preferences:
              type: object
              description: 사용자 기본 설정
              example: {"theme": "dark", "language": "ko"}
    responses:
      200:
        description: 사용자 설정 업데이트 성공
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
                notification_enabled:
                  type: boolean
                  example: true
                location_sharing:
                  type: boolean
                  example: false
                privacy_level:
                  type: string
                  example: "public"
                preferences:
                  type: object
                  example: {"theme": "dark", "language": "ko"}
                updated_at:
                  type: string
                  format: date-time
                  example: "2024-01-01T00:00:00Z"
      401:
        description: 인증 실패
    """
    user_id = get_current_user_id()
    data = request.get_json() or {}

    db = get_db()
    with db.cursor() as cur:
        # 설정이 존재하는지 확인
        cur.execute("SELECT id FROM user_settings WHERE user_id = %s", (user_id,))
        existing = cur.fetchone()

        if existing:
            # 업데이트
            cur.execute(
                """
                UPDATE user_settings 
                SET notification_enabled = COALESCE(%s, notification_enabled),
                    location_sharing = COALESCE(%s, location_sharing),
                    privacy_level = COALESCE(%s, privacy_level),
                    preferences = COALESCE(%s, preferences),
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %s
                RETURNING *
            """,
                (
                    data.get("notification_enabled"),
                    data.get("location_sharing"),
                    data.get("privacy_level"),
                    data.get("preferences"),
                    user_id,
                ),
            )
        else:
            # 생성
            cur.execute(
                """
                INSERT INTO user_settings 
                (user_id, notification_enabled, location_sharing, privacy_level, preferences)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING *
            """,
                (
                    user_id,
                    data.get("notification_enabled", True),
                    data.get("location_sharing", False),
                    data.get("privacy_level", "public"),
                    data.get("preferences"),
                ),
            )

        updated = cur.fetchone()

    return make_response(dict(updated))


@bp.route("/users/verifications", methods=["GET"])
@jwt_required
def get_user_verifications():
    """
    사용자 인증 내역 조회
    ---
    tags:
      - Users
    summary: 사용자 인증 내역 조회
    description: 현재 로그인한 사용자의 인증 요청 내역을 조회합니다.
    security:
      - JWT: []
    responses:
      200:
        description: 사용자 인증 내역 조회 성공
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
                  verification_type:
                    type: string
                    example: "quiz_completion"
                  source_id:
                    type: integer
                    example: 123
                  proof_data:
                    type: object
                    example: {"score": 85, "time_taken": 120}
                  status:
                    type: string
                    enum: ["pending", "approved", "rejected"]
                    example: "approved"
                  verified_at:
                    type: string
                    format: date-time
                    example: "2024-01-15T10:30:00Z"
                  created_at:
                    type: string
                    format: date-time
                    example: "2024-01-01T00:00:00Z"
      401:
        description: 인증 실패
    """
    user_id = get_current_user_id()
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT * FROM user_verifications 
            WHERE user_id = %s 
            ORDER BY created_at DESC
        """,
            (user_id,),
        )
        verifications = cur.fetchall()

    return make_response([dict(v) for v in verifications])


@bp.route("/users/verifications", methods=["POST"])
@jwt_required
def create_verification():
    """
    새로운 인증 요청 생성
    ---
    tags:
      - Users
    summary: 새로운 인증 요청 생성
    description: 현재 로그인한 사용자가 새로운 인증 요청을 생성합니다.
    security:
      - JWT: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - verification_type
          properties:
            verification_type:
              type: string
              description: 인증 유형
              example: "quiz_completion"
            source_id:
              type: integer
              description: "관련 소스 ID (예: 퀴즈 ID)"
              example: 123
            proof_data:
              type: object
              description: 인증 증명 데이터
              example: {"score": 95, "time_taken": 90}
    responses:
      201:
        description: 인증 요청 생성 성공
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
                verification_type:
                  type: string
                  example: "quiz_completion"
                source_id:
                  type: integer
                  example: 123
                proof_data:
                  type: object
                  example: {"score": 95, "time_taken": 90}
                status:
                  type: string
                  example: "pending"
                created_at:
                  type: string
                  format: date-time
                  example: "2024-01-01T00:00:00Z"
      400:
        description: 잘못된 요청
        schema:
          type: object
          properties:
            error:
              type: string
              example: "verification_type required"
      401:
        description: 인증 실패
    """
    user_id = get_current_user_id()
    data = request.get_json() or {}
    verification_type = data.get("verification_type")
    source_id = data.get("source_id")
    proof_data = data.get("proof_data")

    if not verification_type:
        return make_response({"error": "verification_type required"}, 400)

    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO user_verifications 
            (user_id, verification_type, source_id, proof_data)
            VALUES (%s, %s, %s, %s)
            RETURNING *
        """,
            (user_id, verification_type, source_id, proof_data),
        )
        verification = cur.fetchone()

    return make_response(dict(verification), 201)


@bp.route("/levels", methods=["GET"])
@jwt_required
def get_all_levels():
    """
    모든 레벨 정보 조회
    ---
    tags:
      - Users
    summary: 모든 사용자 레벨 정보 조회
    description: 시스템에 정의된 모든 사용자 레벨 정보를 조회합니다.
    security:
      - JWT: []
    responses:
      200:
        description: 레벨 정보 조회 성공
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
                  level:
                    type: integer
                    example: 1
                  name:
                    type: string
                    example: "초보자"
                  required_points:
                    type: integer
                    example: 0
                  required_experience:
                    type: integer
                    example: 0
                  badge_url:
                    type: string
                    example: "/static/badges/beginner.png"
                  description:
                    type: string
                    example: "자전거 이용을 시작한 초보자 레벨입니다"
                  created_at:
                    type: string
                    format: date-time
                    example: "2024-01-01T00:00:00Z"
      401:
        description: 인증 실패
    """
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT * FROM user_levels ORDER BY level")
        levels = cur.fetchall()

    return make_response([dict(level) for level in levels])


@bp.route("/dev/test-token", methods=["GET"])
def get_test_token():
    """
    개발용 테스트 토큰 생성 (개발 환경에서만 사용)
    ---
    tags:
      - Development
    summary: 개발용 JWT 토큰 생성
    description: 프론트엔드 개발을 위한 테스트용 JWT 토큰을 생성합니다. (개발 환경에서만 동작)
    parameters:
      - in: query
        name: user_type
        type: string
        enum: [user, admin]
        default: user
        description: 사용자 타입 (user 또는 admin)
    responses:
      200:
        description: 테스트 토큰 생성 성공
        schema:
          type: object
          properties:
            access_token:
              type: string
              description: JWT 토큰
            user_id:
              type: integer
              description: 사용자 ID
            user_type:
              type: string
              description: 사용자 타입
      403:
        description: 프로덕션 환경에서는 사용 불가
    """
    # 프로덕션 환경에서는 비활성화
    if os.environ.get("FLASK_ENV") == "production":
        return make_response({"error": "Not available in production"}, 403)

    user_type = request.args.get("user_type", "user")

    # 테스트용 사용자 생성/조회
    db = get_db()
    with db.cursor() as cur:
        if user_type == "admin":
            # 기존 테스트 관리자 조회
            cur.execute(
                """
                SELECT id, username, email, is_admin FROM users 
                WHERE kakao_id = 'test_admin_kakao_id'
            """
            )
            user = cur.fetchone()

            if not user:
                # 새로 생성
                cur.execute(
                    """
                    INSERT INTO users (kakao_id, username, email, is_admin) 
                    VALUES ('test_admin_kakao_id', 'test_admin', 'admin@test.com', true)
                    RETURNING id, username, email, is_admin
                """
                )
                user = cur.fetchone()
        else:
            # 기존 테스트 사용자 조회
            cur.execute(
                """
                SELECT id, username, email, is_admin FROM users 
                WHERE kakao_id = 'test_user_kakao_id'
            """
            )
            user = cur.fetchone()

            if not user:
                # 새로 생성
                cur.execute(
                    """
                    INSERT INTO users (kakao_id, username, email, is_admin) 
                    VALUES ('test_user_kakao_id', 'test_user', 'user@test.com', false)
                    RETURNING id, username, email, is_admin
                """
                )
                user = cur.fetchone()

        user_id = user["id"]

    # JWT 토큰 생성 (is_admin 정보 포함)
    token = generate_jwt_token(
        user_id=user_id,
        username=user["username"],
        email=user["email"],
        is_admin=user["is_admin"],
    )

    return make_response(
        {
            "access_token": token,
            "user_id": user_id,
            "user_type": user_type,
            "username": user["username"],
            "email": user["email"],
            "is_admin": user["is_admin"],
        }
    )
