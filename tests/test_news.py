import pytest

from app import create_app
from app.db import get_db
from tests.test_helpers import get_test_jwt_token, get_admin_jwt_token, get_auth_headers, get_admin_headers


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
def test_admin_user(app):
    """테스트용 관리자 사용자 생성"""
    with app.app_context():
        db = get_db()
        with db.cursor() as cur:
            cur.execute(
                "INSERT INTO users (kakao_id, username, email, profile_image_url, is_admin) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                ("admin_kakao_999", "admin", "admin@example.com", "https://k.kakaocdn.net/dn/admin.jpg", True),
            )
            user_id = cur.fetchone()["id"]
        return user_id


@pytest.fixture
def test_user(app):
    """테스트용 일반 사용자 생성"""
    with app.app_context():
        db = get_db()
        with db.cursor() as cur:
            cur.execute(
                "INSERT INTO users (kakao_id, username, email, profile_image_url) VALUES (%s, %s, %s, %s) RETURNING id",
                ("test_kakao_123", "testuser", "test@example.com", "https://k.kakaocdn.net/dn/user.jpg"),
            )
            user_id = cur.fetchone()["id"]
        return user_id


def test_admin_create_update_delete_news(client, test_admin_user):
    """관리자 뉴스 생성/수정/삭제 테스트 (JWT + X-Admin 헤더 필요)"""
    admin_headers = get_admin_headers(get_admin_jwt_token(test_admin_user, "admin", "admin@example.com"))
    
    res = client.post(
        "/admin/news",
        json={"title": "T1", "content": "C1"},
        headers=admin_headers,
    )
    assert res.status_code == 201
    news_id = res.get_json()["data"][0]["id"]

    res = client.put(
        f"/admin/news/{news_id}",
        json={"title": "T1 updated", "content": "C2"},
        headers=admin_headers,
    )
    assert res.status_code == 200
    assert res.get_json()["data"][0]["title"] == "T1 updated"

    res = client.delete(f"/admin/news/{news_id}", headers=admin_headers)
    assert res.status_code == 204


def test_list_news(client, test_admin_user, test_user):
    """뉴스 목록 조회 테스트 (JWT 인증 필요)"""
    admin_headers = get_admin_headers(get_admin_jwt_token(test_admin_user, "admin", "admin@example.com"))
    user_headers = get_auth_headers(get_test_jwt_token(test_user, "testuser", "test@example.com"))
    
    client.post(
        "/admin/news",
        json={"title": "T1", "content": "C1"},
        headers=admin_headers,
    )
    client.post(
        "/admin/news",
        json={"title": "T2", "content": "C2"},
        headers=admin_headers,
    )

    # 인증된 사용자는 뉴스 목록 조회 가능
    res = client.get("/news", headers=user_headers)
    assert res.status_code == 200
    assert len(res.get_json()["data"]) >= 2
    
    # 인증 없이는 접근 불가
    res = client.get("/news")
    assert res.status_code == 401


def test_get_news_detail(client, test_admin_user, test_user):
    """뉴스 상세 조회 테스트 (JWT 인증 필요)"""
    admin_headers = get_admin_headers(get_admin_jwt_token(test_admin_user, "admin", "admin@example.com"))
    user_headers = get_auth_headers(get_test_jwt_token(test_user, "testuser", "test@example.com"))
    
    # 관리자가 뉴스 생성
    res = client.post(
        "/admin/news",
        json={"title": "Test News", "content": "Test Content"},
        headers=admin_headers,
    )
    news_id = res.get_json()["data"][0]["id"]
    
    # 인증된 사용자는 뉴스 상세 조회 가능
    res = client.get(f"/news/{news_id}", headers=user_headers)
    assert res.status_code == 200
    assert res.get_json()["data"][0]["title"] == "Test News"
    
    # 인증 없이는 접근 불가
    res = client.get(f"/news/{news_id}")
    assert res.status_code == 401


def test_admin_unauthorized_access(client, test_user):
    """일반 사용자가 관리자 뉴스 기능 접근 시도 테스트"""
    user_headers = get_auth_headers(get_test_jwt_token(test_user, "testuser", "test@example.com"))
    
    # X-Admin 헤더 없이 시도
    res = client.post(
        "/admin/news",
        json={"title": "Test", "content": "Test"},
        headers=user_headers,
    )
    assert res.status_code == 403
    
    # 일반 사용자가 X-Admin 헤더 추가해도 실패
    user_headers["X-Admin"] = "true"
    res = client.post(
        "/admin/news",
        json={"title": "Test", "content": "Test"},
        headers=user_headers,
    )
    assert res.status_code == 403
