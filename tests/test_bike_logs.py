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
                "INSERT INTO users (username, email) VALUES (%s, %s) RETURNING id",
                ("bikeuser", "bike@example.com"),
            )
            return cur.fetchone()["id"]


def test_bike_log_crud(client, test_user):
    # create log
    res = client.post(
        f"/users/{test_user}/bike-logs",
        json={"description": "morning ride"},
    )
    assert res.status_code == 201
    log_id = res.get_json()["id"]

    # list logs
    res = client.get(f"/users/{test_user}/bike-logs")
    assert res.status_code == 200
    logs = res.get_json()
    assert len(logs) == 1
    assert logs[0]["description"] == "morning ride"

    # update log
    res = client.put(
        f"/bike-logs/{log_id}",
        json={"description": "evening ride"},
    )
    assert res.status_code == 200
    assert res.get_json()["description"] == "evening ride"

    # delete log
    res = client.delete(f"/bike-logs/{log_id}")
    assert res.status_code == 204

    # list logs after deletion
    res = client.get(f"/users/{test_user}/bike-logs")
    assert res.status_code == 200
    assert res.get_json() == []
