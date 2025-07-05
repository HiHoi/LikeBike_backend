from __future__ import annotations

import asyncio
from typing import Any, Dict

import aiohttp
from flask import Blueprint, request

from ..utils.responses import make_response
from ..utils.auth import generate_jwt_token, jwt_required, get_current_user_id, refresh_jwt_token, get_token_from_header

from ..db import get_db

bp = Blueprint("users", __name__)


async def fetch_kakao_user_info(access_token: str) -> Dict[str, Any]:
    """Retrieve user info from Kakao API."""
    url = "https://kapi.kakao.com/v2/user/me"
    headers = {"Authorization": f"Bearer {access_token}"}
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
    summary: 카카오 토큰을 사용하여 사용자 등록 또는 로그인
    description: 카카오 액세스 토큰을 사용하여 새 사용자를 등록하거나 기존 사용자로 로그인합니다.
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - access_token
          properties:
            access_token:
              type: string
              description: 카카오 액세스 토큰
              example: "kakao_access_token_example"
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
    access_token = data.get("access_token")
    if not access_token:
        return make_response({"error": "access_token required"}, 400)

    try:
        kakao_info = asyncio.run(fetch_kakao_user_info(access_token))
    except Exception:
        return make_response({"error": "invalid kakao token"}, 400)

    kakao_id = str(kakao_info.get("id"))
    kakao_account = kakao_info.get("kakao_account", {})
    profile = kakao_account.get("profile", {})
    username = profile.get("nickname") or "user"
    email = kakao_account.get("email") or f"{kakao_id}@kakao"

    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "SELECT id FROM users WHERE kakao_id = %s",
            (kakao_id,),
        )
        existing = cur.fetchone()
        if existing:
            user_id = existing["id"]
        else:
            cur.execute(
                "INSERT INTO users (kakao_id, username, email) VALUES (%s, %s, %s) RETURNING id",
                (kakao_id, username, email),
            )
            user_id = cur.fetchone()["id"]
            
            # 기본 설정 생성
            cur.execute(
                "INSERT INTO user_settings (user_id) VALUES (%s)",
                (user_id,)
            )
        
        # JWT 토큰 생성
        jwt_token = generate_jwt_token(user_id, username, email)
        
    return make_response({"id": user_id, "username": username, "email": email, "access_token": jwt_token}, 201)


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
      400:
        description: 잘못된 요청
      401:
        description: 인증 실패
    """
    user_id = get_current_user_id()
    data = request.get_json() or {}
    username = data.get("username")
    email = data.get("email")
    if not username and not email:
        return make_response({"error": "nothing to update"}, 400)

    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "UPDATE users SET username = COALESCE(%s, username), email = COALESCE(%s, email) WHERE id = %s RETURNING id, username, email",
            (username, email, user_id),
        )
        updated = cur.fetchone()
        if not updated:
            return make_response({"error": "user not found"}, 404)

    return make_response(dict(updated))


@bp.route("/users/profile", methods=["DELETE"])
@jwt_required
def delete_user():
    user_id = get_current_user_id()
    db = get_db()
    with db.cursor() as cur:
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        if cur.rowcount == 0:
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
        cur.execute("""
            SELECT u.id, u.username, u.email, u.points, u.level, u.experience_points,
                   ul.level_name, ul.description, ul.benefits, u.created_at
            FROM users u
            LEFT JOIN user_levels ul ON u.level = ul.level
            WHERE u.id = %s
        """, (user_id,))
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
        cur.execute("SELECT level, experience_points FROM users WHERE id = %s", (user_id,))
        user = cur.fetchone()
        if not user:
            return make_response({"error": "user not found"}, 404)
        
        new_exp = user["experience_points"] + experience_points
        
        # 새로운 레벨 계산
        cur.execute("""
            SELECT level FROM user_levels 
            WHERE required_exp <= %s 
            ORDER BY level DESC LIMIT 1
        """, (new_exp,))
        level_result = cur.fetchone()
        new_level = level_result["level"] if level_result else 1
        
        # 사용자 정보 업데이트
        cur.execute("""
            UPDATE users 
            SET experience_points = %s, level = %s 
            WHERE id = %s 
            RETURNING level, experience_points
        """, (new_exp, new_level, user_id))
        updated = cur.fetchone()
        
        level_up = new_level > user["level"]
    
    return make_response({
        "level": updated["level"],
        "experience_points": updated["experience_points"],
        "level_up": level_up
    })


@bp.route("/users/settings", methods=["GET"])
@jwt_required
def get_user_settings():
    """사용자 설정 조회"""
    user_id = get_current_user_id()
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT * FROM user_settings WHERE user_id = %s", (user_id,))
        settings = cur.fetchone()
        if not settings:
            # 기본 설정 생성
            cur.execute("""
                INSERT INTO user_settings (user_id) 
                VALUES (%s) 
                RETURNING *
            """, (user_id,))
            settings = cur.fetchone()
    
    return make_response(dict(settings))


@bp.route("/users/settings", methods=["PUT"])
@jwt_required
def update_user_settings():
    """사용자 설정 업데이트"""
    user_id = get_current_user_id()
    data = request.get_json() or {}
    
    db = get_db()
    with db.cursor() as cur:
        # 설정이 존재하는지 확인
        cur.execute("SELECT id FROM user_settings WHERE user_id = %s", (user_id,))
        existing = cur.fetchone()
        
        if existing:
            # 업데이트
            cur.execute("""
                UPDATE user_settings 
                SET notification_enabled = COALESCE(%s, notification_enabled),
                    location_sharing = COALESCE(%s, location_sharing),
                    privacy_level = COALESCE(%s, privacy_level),
                    preferences = COALESCE(%s, preferences),
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %s
                RETURNING *
            """, (
                data.get("notification_enabled"),
                data.get("location_sharing"),
                data.get("privacy_level"),
                data.get("preferences"),
                user_id
            ))
        else:
            # 생성
            cur.execute("""
                INSERT INTO user_settings 
                (user_id, notification_enabled, location_sharing, privacy_level, preferences)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING *
            """, (
                user_id,
                data.get("notification_enabled", True),
                data.get("location_sharing", False),
                data.get("privacy_level", "public"),
                data.get("preferences")
            ))
        
        updated = cur.fetchone()
    
    return make_response(dict(updated))


@bp.route("/users/verifications", methods=["GET"])
@jwt_required
def get_user_verifications():
    """사용자 인증 내역 조회"""
    user_id = get_current_user_id()
    db = get_db()
    with db.cursor() as cur:
        cur.execute("""
            SELECT * FROM user_verifications 
            WHERE user_id = %s 
            ORDER BY created_at DESC
        """, (user_id,))
        verifications = cur.fetchall()
    
    return make_response([dict(v) for v in verifications])


@bp.route("/users/verifications", methods=["POST"])
@jwt_required
def create_verification():
    """새로운 인증 요청 생성"""
    user_id = get_current_user_id()
    data = request.get_json() or {}
    verification_type = data.get("verification_type")
    source_id = data.get("source_id")
    proof_data = data.get("proof_data")
    
    if not verification_type:
        return make_response({"error": "verification_type required"}, 400)
    
    db = get_db()
    with db.cursor() as cur:
        cur.execute("""
            INSERT INTO user_verifications 
            (user_id, verification_type, source_id, proof_data)
            VALUES (%s, %s, %s, %s)
            RETURNING *
        """, (user_id, verification_type, source_id, proof_data))
        verification = cur.fetchone()
    
    return make_response(dict(verification), 201)


@bp.route("/levels", methods=["GET"])
@jwt_required
def get_all_levels():
    """모든 레벨 정보 조회"""
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT * FROM user_levels ORDER BY level")
        levels = cur.fetchall()
    
    return make_response([dict(level) for level in levels])
