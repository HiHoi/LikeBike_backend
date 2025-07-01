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


def test_admin_create_update_delete_news(client):
    res = client.post(
        "/admin/news",
        json={"title": "T1", "content": "C1"},
        headers={"X-Admin": "true"},
    )
    assert res.status_code == 201
    news_id = res.get_json()["data"][0]["id"]

    res = client.put(
        f"/admin/news/{news_id}",
        json={"title": "T1 updated", "content": "C2"},
        headers={"X-Admin": "true"},
    )
    assert res.status_code == 200
    assert res.get_json()["data"][0]["title"] == "T1 updated"

    res = client.delete(f"/admin/news/{news_id}", headers={"X-Admin": "true"})
    assert res.status_code == 204


def test_list_news(client):
    client.post(
        "/admin/news",
        json={"title": "T1", "content": "C1"},
        headers={"X-Admin": "true"},
    )
    client.post(
        "/admin/news",
        json={"title": "T2", "content": "C2"},
        headers={"X-Admin": "true"},
    )

    res = client.get("/news")
    assert res.status_code == 200
    assert len(res.get_json()["data"]) >= 2
