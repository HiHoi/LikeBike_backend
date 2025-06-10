import pytest

from app import create_app


@pytest.fixture
def client():
    app = create_app({"TESTING": True, "DATABASE": ":memory:"})
    with app.test_client() as client:
        yield client


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


def test_user_attempt_quiz(client):
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
        json={"user_id": 1, "answer": "42"},
    )
    assert res.status_code == 200
    assert res.get_json()["is_correct"] is True

    # user attempts wrong answer
    res = client.post(
        f"/quizzes/{quiz_id}/attempt",
        json={"user_id": 1, "answer": "0"},
    )
    assert res.status_code == 200
    assert res.get_json()["is_correct"] is False
