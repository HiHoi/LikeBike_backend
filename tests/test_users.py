import pytest

from app import create_app
from tests.test_helpers import get_test_jwt_token, get_auth_headers
from app.db import get_db


@pytest.fixture
def app():
    return create_app(
        {"TESTING": True, "DATABASE_URL": "postgresql://localhost/likebike_test"}
    )


@pytest.fixture
def client(app):
    return app.test_client()


def test_register_user(client, monkeypatch, app):
    """사용자 등록/로그인 테스트 (JWT 토큰 발급 확인)"""

    async def fake_fetch(token: str):
        return {
            "id": 999,
            "kakao_account": {
                "email": "test@kakao.com",
                "profile": {
                    "nickname": "kakao_user",
                    "profile_image_url": "https://k.kakaocdn.net/dn/test_profile.jpg",
                },
            },
        }

    monkeypatch.setattr("app.routes.users.fetch_kakao_user_info", fake_fetch)

    res = client.post("/users", json={"access_token": "token"})
    assert res.status_code == 201
    data = res.get_json()["data"][0]
    assert "access_token" in data
    assert data["username"] == "kakao_user"
    assert data["email"] == "test@kakao.com"
    assert data["profile_image_url"] == "https://k.kakaocdn.net/dn/test_profile.jpg"


def test_update_user_profile(client, monkeypatch, app):
    """사용자 프로필 수정 테스트 (JWT 인증 필요)"""

    # 먼저 사용자 등록
    async def fake_fetch(token: str):
        return {
            "id": 999,
            "kakao_account": {
                "email": "test@kakao.com",
                "profile": {
                    "nickname": "kakao_user",
                    "profile_image_url": "https://k.kakaocdn.net/dn/test_profile.jpg",
                },
            },
        }

    monkeypatch.setattr("app.routes.users.fetch_kakao_user_info", fake_fetch)

    # 사용자 등록 후 JWT 토큰 획득
    res = client.post("/users", json={"access_token": "token"})
    user_data = res.get_json()["data"][0]
    user_id = user_data["id"]
    jwt_token = user_data["access_token"]

    # JWT 토큰으로 프로필 수정 (프로필 이미지 포함)
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Content-Type": "application/json",
    }
    res = client.put(
        "/users/profile",
        json={
            "username": "updated",
            "profile_image_url": "https://k.kakaocdn.net/dn/updated_profile.jpg",
        },
        headers=headers,
    )
    assert res.status_code == 200
    data = res.get_json()["data"][0]
    assert data["username"] == "updated"
    assert data["profile_image_url"] == "https://k.kakaocdn.net/dn/updated_profile.jpg"


def test_delete_user_profile(client, monkeypatch, app):
    """사용자 계정 삭제 테스트 (JWT 인증 필요)"""

    # 먼저 사용자 등록
    async def fake_fetch(token: str):
        return {
            "id": 999,
            "kakao_account": {
                "email": "test@kakao.com",
                "profile": {
                    "nickname": "kakao_user",
                    "profile_image_url": "https://k.kakaocdn.net/dn/test_profile.jpg",
                },
            },
        }

    monkeypatch.setattr("app.routes.users.fetch_kakao_user_info", fake_fetch)

    # 사용자 등록 후 JWT 토큰 획득
    res = client.post("/users", json={"access_token": "token"})
    jwt_token = res.get_json()["data"][0]["access_token"]

    # JWT 토큰으로 계정 삭제
    headers = {"Authorization": f"Bearer {jwt_token}"}
    res = client.delete("/users/profile", headers=headers)
    assert res.status_code == 204


def test_get_user_profile(client, monkeypatch, app):
    """사용자 프로필 조회 테스트 (JWT 인증 필요)"""

    # 먼저 사용자 등록
    async def fake_fetch(token: str):
        return {
            "id": 999,
            "kakao_account": {
                "email": "test@kakao.com",
                "profile": {
                    "nickname": "kakao_user",
                    "profile_image_url": "https://k.kakaocdn.net/dn/test_profile.jpg",
                },
            },
        }

    monkeypatch.setattr("app.routes.users.fetch_kakao_user_info", fake_fetch)

    # 사용자 등록 후 JWT 토큰 획득
    res = client.post("/users", json={"access_token": "token"})
    jwt_token = res.get_json()["data"][0]["access_token"]

    # JWT 토큰으로 프로필 조회
    headers = {"Authorization": f"Bearer {jwt_token}"}
    res = client.get("/users/profile", headers=headers)
    assert res.status_code == 200
    data = res.get_json()["data"][0]
    assert data["username"] == "kakao_user"
    assert data["email"] == "test@kakao.com"
    assert "profile_image_url" in data


def test_unauthorized_access(client):
    """JWT 토큰 없이 인증이 필요한 엔드포인트 접근 테스트"""
    # 토큰 없이 프로필 조회 시도
    res = client.get("/users/profile")
    assert res.status_code == 401
    assert "Authorization token required" in res.get_json()["data"][0]["error"]

    # 토큰 없이 프로필 수정 시도
    res = client.put("/users/profile", json={"username": "test"})
    assert res.status_code == 401

    # 토큰 없이 계정 삭제 시도
    res = client.delete("/users/profile")
    assert res.status_code == 401


def test_invalid_token_access(client):
    """잘못된 JWT 토큰으로 접근 테스트"""
    headers = {
        "Authorization": "Bearer invalid_token",
        "Content-Type": "application/json",
    }

    res = client.get("/users/profile", headers=headers)
    assert res.status_code == 401
    assert "Invalid or expired token" in res.get_json()["data"][0]["error"]


def test_logout(client, monkeypatch):
    """로그아웃 테스트"""

    # 사용자 등록
    async def fake_fetch(token: str):
        return {
            "id": 999,
            "kakao_account": {
                "email": "test@kakao.com",
                "profile": {
                    "nickname": "kakao_user",
                    "profile_image_url": "https://k.kakaocdn.net/dn/test_profile.jpg",
                },
            },
        }

    monkeypatch.setattr("app.routes.users.fetch_kakao_user_info", fake_fetch)

    res = client.post("/users", json={"access_token": "token"})
    jwt_token = res.get_json()["data"][0]["access_token"]

    # 로그아웃
    headers = {"Authorization": f"Bearer {jwt_token}"}
    res = client.post("/users/logout", headers=headers)
    assert res.status_code == 200
    assert "Successfully logged out" in res.get_json()["data"][0]["message"]


def test_token_refresh(client, monkeypatch):
    """토큰 새로고침 테스트"""
    import time

    # 사용자 등록
    async def fake_fetch(token: str):
        return {
            "id": 999,
            "kakao_account": {
                "email": "test@kakao.com",
                "profile": {
                    "nickname": "kakao_user",
                    "profile_image_url": "https://k.kakaocdn.net/dn/test_profile.jpg",
                },
            },
        }

    monkeypatch.setattr("app.routes.users.fetch_kakao_user_info", fake_fetch)

    res = client.post("/users", json={"access_token": "token"})
    old_token = res.get_json()["data"][0]["access_token"]

    # 시간을 조금 지연시켜 다른 iat를 가지도록 함
    time.sleep(1)

    # 토큰 새로고침
    headers = {"Authorization": f"Bearer {old_token}"}
    res = client.post("/users/refresh", headers=headers)
    assert res.status_code == 200
    new_token = res.get_json()["data"][0]["access_token"]
    assert new_token != old_token  # 새로운 토큰이 생성되어야 함


def test_get_user_rewards(client, monkeypatch, app):
    async def fake_fetch(token: str):
        return {
            "id": 999,
            "kakao_account": {
                "email": "test@kakao.com",
                "profile": {
                    "nickname": "kakao_user",
                    "profile_image_url": "https://k.kakaocdn.net/dn/test_profile.jpg",
                },
            },
        }

    monkeypatch.setattr("app.routes.users.fetch_kakao_user_info", fake_fetch)

    res = client.post("/users", json={"access_token": "token"})
    data = res.get_json()["data"][0]
    jwt_token = data["access_token"]
    user_id = data["id"]

    with app.app_context():
        db = get_db()
        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO rewards (user_id, source_type, points, reward_reason)
                VALUES (%s, %s, %s, %s) RETURNING id
                """,
                (user_id, "test", 5, "테스트"),
            )
            reward_id = cur.fetchone()["id"]

    headers = {"Authorization": f"Bearer {jwt_token}"}
    res = client.get("/users/rewards", headers=headers)
    assert res.status_code == 200
    rewards = res.get_json()["data"]
    assert len(rewards) == 1
    assert rewards[0]["id"] == reward_id
    assert rewards[0]["points"] == 5
