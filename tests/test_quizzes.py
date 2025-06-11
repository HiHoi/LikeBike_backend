import pytest

from app import create_app
from app.db import get_db, init_db


@pytest.fixture
def app():
    # 테스트용 PostgreSQL 데이터베이스 사용
    app = create_app(
        {"TESTING": True, "DATABASE_URL": "postgresql://localhost/likebike_test"}
    )

    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def test_user(app):
    """테스트용 사용자 생성"""
    with app.app_context():
        db = get_db()
        with db.cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, email) VALUES (%s, %s) RETURNING id",
                ("testuser", "test@example.com"),
            )
            user_id = cur.fetchone()["id"]
        return user_id


def test_admin_create_update_delete_quiz(client):
    # create
    res = client.post(
        "/admin/quizzes",
        json={"question": "Q1", "correct_answer": "A"},
        headers={"X-Admin": "true"},
    )
    assert res.status_code == 201
    quiz_id = res.get_json()["id"]

    # update
    res = client.put(
        f"/admin/quizzes/{quiz_id}",
        json={"question": "Q1 updated", "correct_answer": "B"},
        headers={"X-Admin": "true"},
    )
    assert res.status_code == 200
    assert res.get_json()["question"] == "Q1 updated"

    # delete
    res = client.delete(f"/admin/quizzes/{quiz_id}", headers={"X-Admin": "true"})
    assert res.status_code == 204


def test_user_attempt_quiz(client, test_user):
    # admin creates quiz first
    res = client.post(
        "/admin/quizzes",
        json={"question": "What?", "correct_answer": "42"},
        headers={"X-Admin": "true"},
    )
    quiz_id = res.get_json()["id"]

    # user attempts correctly
    res = client.post(
        f"/quizzes/{quiz_id}/attempt",
        json={"user_id": test_user, "answer": "42"},
    )
    assert res.status_code == 200
    assert res.get_json()["is_correct"] is True

    # user attempts wrong answer
    res = client.post(
        f"/quizzes/{quiz_id}/attempt",
        json={"user_id": test_user, "answer": "0"},
    )
    assert res.status_code == 200
    assert res.get_json()["is_correct"] is False


def test_generate_quiz(client, monkeypatch):
    async def fake_generate(prompt, api_key):
        assert api_key == "dummy"
        assert prompt == "make a quiz"
        return {"question": "dummy q", "correct_answer": "dummy a"}

    monkeypatch.setenv("CLOVA_API_KEY", "dummy")
    monkeypatch.setattr("app.routes.quizzes._generate_from_clova", fake_generate)

    res = client.post(
        "/admin/quizzes/generate",
        json={"prompt": "make a quiz"},
        headers={"X-Admin": "true"},
    )
    assert res.status_code == 201
    assert res.get_json()["question"] == "dummy q"
    assert res.get_json()["correct_answer"] == "dummy a"
