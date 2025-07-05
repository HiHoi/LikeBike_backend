from __future__ import annotations

import asyncio
from typing import Any, Dict

import aiohttp
from flask import Blueprint, request

from ..utils.responses import make_response

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
    return make_response({"id": user_id, "username": username, "email": email}, 201)


@bp.route("/users/<int:user_id>", methods=["PUT"])
def update_user(user_id: int):
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


@bp.route("/users/<int:user_id>", methods=["DELETE"])
def delete_user(user_id: int):
    db = get_db()
    with db.cursor() as cur:
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        if cur.rowcount == 0:
            return make_response({"error": "user not found"}, 404)

    return make_response(None, 204)


@bp.route("/users/<int:user_id>/profile", methods=["GET"])
def get_user_profile(user_id: int):
    """사용자 프로필 정보 조회 (레벨 정보 포함)"""
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


@bp.route("/users/<int:user_id>/level", methods=["PUT"])
def update_user_level(user_id: int):
    """사용자 경험치 업데이트 및 레벨 확인"""
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


@bp.route("/users/<int:user_id>/settings", methods=["GET"])
def get_user_settings(user_id: int):
    """사용자 설정 조회"""
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


@bp.route("/users/<int:user_id>/settings", methods=["PUT"])
def update_user_settings(user_id: int):
    """사용자 설정 업데이트"""
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


@bp.route("/users/<int:user_id>/verifications", methods=["GET"])
def get_user_verifications(user_id: int):
    """사용자 인증 내역 조회"""
    db = get_db()
    with db.cursor() as cur:
        cur.execute("""
            SELECT * FROM user_verifications 
            WHERE user_id = %s 
            ORDER BY created_at DESC
        """, (user_id,))
        verifications = cur.fetchall()
    
    return make_response([dict(v) for v in verifications])


@bp.route("/users/<int:user_id>/verifications", methods=["POST"])
def create_verification(user_id: int):
    """새로운 인증 요청 생성"""
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
def get_all_levels():
    """모든 레벨 정보 조회"""
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT * FROM user_levels ORDER BY level")
        levels = cur.fetchall()
    
    return make_response([dict(level) for level in levels])
