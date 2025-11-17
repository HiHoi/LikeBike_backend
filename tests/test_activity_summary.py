from datetime import datetime, timedelta, timezone

import pytest

from app import create_app
from app.db import get_db
from app.utils.auth import generate_jwt_token


@pytest.fixture
def client():
    app = create_app({"TESTING": True})
    with app.test_client() as client:
        yield client


def _insert_sample_data(app):
    with app.app_context():
        db = get_db()
        with db.cursor() as cur:
            cur.execute(
                "INSERT INTO user_levels (level, level_name, required_exp) VALUES (%s, %s, %s)"
                " ON CONFLICT (level) DO NOTHING",
                (1, "Beginner", 0),
            )
            cur.execute(
                """
                INSERT INTO users (kakao_id, username, email, level)
                VALUES (%s, %s, %s, %s)
                RETURNING id, username
                """,
                ("kakao-1", "테스트", "test@example.com", 1),
            )
            user = cur.fetchone()
            user_id = user["id"]

            now = datetime.now(timezone.utc)
            within_period = now - timedelta(days=3)
            outside_period = now - timedelta(days=20)

            quiz_rows = [
                (user_id, 1, True, within_period),
                (user_id, 2, True, within_period),
                (user_id, 3, True, within_period),
                (user_id, 4, False, within_period),
                (user_id, 5, True, outside_period),
            ]
            args_str = ",".join(["(%s, %s, %s, %s)"] * len(quiz_rows))
            cur.execute(
                f"""
                INSERT INTO user_quiz_attempts (user_id, quiz_id, is_correct, attempted_at)
                VALUES {args_str}
                """,
                [value for row in quiz_rows for value in row],
            )

            bike_rows = [
                (
                    user_id,
                    "첫 번째 라이딩",
                    "verified",
                    within_period,
                ),
                (
                    user_id,
                    "두 번째 라이딩",
                    "verified",
                    within_period,
                ),
                (
                    user_id,
                    "세 번째 라이딩",
                    "pending",
                    within_period,
                ),
                (
                    user_id,
                    "네 번째 라이딩",
                    "verified",
                    outside_period,
                ),
            ]
            args_str = ",".join(["(%s, %s, %s, %s)"] * len(bike_rows))
            cur.execute(
                f"""
                INSERT INTO bike_usage_logs (
                    user_id,
                    description,
                    verification_status,
                    created_at
                )
                VALUES {args_str}
                """,
                [value for row in bike_rows for value in row],
            )

            course_rows = [
                (
                    user_id,
                    "멋진 코스",
                    "verified",
                    200,
                    within_period,
                ),
                (
                    user_id,
                    "재미있는 코스",
                    "pending",
                    0,
                    within_period,
                ),
                (
                    user_id,
                    "오래된 코스",
                    "verified",
                    100,
                    outside_period,
                ),
            ]
            args_str = ",".join(["(%s, %s, %s, %s, %s)"] * len(course_rows))
            cur.execute(
                f"""
                INSERT INTO course_recommendations (
                    user_id,
                    title,
                    status,
                    points_awarded,
                    created_at
                )
                VALUES {args_str}
                """,
                [value for row in course_rows for value in row],
            )

    return user_id


def test_activity_summary_endpoint(client):
    app = client.application
    user_id = _insert_sample_data(app)
    token = generate_jwt_token(user_id, username="테스트", is_admin=False)

    response = client.get(
        f"/users/{user_id}/activity-summary",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    data = payload["data"][0]

    assert data["user_id"] == user_id
    assert data["quizzes"]["attempts"] == 4
    assert data["quizzes"]["correct"] == 3
    assert data["quizzes"]["accuracy"] == 75.0
    assert data["bike_logs"]["attempts"] == 3
    assert data["bike_logs"]["approved"] == 2
    assert data["course_recommendations"]["submitted"] == 2
    assert data["course_recommendations"]["approved"] == 1
    assert data["course_recommendations"]["points"] == 200
    assert "지난 2주 동안" in data["summary_text"]
    assert "정답률은 75%" in data["summary_text"]
