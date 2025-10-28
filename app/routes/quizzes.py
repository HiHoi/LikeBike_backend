import asyncio
import os
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Sequence

import aiohttp
from psycopg2.extras import Json
from flask import Blueprint, request

from ..db import get_db
from ..utils.auth import admin_required, get_current_user_id, jwt_required
from ..utils.responses import make_response
from ..utils.timezone import get_kst_today

bp = Blueprint("quizzes", __name__)

CLOVA_API_URL = "https://clovastudio.apigw.ntruss.com/testapp/v1/chat/completions"
ALLOWED_QUIZ_TYPES = {"select", "ox", "input"}


_HINT_DESCRIPTION_SUPPORTED: Optional[bool] = None


def _quizzes_supports_hint_description(connection) -> bool:
    """Return whether the quizzes table includes the hint_description column."""

    global _HINT_DESCRIPTION_SUPPORTED
    if _HINT_DESCRIPTION_SUPPORTED is not None:
        return _HINT_DESCRIPTION_SUPPORTED

    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = 'quizzes'
              AND column_name = 'hint_description'
            LIMIT 1
            """
        )
        _HINT_DESCRIPTION_SUPPORTED = cur.fetchone() is not None

    return _HINT_DESCRIPTION_SUPPORTED


def _normalize_input_payload(answers: Any, correct_answer: str) -> Dict[str, Any]:
    if answers is None:
        accepted_answers: List[str] = []
        case_sensitive = False
    elif isinstance(answers, dict):
        accepted_answers = [
            str(value)
            for value in answers.get("accepted_answers", [])
            if isinstance(value, str) and value.strip()
        ]
        case_sensitive = bool(answers.get("case_sensitive", False))
    elif isinstance(answers, Sequence) and not isinstance(answers, (str, bytes)):
        accepted_answers = [str(value) for value in answers if isinstance(value, str)]
        case_sensitive = False
    else:
        raise ValueError("answers must be a list or object when quiz_type is 'input'")

    normalized_correct = correct_answer.strip()
    if not normalized_correct:
        raise ValueError("correct_answer required")

    if normalized_correct not in accepted_answers:
        accepted_answers.append(normalized_correct)

    unique_answers = []
    seen = set()
    key_func = (lambda v: v if case_sensitive else v.casefold())
    for value in accepted_answers:
        key = key_func(value)
        if key not in seen:
            seen.add(key)
            unique_answers.append(value)

    return {"accepted_answers": unique_answers, "case_sensitive": case_sensitive}


def _evaluate_input(config: Dict[str, Any], answer: str) -> bool:
    accepted = config.get("accepted_answers", []) if isinstance(config, dict) else []
    case_sensitive = bool(config.get("case_sensitive", False)) if isinstance(config, dict) else False
    submitted = answer.strip()
    if not case_sensitive:
        submitted_key = submitted.casefold()
        return any(str(value).strip().casefold() == submitted_key for value in accepted)
    return any(str(value).strip() == submitted for value in accepted)


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
            - hint_description
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
            quiz_type:
              type: string
              enum: [select, ox, input]
              description: 퀴즈 유형
              example: select
            hint_link:
              type: string
              description: 힌트에 대한 사이트 링크
              example: "https://example.com/hint"
            hint_description:
              type: string
              description: 힌트에 대한 설명
              example: "헬멧 착용 가이드 영상"
            explanation:
              type: string
              description: 정답 해설
              example: "헬멧은 머리를 보호하기 위한 필수 장비입니다."
            answers:
              description: >-
                객관식 보기 배열 또는 단답형 허용 답안 정의.
                단답형(input)은 {"accepted_answers": [...], "case_sensitive": false}
                형식을 사용합니다.
              oneOf:
                - type: array
                  items:
                    type: string
                  example: ["헬멧", "모자", "장갑"]
                - type: object
                  properties:
                    accepted_answers:
                      type: array
                      items:
                        type: string
                      example: ["헬멧"]
                    case_sensitive:
                      type: boolean
                      example: false
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
                  quiz_type:
                    type: string
                    example: select
                  correct_answer:
                    type: string
                    example: "헬멧"
                  hint_link:
                    type: string
                    example: "https://example.com/hint"
                  hint_description:
                    type: string
                    example: "헬멧 착용 가이드 영상"
                  explanation:
                    type: string
                    example: "헬멧은 머리를 보호하기 위한 필수 장비입니다."
                  answers:
                    description: >-
                      선택지 배열 또는 단답형 허용 답안 정의.
                      단답형(input)은 {"accepted_answers": [...], "case_sensitive": false}
                      형식을 사용합니다.
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
    correct_answer = data.get("correct_answer", "")
    quiz_type_raw = data.get("quiz_type")
    if quiz_type_raw is None:
        return make_response({"error": "quiz_type is required"}, 400)
    if not isinstance(quiz_type_raw, str):
        return make_response({"error": "quiz_type must be a string"}, 400)
    quiz_type = quiz_type_raw.strip().lower()
    if not quiz_type:
        return make_response({"error": "quiz_type is required"}, 400)
    answers_payload = data.get("answers")
    hint_link = data.get("hint_link")
    hint_description = data.get("hint_description")
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

    if quiz_type not in ALLOWED_QUIZ_TYPES:
        return make_response(
            {
                "error": "quiz_type must be one of ['select', 'ox', 'input']"
            },
            400,
        )

    correct_answer = str(correct_answer).strip()

    if not question or not correct_answer:
        return make_response({"error": "question and correct_answer required"}, 400)

    try:
        if quiz_type == "select":
            if not isinstance(answers_payload, list) or len(answers_payload) < 2:
                raise ValueError("answers must include at least two choices for select quizzes")
            normalized_answers = [str(value) for value in answers_payload]
        elif quiz_type == "ox":
            normalized_correct = correct_answer.upper()
            if normalized_correct not in {"O", "X"}:
                raise ValueError("correct_answer must be 'O' or 'X' for ox quizzes")
            correct_answer = normalized_correct
            options = ["O", "X"]
            if isinstance(answers_payload, list) and {opt.upper() for opt in answers_payload} == {"O", "X"}:
                options = [value.upper() for value in answers_payload]
            normalized_answers = options
        else:
            normalized_answers = _normalize_input_payload(answers_payload, correct_answer)
    except ValueError as exc:
        return make_response({"error": str(exc)}, 400)

    db = get_db()
    supports_hint_description = _quizzes_supports_hint_description(db)
    with db.cursor() as cur:
        answers_json = Json(normalized_answers)

        if supports_hint_description:
            cur.execute(
                """
                INSERT INTO quizzes (question, quiz_type, correct_answer, answers, hint_link, hint_description, explanation, display_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    question,
                    quiz_type,
                    correct_answer,
                    answers_json,
                    hint_link,
                    hint_description,
                    explanation,
                    display_date,
                ),
            )
        else:
            cur.execute(
                """
                INSERT INTO quizzes (question, quiz_type, correct_answer, answers, hint_link, explanation, display_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    question,
                    quiz_type,
                    correct_answer,
                    answers_json,
                    hint_link,
                    explanation,
                    display_date,
                ),
            )
        quiz_id = cur.fetchone()["id"]

    return make_response(
        {
            "id": quiz_id,
            "question": question,
            "hint_link": hint_link,
            "hint_description": hint_description,
            "correct_answer": correct_answer,
            "quiz_type": quiz_type,
            "answers": normalized_answers,
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
            - hint_description
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
            hint_description:
              type: string
              description: 힌트에 대한 설명
              example: "헬멧 착용 가이드 영상"
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
                  hint_description:
                    type: string
                    example: "헬멧 착용 가이드 영상"
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
    correct_answer = data.get("correct_answer", "")
    quiz_type_raw = data.get("quiz_type")
    if quiz_type_raw is None:
        return make_response({"error": "quiz_type is required"}, 400)
    if not isinstance(quiz_type_raw, str):
        return make_response({"error": "quiz_type must be a string"}, 400)
    quiz_type = quiz_type_raw.strip().lower()
    if not quiz_type:
        return make_response({"error": "quiz_type is required"}, 400)
    answers_payload = data.get("answers")
    hint_link = data.get("hint_link")
    hint_description = data.get("hint_description")
    explanation = data.get("explanation")
    if not question or not correct_answer:
        return make_response({"error": "question and correct_answer required"}, 400)

    if quiz_type not in ALLOWED_QUIZ_TYPES:
        return make_response(
            {
                "error": "quiz_type must be one of ['select', 'ox', 'input']"
            },
            400,
        )

    correct_answer = str(correct_answer).strip()

    try:
        if quiz_type == "select":
            if not isinstance(answers_payload, list) or len(answers_payload) < 2:
                raise ValueError("answers must include at least two choices for select quizzes")
            normalized_answers = [str(value) for value in answers_payload]
        elif quiz_type == "ox":
            normalized_correct = correct_answer.upper()
            if normalized_correct not in {"O", "X"}:
                raise ValueError("correct_answer must be 'O' or 'X' for ox quizzes")
            correct_answer = normalized_correct
            options = ["O", "X"]
            if isinstance(answers_payload, list) and {opt.upper() for opt in answers_payload} == {"O", "X"}:
                options = [value.upper() for value in answers_payload]
            normalized_answers = options
        else:
            normalized_answers = _normalize_input_payload(answers_payload, correct_answer)
    except ValueError as exc:
        return make_response({"error": str(exc)}, 400)

    db = get_db()
    supports_hint_description = _quizzes_supports_hint_description(db)
    with db.cursor() as cur:
        answers_json = Json(normalized_answers)

        if supports_hint_description:
            cur.execute(
                """
                UPDATE quizzes
                SET question = %s,
                    quiz_type = %s,
                    correct_answer = %s,
                    answers = %s,
                    hint_link = %s,
                    hint_description = %s,
                    explanation = %s
                WHERE id = %s
                RETURNING id, question, quiz_type, correct_answer, answers, hint_link, hint_description, explanation
                """,
                (
                    question,
                    quiz_type,
                    correct_answer,
                    answers_json,
                    hint_link,
                    hint_description,
                    explanation,
                    quiz_id,
                ),
            )
        else:
            cur.execute(
                """
                UPDATE quizzes
                SET question = %s,
                    quiz_type = %s,
                    correct_answer = %s,
                    answers = %s,
                    hint_link = %s,
                    explanation = %s
                WHERE id = %s
                RETURNING id, question, quiz_type, correct_answer, answers, hint_link, explanation
                """,
                (
                    question,
                    quiz_type,
                    correct_answer,
                    answers_json,
                    hint_link,
                    explanation,
                    quiz_id,
                ),
            )
        result = cur.fetchone()
        if not result:
            return make_response({"error": "quiz not found"}, 404)

    updated = dict(result)
    if not supports_hint_description:
        updated["hint_description"] = hint_description
    return make_response(updated)


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
                  quiz_type:
                    type: string
                    example: select
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
                  hint_description:
                    type: string
                    example: "헬멧 착용 가이드 영상"
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
    supports_hint_description = _quizzes_supports_hint_description(db)
    with db.cursor() as cur:
        if supports_hint_description:
            cur.execute(
                """
                SELECT id, question, quiz_type, answers, hint_link, hint_description, explanation, display_date
                FROM quizzes
                ORDER BY display_date DESC, id DESC
                """
            )
        else:
            cur.execute(
                """
                SELECT id, question, quiz_type, answers, hint_link, explanation, display_date
                FROM quizzes
                ORDER BY display_date DESC, id DESC
                """
            )
        quizzes = [dict(row) for row in cur.fetchall()]
    if not supports_hint_description:
        for quiz in quizzes:
            quiz.setdefault("hint_description", None)
    for q in quizzes:
        if isinstance(q.get("display_date"), date):
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
    if answer is None:
        return make_response({"error": "answer required"}, 400)
    submitted_answer = str(answer)

    db = get_db()
    with db.cursor() as cur:
        # 퀴즈 정보 조회
        cur.execute(
            "SELECT quiz_type, correct_answer, answers FROM quizzes WHERE id = %s",
            (quiz_id,),
        )
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

        quiz_type = quiz["quiz_type"]
        correct_answer = quiz["correct_answer"]
        answers_payload = quiz.get("answers")

        if quiz_type == "select":
            is_correct = submitted_answer.strip() == correct_answer.strip()
        elif quiz_type == "ox":
            is_correct = submitted_answer.strip().upper() == correct_answer
        else:
            if isinstance(answers_payload, dict):
                input_config = answers_payload
            else:
                input_config = _normalize_input_payload(
                    answers_payload,
                    correct_answer,
                )
            is_correct = _evaluate_input(input_config, submitted_answer)

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
    answers_payload = result.get("answers")
    hint_link = result.get("hint_link")
    hint_description = result.get("hint_description")
    explanation = result.get("explanation")
    quiz_type = result.get("quiz_type", "select")

    if not question or not correct_answer:
        return make_response({"error": "invalid response from Clova X"}, 502)

    if quiz_type not in ALLOWED_QUIZ_TYPES:
        quiz_type = "select"

    correct_answer = str(correct_answer).strip()
    if not correct_answer:
        return make_response({"error": "invalid response from Clova X"}, 502)

    try:
        if quiz_type == "select":
            normalized_answers = answers_payload if isinstance(answers_payload, list) else []
        elif quiz_type == "ox":
            correct_answer = correct_answer.strip().upper()
            normalized_answers = ["O", "X"]
        else:
            normalized_answers = _normalize_input_payload(answers_payload, correct_answer)
    except ValueError:
        quiz_type = "select"
        normalized_answers = []
        correct_answer = str(correct_answer)

    db = get_db()
    supports_hint_description = _quizzes_supports_hint_description(db)
    with db.cursor() as cur:
        answers_json = Json(normalized_answers)

        if supports_hint_description:
            cur.execute(
                """
                INSERT INTO quizzes (question, quiz_type, correct_answer, answers, hint_link, hint_description, explanation)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    question,
                    quiz_type,
                    str(correct_answer),
                    answers_json,
                    hint_link,
                    hint_description,
                    explanation,
                ),
            )
        else:
            cur.execute(
                """
                INSERT INTO quizzes (question, quiz_type, correct_answer, answers, hint_link, explanation)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    question,
                    quiz_type,
                    str(correct_answer),
                    answers_json,
                    hint_link,
                    explanation,
                ),
            )
        quiz_id = cur.fetchone()["id"]

    return make_response(
        {
            "id": quiz_id,
            "question": question,
            "quiz_type": quiz_type,
            "correct_answer": str(correct_answer),
            "answers": normalized_answers,
            "hint_link": hint_link,
            "hint_description": hint_description,
            "explanation": explanation,
        },
        201,
    )
