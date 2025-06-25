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
