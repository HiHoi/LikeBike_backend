import pytest

from app import create_app
from app.db import get_db


@pytest.fixture
def app():
    app = create_app(
        {"TESTING": True, "DATABASE_URL": "postgresql://localhost/likebike_test"}
    )
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def test_user(app):
    with app.app_context():
        db = get_db()
        with db.cursor() as cur:
            cur.execute(
                "INSERT INTO users (kakao_id, username, email) VALUES (%s, %s, %s) RETURNING id",
                ("test_kakao_id", "bikeuser", "bike@example.com"),
            )
            return cur.fetchone()["id"]


def test_bike_log_crud(client, test_user):
    # create log with GPS data
    res = client.post(
        f"/users/{test_user}/bike-logs",
        json={
            "description": "morning ride",
            "start_latitude": 37.5665,
            "start_longitude": 126.9780,
            "end_latitude": 37.5675,
            "end_longitude": 126.9790,
            "distance": 5.2,
            "duration_minutes": 30
        },
    )
    assert res.status_code == 201
    log_data = res.get_json()["data"][0]
    log_id = log_data["id"]
    
    # 보상이 포함되어 있는지 확인
    assert "points_earned" in log_data
    assert "experience_earned" in log_data
    assert float(log_data["distance"]) == 5.2

    # list logs
    res = client.get(f"/users/{test_user}/bike-logs")
    assert res.status_code == 200
    logs = res.get_json()["data"]
    assert len(logs) == 1
    assert logs[0]["description"] == "morning ride"

    # update log
    res = client.put(
        f"/bike-logs/{log_id}",
        json={"description": "evening ride"},
    )
    assert res.status_code == 200
    assert res.get_json()["data"][0]["description"] == "evening ride"

    # delete log
    res = client.delete(f"/bike-logs/{log_id}")
    assert res.status_code == 204

    # list logs after deletion
    res = client.get(f"/users/{test_user}/bike-logs")
    assert res.status_code == 200
    assert res.get_json()["data"] == []
