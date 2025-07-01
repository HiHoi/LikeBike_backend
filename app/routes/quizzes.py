import asyncio
import os

import aiohttp
from flask import Blueprint, request

from ..utils.responses import make_response

from ..db import get_db

bp = Blueprint("quizzes", __name__)

CLOVA_API_URL = "https://clovastudio.apigw.ntruss.com/testapp/v1/chat/completions"


async def _generate_from_clova(prompt: str, api_key: str) -> dict:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {"prompt": prompt}
    async with aiohttp.ClientSession() as session:
        async with session.post(CLOVA_API_URL, headers=headers, json=payload) as resp:
            resp.raise_for_status()
            return await resp.json()


def _require_admin():
    if request.headers.get("X-Admin") != "true":
        return make_response({"error": "admin only"}, 403)
    return None


@bp.route("/admin/quizzes", methods=["POST"])
def create_quiz():
    admin_check = _require_admin()
    if admin_check:
        return admin_check
    data = request.get_json() or {}
    question = data.get("question")
    correct_answer = data.get("correct_answer")
    if not question or not correct_answer:
        return make_response({"error": "question and correct_answer required"}, 400)

    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO quizzes (question, correct_answer) VALUES (%s, %s) RETURNING id",
            (question, correct_answer),
        )
        quiz_id = cur.fetchone()["id"]

    return make_response(
        {"id": quiz_id, "question": question, "correct_answer": correct_answer},
        201,
    )


@bp.route("/admin/quizzes/<int:quiz_id>", methods=["PUT"])
def update_quiz(quiz_id):
    admin_check = _require_admin()
    if admin_check:
        return admin_check
    data = request.get_json() or {}
    question = data.get("question")
    correct_answer = data.get("correct_answer")
    if not question or not correct_answer:
        return make_response({"error": "question and correct_answer required"}, 400)

    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "UPDATE quizzes SET question = %s, correct_answer = %s WHERE id = %s RETURNING id, question, correct_answer",
            (question, correct_answer, quiz_id),
        )
        result = cur.fetchone()
        if not result:
            return make_response({"error": "quiz not found"}, 404)

    return make_response(dict(result))


@bp.route("/admin/quizzes/<int:quiz_id>", methods=["DELETE"])
def delete_quiz(quiz_id):
    admin_check = _require_admin()
    if admin_check:
        return admin_check

    db = get_db()
    with db.cursor() as cur:
        cur.execute("DELETE FROM quizzes WHERE id = %s", (quiz_id,))
        if cur.rowcount == 0:
            return make_response({"error": "quiz not found"}, 404)

    return make_response(None, 204)


@bp.route("/quizzes", methods=["GET"])
def list_quizzes():
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT id, question FROM quizzes")
        quizzes = cur.fetchall()

    return make_response(quizzes)


@bp.route("/quizzes/<int:quiz_id>/attempt", methods=["POST"])
def attempt_quiz(quiz_id):
    data = request.get_json() or {}
    user_id = data.get("user_id")
    answer = data.get("answer")
    if not user_id or not answer:
        return make_response({"error": "user_id and answer required"}, 400)

    db = get_db()
    with db.cursor() as cur:
        # 퀴즈 정보 조회
        cur.execute("SELECT correct_answer FROM quizzes WHERE id = %s", (quiz_id,))
        quiz = cur.fetchone()
        if not quiz:
            return make_response({"error": "quiz not found"}, 404)

        is_correct = answer == quiz["correct_answer"]

        # 시도 기록 저장
        cur.execute(
            "INSERT INTO user_quiz_attempts (user_id, quiz_id, is_correct) VALUES (%s, %s, %s)",
            (user_id, quiz_id, is_correct),
        )

    return make_response({"is_correct": is_correct})


@bp.route("/admin/quizzes/generate", methods=["POST"])
def generate_quiz():
    admin_check = _require_admin()
    if admin_check:
        return admin_check
    data = request.get_json() or {}
    prompt = data.get("prompt")
    if not prompt:
        return make_response({"error": "prompt required"}, 400)

    api_key = os.environ.get("CLOVA_API_KEY")
    if not api_key:
        return make_response({"error": "CLOVA_API_KEY not set"}, 500)

    try:
        result = asyncio.run(_generate_from_clova(prompt, api_key))
    except Exception:  # pragma: no cover - network errors
        return make_response({"error": "Failed to call Clova X"}, 502)

    question = result.get("question")
    correct_answer = result.get("correct_answer")
    if not question or not correct_answer:
        return make_response({"error": "invalid response from Clova X"}, 502)

    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO quizzes (question, correct_answer) VALUES (%s, %s) RETURNING id",
            (question, correct_answer),
        )
        quiz_id = cur.fetchone()["id"]

    return make_response(
        {"id": quiz_id, "question": question, "correct_answer": correct_answer},
        201,
    )
