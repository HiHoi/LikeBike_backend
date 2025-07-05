import pytest

from app import create_app
from app.db import get_db, init_db
from tests.test_helpers import get_test_jwt_token, get_admin_jwt_token, get_auth_headers, get_admin_headers


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
                "INSERT INTO users (kakao_id, username, email, profile_image_url) VALUES (%s, %s, %s, %s) RETURNING id",
                ("test_kakao_123", "testuser", "test@example.com", "https://k.kakaocdn.net/dn/quiz_user.jpg"),
            )
            user_id = cur.fetchone()["id"]
        return user_id


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


def test_admin_create_update_delete_quiz(client, test_admin_user):
    """관리자 퀴즈 생성/수정/삭제 테스트 (JWT + X-Admin 헤더 필요)"""
    admin_headers = get_admin_headers(get_admin_jwt_token(test_admin_user, "admin", "admin@example.com"))
    
    # create
    res = client.post(
        "/admin/quizzes",
        json={"question": "Q1", "correct_answer": "A"},
        headers=admin_headers,
    )
    assert res.status_code == 201
    quiz_id = res.get_json()["data"][0]["id"]

    # update
    res = client.put(
        f"/admin/quizzes/{quiz_id}",
        json={"question": "Q1 updated", "correct_answer": "B"},
        headers=admin_headers,
    )
    assert res.status_code == 200
    assert res.get_json()["data"][0]["question"] == "Q1 updated"

    # delete
    res = client.delete(f"/admin/quizzes/{quiz_id}", headers=admin_headers)
    assert res.status_code == 204


def test_user_attempt_quiz(client, test_user, test_admin_user):
    """사용자 퀴즈 시도 테스트 (JWT 인증 필요)"""
    admin_headers = get_admin_headers(get_admin_jwt_token(test_admin_user, "admin", "admin@example.com"))
    user_headers = get_auth_headers(get_test_jwt_token(test_user, "testuser", "test@example.com"))
    
    # admin creates quiz first
    res = client.post(
        "/admin/quizzes",
        json={"question": "What?", "correct_answer": "42"},
        headers=admin_headers,
    )
    quiz_id = res.get_json()["data"][0]["id"]

    # user attempts correctly
    res = client.post(
        f"/quizzes/{quiz_id}/attempt",
        json={"answer": "42"},
        headers=user_headers,
    )
    assert res.status_code == 200
    assert res.get_json()["data"][0]["is_correct"] is True

    # user attempts wrong answer
    res = client.post(
        f"/quizzes/{quiz_id}/attempt",
        json={"answer": "0"},
        headers=user_headers,
    )
    assert res.status_code == 200
    assert res.get_json()["data"][0]["is_correct"] is False


def test_list_quizzes_requires_auth(client, test_user, test_admin_user):
    """퀴즈 목록 조회 테스트 (JWT 인증 필요)"""
    admin_headers = get_admin_headers(get_admin_jwt_token(test_admin_user, "admin", "admin@example.com"))
    user_headers = get_auth_headers(get_test_jwt_token(test_user, "testuser", "test@example.com"))
    
    # 관리자가 퀴즈 생성
    client.post(
        "/admin/quizzes",
        json={"question": "Test Question", "correct_answer": "Test Answer"},
        headers=admin_headers,
    )
    
    # 인증된 사용자는 퀴즈 목록 조회 가능
    res = client.get("/quizzes", headers=user_headers)
    assert res.status_code == 200
    assert len(res.get_json()["data"]) >= 1
    
    # 인증 없이는 접근 불가
    res = client.get("/quizzes")
    assert res.status_code == 401


def test_admin_unauthorized_access(client, test_user):
    """일반 사용자가 관리자 기능 접근 시도 테스트"""
    user_headers = get_auth_headers(get_test_jwt_token(test_user, "testuser", "test@example.com"))
    
    # X-Admin 헤더 없이 시도
    res = client.post(
        "/admin/quizzes",
        json={"question": "Test", "correct_answer": "Test"},
        headers=user_headers,
    )
    assert res.status_code == 403
    
    # 일반 사용자가 X-Admin 헤더 추가해도 실패 (토큰에 is_admin=False)
    user_headers["X-Admin"] = "true"
    res = client.post(
        "/admin/quizzes",
        json={"question": "Test", "correct_answer": "Test"},
        headers=user_headers,
    )
    assert res.status_code == 403


def test_quiz_attempt_unauthorized(client, test_admin_user):
    """인증 없이 퀴즈 시도 테스트"""
    admin_headers = get_admin_headers(get_admin_jwt_token(test_admin_user, "admin", "admin@example.com"))
    
    # 관리자가 퀴즈 생성
    res = client.post(
        "/admin/quizzes",
        json={"question": "Test", "correct_answer": "42"},
        headers=admin_headers,
    )
    quiz_id = res.get_json()["data"][0]["id"]
    
    # 인증 없이 퀴즈 시도
    res = client.post(
        f"/quizzes/{quiz_id}/attempt",
        json={"answer": "42"},
    )
    assert res.status_code == 401


def test_generate_quiz(client, monkeypatch):
    async def fake_generate(prompt, api_key):
        assert api_key == "dummy"
        assert prompt == "make a quiz"
        return {"question": "dummy q", "correct_answer": "dummy a"}

    monkeypatch.setenv("CLOVA_API_KEY", "dummy")
    monkeypatch.setattr("app.routes.quizzes._generate_from_clova", fake_generate)

    # 관리자 토큰과 헤더 생성
    admin_token = get_admin_jwt_token()
    admin_headers = get_admin_headers(admin_token)

    res = client.post(
        "/admin/quizzes/generate",
        json={"prompt": "make a quiz"},
        headers=admin_headers,
    )
    assert res.status_code == 201
    assert res.get_json()["data"][0]["question"] == "dummy q"
    assert res.get_json()["data"][0]["correct_answer"] == "dummy a"
