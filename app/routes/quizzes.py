import asyncio
import os

import aiohttp
from flask import Blueprint, request

from ..utils.responses import make_response
from ..utils.auth import jwt_required, admin_required, get_current_user_id

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


@bp.route("/admin/quizzes", methods=["POST"])
@admin_required
def create_quiz():
    """
    퀴즈 생성 (관리자)
    ---
    tags:
      - Quizzes
    summary: 새로운 퀴즈 생성 (관리자 전용)
    description: 관리자 권한으로 새로운 퀴즈를 생성합니다.
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
            - question
            - correct_answer
            - answers
          properties:
            question:
              type: string
              description: 퀴즈 질문
              example: "자전거 안전을 위해 반드시 착용해야 하는 것은?"
            correct_answer:
              type: string
              description: 정답
              example: "헬멧"
            answers:
              type: array
              description: 선택지 배열 (정답 포함)
              items:
                type: string
              example: ["모자", "선글라스", "헬멧", "장갑"]
    responses:
      201:
        description: 퀴즈 생성 성공
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
                  question:
                    type: string
                    example: "자전거 안전을 위해 반드시 착용해야 하는 것은?"
                  correct_answer:
                    type: string
                    example: "헬멧"
                  answers:
                    type: array
                    items:
                      type: string
                    example: ["모자", "선글라스", "헬멧", "장갑"]
      400:
        description: 잘못된 요청
      401:
        description: 인증 실패
      403:
        description: 관리자 권한 필요
    """
    data = request.get_json() or {}
    question = data.get("question")
    correct_answer = data.get("correct_answer")
    answers = data.get("answers", [])  # 선택지 배열
    if not question or not correct_answer:
        return make_response({"error": "question and correct_answer required"}, 400)

    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO quizzes (question, correct_answer, answers) VALUES (%s, %s, %s) RETURNING id",
            (question, correct_answer, answers),
        )
        quiz_id = cur.fetchone()["id"]

    return make_response(
        {"id": quiz_id, "question": question, "correct_answer": correct_answer, "answers": answers},
        201,
    )


@bp.route("/admin/quizzes/<int:quiz_id>", methods=["PUT"])
@admin_required
def update_quiz(quiz_id):
    data = request.get_json() or {}
    question = data.get("question")
    correct_answer = data.get("correct_answer")
    answers = data.get("answers", [])
    if not question or not correct_answer:
        return make_response({"error": "question and correct_answer required"}, 400)

    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "UPDATE quizzes SET question = %s, correct_answer = %s, answers = %s WHERE id = %s RETURNING id, question, correct_answer, answers",
            (question, correct_answer, answers, quiz_id),
        )
        result = cur.fetchone()
        if not result:
            return make_response({"error": "quiz not found"}, 404)

    return make_response(dict(result))


@bp.route("/admin/quizzes/<int:quiz_id>", methods=["DELETE"])
@admin_required
def delete_quiz(quiz_id):
    db = get_db()
    with db.cursor() as cur:
        cur.execute("DELETE FROM quizzes WHERE id = %s", (quiz_id,))
        if cur.rowcount == 0:
            return make_response({"error": "quiz not found"}, 404)

    return make_response(None, 204)


@bp.route("/quizzes", methods=["GET"])
@jwt_required
def list_quizzes():
    """
    퀴즈 목록 조회
    ---
    tags:
      - Quizzes
    summary: 사용 가능한 퀴즈 목록 조회
    description: 인증된 사용자가 시도할 수 있는 퀴즈들의 목록을 조회합니다.
    security:
      - JWT: []
    responses:
      200:
        description: 퀴즈 목록 조회 성공
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
                  question:
                    type: string
                    example: "자전거 안전을 위해 반드시 착용해야 하는 것은?"
      401:
        description: 인증 실패
    """
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT id, question FROM quizzes")
        quizzes = cur.fetchall()

    return make_response(quizzes)


@bp.route("/quizzes/<int:quiz_id>/attempt", methods=["POST"])
@jwt_required
def attempt_quiz(quiz_id):
    """
    퀴즈 시도
    ---
    tags:
      - Quizzes
    summary: 퀴즈 문제 시도
    description: 특정 퀴즈에 답을 제출하고 정답 여부에 따라 보상을 받습니다.
    security:
      - JWT: []
    parameters:
      - in: path
        name: quiz_id
        required: true
        type: integer
        description: 퀴즈 ID
        example: 1
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - answer
          properties:
            answer:
              type: string
              description: 사용자가 제출한 답
              example: "헬멧"
    responses:
      200:
        description: 퀴즈 시도 성공
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
                  is_correct:
                    type: boolean
                    example: true
                  reward_given:
                    type: boolean
                    example: true
                  points_earned:
                    type: integer
                    example: 10
                  experience_earned:
                    type: integer
                    example: 5
      400:
        description: 잘못된 요청
      401:
        description: 인증 실패
      404:
        description: 퀴즈를 찾을 수 없음
    """
    user_id = get_current_user_id()
    data = request.get_json() or {}
    answer = data.get("answer")
    if not answer:
        return make_response({"error": "answer required"}, 400)

    db = get_db()
    with db.cursor() as cur:
        # 퀴즈 정보 조회
        cur.execute("SELECT correct_answer FROM quizzes WHERE id = %s", (quiz_id,))
        quiz = cur.fetchone()
        if not quiz:
            return make_response({"error": "quiz not found"}, 404)

        # 이미 정답을 맞춘 퀴즈인지 확인
        cur.execute("""
            SELECT id FROM user_quiz_attempts 
            WHERE user_id = %s AND quiz_id = %s AND is_correct = true
        """, (user_id, quiz_id))
        already_correct = cur.fetchone()

        is_correct = answer == quiz["correct_answer"]

        # 시도 기록 저장
        cur.execute(
            "INSERT INTO user_quiz_attempts (user_id, quiz_id, is_correct) VALUES (%s, %s, %s)",
            (user_id, quiz_id, is_correct),
        )

        # 정답이고 처음 맞춘 경우 보상 지급
        reward_given = False
        if is_correct and not already_correct:
            points = 10  # 퀴즈 정답 시 10포인트
            exp = 5      # 퀴즈 정답 시 5경험치
            
            # 포인트 업데이트
            cur.execute("""
                UPDATE users 
                SET points = points + %s, experience_points = experience_points + %s 
                WHERE id = %s
            """, (points, exp, user_id))
            
            # 보상 기록
            cur.execute("""
                INSERT INTO rewards 
                (user_id, source_type, source_id, points, experience_points, reward_reason)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (user_id, "quiz", quiz_id, points, exp, "퀴즈 정답"))
            
            reward_given = True

    response_data = {
        "is_correct": is_correct,
        "reward_given": reward_given
    }
    
    if reward_given:
        response_data.update({
            "points_earned": 10,
            "experience_earned": 5
        })

    return make_response(response_data)


@bp.route("/admin/quizzes/generate", methods=["POST"])
@admin_required
def generate_quiz():
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
