import pytest

from app import create_app


@pytest.fixture
def app():
    return create_app(
        {"TESTING": True, "DATABASE_URL": "postgresql://localhost/likebike_test"}
    )


@pytest.fixture
def client(app):
    return app.test_client()


def test_register_update_delete_user(client, monkeypatch, app):
    async def fake_fetch(token: str):
        return {
            "id": 999,
            "kakao_account": {
                "email": "test@kakao.com",
                "profile": {"nickname": "kakao_user"},
            },
        }

    monkeypatch.setattr("app.routes.users.fetch_kakao_user_info", fake_fetch)

    res = client.post("/users", json={"access_token": "token"})
    assert res.status_code == 201
    user_id = res.get_json()["data"][0]["id"]

    res = client.put(f"/users/{user_id}", json={"username": "updated"})
    assert res.status_code == 200
    assert res.get_json()["data"][0]["username"] == "updated"

    res = client.delete(f"/users/{user_id}")
    assert res.status_code == 204
