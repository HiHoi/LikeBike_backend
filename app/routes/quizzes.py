import asyncio
import os
from datetime import date, datetime

import aiohttp
from flask import Blueprint, request

from ..db import get_db
from ..utils.auth import admin_required, get_current_user_id, jwt_required
from ..utils.responses import make_response
from ..utils.timezone import get_kst_today

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
            - hint_link
            - explanation
            - display_date
          properties:
            question:
              type: string
              description: 퀴즈 질문
              example: "자전거 안전을 위해 반드시 착용해야 하는 것은?"
            correct_answer:
              type: string
              description: 정답
              example: "헬멧"
            hint_link:
              type: string
              description: 힌트에 대한 사이트 링크
              example: "https://example.com/hint"
            explanation:
              type: string
              description: 정답 해설
              example: "헬멧은 머리를 보호하기 위한 필수 장비입니다."
            answers:
              type: array
              description: 선택지 배열 (정답 포함)
              items:
                type: string
              example: ["모자", "선글라스", "헬멧", "장갑"]
            display_date:
              type: string
              format: date
              description: 퀴즈가 노출될 날짜
              example: "2024-01-01"
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
                  hint_link:
                    type: string
                    example: "https://example.com/hint"
                  answers:
                    type: array
                    items:
                      type: string
                    example: ["모자", "선글라스", "헬멧", "장갑"]
                  display_date:
                    type: string
                    format: date
                    example: "2024-01-01"
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
    hint_link = data.get("hint_link")
    explanation = data.get("explanation")
    display_date = data.get("display_date") or get_kst_today()

    # display_date가 문자열인 경우 date 객체로 변환
    if isinstance(display_date, str):
        try:
            display_date = datetime.fromisoformat(display_date).date()
        except ValueError:
            try:
                display_date = datetime.strptime(display_date, "%Y-%m-%d").date()
            except ValueError:
                display_date = get_kst_today()

    if not question or not correct_answer:
        return make_response({"error": "question and correct_answer required"}, 400)

    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO quizzes (question, correct_answer, answers, hint_link, explanation, display_date) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            (question, correct_answer, answers, hint_link, explanation, display_date),
        )
        quiz_id = cur.fetchone()["id"]

    return make_response(
        {
            "id": quiz_id,
            "question": question,
            "hint_link": hint_link,
            "correct_answer": correct_answer,
            "answers": answers,
            "explanation": explanation,
            "display_date": display_date.isoformat(),
        },
        201,
    )


@bp.route("/admin/quizzes/<int:quiz_id>", methods=["PUT"])
@admin_required
def update_quiz(quiz_id):
    """
    퀴즈 수정 (관리자)
    ---
    tags:
      - Quizzes
    summary: 기존 퀴즈 수정 (관리자 전용)
    description: 관리자 권한으로 기존 퀴즈 정보를 수정합니다.
    security:
      - JWT: []
      - AdminHeader: []
    parameters:
      - in: path
        name: quiz_id
        required: true
        type: integer
        description: 수정할 퀴즈 ID
        example: 1
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - question
            - correct_answer
            - answers
            - hint_link
            - explanation
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
            hint_link:
              type: string
              description: 힌트에 대한 사이트 링크
              example: "https://example.com/hint"
            explanation:
              type: string
              description: 정답 해설
              example: "헬멧은 머리를 보호하기 위한 필수 장비입니다."
    responses:
      200:
        description: 퀴즈 수정 성공
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
                  correct_answer:
                    type: string
                    example: "헬멧"
                  answers:
                    type: array
                    items:
                      type: string
                    example: ["모자", "선글라스", "헬멧", "장갑"]
                  hint_link:
                    type: string
                    example: "https://example.com/hint"
                  explanation:
                    type: string
                    example: "헬멧은 머리를 보호하기 위한 필수 장비입니다."
                  display_date:
                    type: string
                    format: date
                    example: "2024-01-01"
      400:
        description: 잘못된 요청
      401:
        description: 인증 실패
      403:
        description: 관리자 권한 필요
      404:
        description: 퀴즈를 찾을 수 없음
    """
    data = request.get_json() or {}
    question = data.get("question")
    correct_answer = data.get("correct_answer")
    answers = data.get("answers", [])
    hint_link = data.get("hint_link")
    explanation = data.get("explanation")
    if not question or not correct_answer:
        return make_response({"error": "question and correct_answer required"}, 400)

    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "UPDATE quizzes SET question = %s, correct_answer = %s, answers = %s, hint_link = %s, explanation = %s WHERE id = %s RETURNING id, question, correct_answer, answers, hint_link, explanation",
            (question, correct_answer, answers, hint_link, explanation, quiz_id),
        )
        result = cur.fetchone()
        if not result:
            return make_response({"error": "quiz not found"}, 404)

    return make_response(dict(result))


@bp.route("/admin/quizzes/<int:quiz_id>", methods=["DELETE"])
@admin_required
def delete_quiz(quiz_id):
    """
    퀴즈 삭제 (관리자)
    ---
    tags:
      - Quizzes
    summary: 기존 퀴즈 삭제 (관리자 전용)
    description: 관리자 권한으로 기존 퀴즈를 삭제합니다.
    security:
      - JWT: []
      - AdminHeader: []
    parameters:
      - in: path
        name: quiz_id
        required: true
        type: integer
        description: 삭제할 퀴즈 ID
        example: 1
    responses:
      204:
        description: 퀴즈 삭제 성공 (No Content)
      401:
        description: 인증 실패
      403:
        description: 관리자 권한 필요
      404:
        description: 퀴즈를 찾을 수 없음
        schema:
          type: object
          properties:
            error:
              type: string
              example: "quiz not found"
    """
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
                  answers:
                    type: array
                    items:
                      type: string
                    example: ["모자", "선글라스", "헬멧", "장갑"]
                  hint_link:
                    type: string
                    example: "https://example.com/hint"
                  explanation:
                    type: string
                    example: "헬멧은 머리를 보호하기 위한 필수 장비입니다."
                  display_date:
                    type: string
                    format: date
                    example: "2024-01-01"
      401:
        description: 인증 실패
    """
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "SELECT id, question, answers, hint_link, explanation, display_date FROM quizzes"
        )
        quizzes = cur.fetchall()
    for q in quizzes:
        if isinstance(q["display_date"], date):
            q["display_date"] = q["display_date"].isoformat()

    return make_response(quizzes)


@bp.route("/quizzes/today/status", methods=["GET"])
@jwt_required
def today_quiz_status():
    """
    오늘 퀴즈 시도 여부 확인
    ---
    tags:
      - Quizzes
    summary: 사용자가 오늘의 퀴즈를 풀었는지 여부 조회
    description: 오늘 날짜에 해당하는 퀴즈가 존재하면 사용자가 이미 시도했는지 반환합니다.
    security:
      - JWT: []
    responses:
      200:
        description: 시도 여부 조회 성공
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
                  attempted:
                    type: boolean
                    example: true
                  is_correct:
                    type: boolean
                    example: false
      401:
        description: 인증 실패
    """
    user_id = get_current_user_id()
    today = get_kst_today()
    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT id FROM quizzes WHERE display_date = %s", (today,))
        quiz = cur.fetchone()
        if not quiz:
            return make_response({"attempted": False, "is_correct": False})

        cur.execute(
            "SELECT bool_or(is_correct) AS is_correct, COUNT(*) > 0 AS attempted "
            "FROM user_quiz_attempts WHERE user_id = %s AND quiz_id = %s",
            (user_id, quiz["id"]),
        )
        row = cur.fetchone()
        attempted = row["attempted"]
        is_correct = row["is_correct"] if attempted else False

    return make_response({"attempted": attempted, "is_correct": is_correct})


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
        cur.execute(
            """
            SELECT id FROM user_quiz_attempts 
            WHERE user_id = %s AND quiz_id = %s AND is_correct = true
        """,
            (user_id, quiz_id),
        )
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
            exp = 10  # 퀴즈 정답 시 5경험치

            # 경험치 업데이트
            cur.execute(
                """
                UPDATE users
                SET experience_points = experience_points + %s
                WHERE id = %s
                """,
                (exp, user_id),
            )

            # 보상 기록
            cur.execute(
                """
                INSERT INTO rewards
                (user_id, source_type, source_id, points, experience_points, reward_reason)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (user_id, "quiz", quiz_id, 0, exp, "자전거 안전 퀴즈"),
            )

            reward_given = True

    response_data = {"is_correct": is_correct, "reward_given": reward_given}

    if reward_given:
        response_data.update({"experience_earned": exp})

    return make_response(response_data)


@bp.route("/admin/quizzes/generate", methods=["POST"])
@admin_required
def generate_quiz():
    """
    AI 퀴즈 생성 (관리자)
    ---
    tags:
      - Quizzes
    summary: AI를 활용한 퀴즈 자동 생성 (관리자 전용)
    description: Clova X API를 사용하여 주제에 따른 퀴즈를 자동으로 생성합니다.
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
            - prompt
          properties:
            prompt:
              type: string
              description: 퀴즈 생성을 위한 주제나 키워드
              example: "자전거 안전 운행에 대한 문제"
    responses:
      200:
        description: 퀴즈 생성 성공
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
        schema:
          type: object
          properties:
            error:
              type: string
              example: "prompt required"
      401:
        description: 인증 실패
      403:
        description: 관리자 권한 필요
      500:
        description: 서버 설정 오류
        schema:
          type: object
          properties:
            error:
              type: string
              example: "CLOVA_API_KEY not set"
      502:
        description: 외부 API 호출 실패
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Failed to call Clova X"
    """
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
