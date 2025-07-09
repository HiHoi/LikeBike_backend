import pytest
import io
from unittest.mock import patch, MagicMock

from app import create_app
from app.db import get_db
from tests.test_helpers import get_test_jwt_token, get_auth_headers, get_admin_headers


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
                "INSERT INTO users (kakao_id, username, email, profile_image_url) VALUES (%s, %s, %s, %s) RETURNING id",
                ("test_kakao_id", "bikeuser", "bike@example.com", "https://k.kakaocdn.net/dn/test.jpg"),
            )
            return cur.fetchone()["id"]


@pytest.fixture
def admin_user(app):
    with app.app_context():
        db = get_db()
        with db.cursor() as cur:
            cur.execute(
                "INSERT INTO users (kakao_id, username, email, profile_image_url, is_admin) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                ("admin_kakao_id", "admin", "admin@example.com", "https://k.kakaocdn.net/dn/admin.jpg", True),
            )
            return cur.fetchone()["id"]


def create_fake_image():
    """테스트용 가짜 이미지 파일 생성"""
    return (io.BytesIO(b"fake image data"), "test_image.jpg")


@patch('app.routes.bike_logs.upload_file_to_ncp')
def test_create_bike_log_success(mock_upload, client, test_user):
    """자전거 활동 기록 생성 성공 테스트"""
    # Mock 파일 업로드 성공
    mock_upload.side_effect = [
        ("https://test.com/bike.jpg", None),  # 자전거 사진
        ("https://test.com/safety.jpg", None)  # 안전 장비 사진
    ]
    
    token = get_test_jwt_token(test_user, f"user_{test_user}", f"user{test_user}@example.com")
    headers = get_auth_headers(token)
    
    bike_photo, _ = create_fake_image()
    safety_photo, _ = create_fake_image()
    
    res = client.post(
        "/users/bike-logs",
        data={
            "description": "한강 라이딩",
            "bike_photo": (bike_photo, "bike.jpg"),
            "safety_gear_photo": (safety_photo, "safety.jpg")
        },
        headers=headers,
        content_type='multipart/form-data'
    )
    
    assert res.status_code == 201
    data = res.get_json()["data"][0]  # 첫 번째 요소 접근
    
    assert data["description"] == "한강 라이딩"
    assert data["bike_photo_url"] == "https://test.com/bike.jpg"
    assert data["safety_gear_photo_url"] == "https://test.com/safety.jpg"
    assert data["verification_status"] == "pending"
    assert "started_at" in data
    assert mock_upload.call_count == 2


def test_create_bike_log_missing_description(client, test_user):
    """설명 누락 시 실패 테스트"""
    token = get_test_jwt_token(test_user, f"user_{test_user}", f"user{test_user}@example.com")
    headers = get_auth_headers(token)
    
    bike_photo, _ = create_fake_image()
    safety_photo, _ = create_fake_image()
    
    res = client.post(
        "/users/bike-logs",
        data={
            "bike_photo": (bike_photo, "bike.jpg"),
            "safety_gear_photo": (safety_photo, "safety.jpg")
        },
        headers=headers,
        content_type='multipart/form-data'
    )
    
    assert res.status_code == 400
    assert "description required" in res.get_json()["data"][0]["error"]


def test_create_bike_log_missing_photos(client, test_user):
    """사진 누락 시 실패 테스트"""
    token = get_test_jwt_token(test_user, f"user_{test_user}", f"user{test_user}@example.com")
    headers = get_auth_headers(token)
    
    res = client.post(
        "/users/bike-logs",
        data={"description": "테스트 라이딩"},
        headers=headers,
        content_type='multipart/form-data'
    )
    
    assert res.status_code == 400
    assert "bike_photo and safety_gear_photo required" in res.get_json()["data"][0]["error"]


@patch('app.routes.bike_logs.upload_file_to_ncp')
def test_create_bike_log_upload_failure(mock_upload, client, test_user):
    """파일 업로드 실패 테스트"""
    # Mock 파일 업로드 실패
    mock_upload.return_value = (None, "업로드 실패")
    
    token = get_test_jwt_token(test_user, f"user_{test_user}", f"user{test_user}@example.com")
    headers = get_auth_headers(token)
    
    bike_photo, _ = create_fake_image()
    safety_photo, _ = create_fake_image()
    
    res = client.post(
        "/users/bike-logs",
        data={
            "description": "테스트 라이딩",
            "bike_photo": (bike_photo, "bike.jpg"),
            "safety_gear_photo": (safety_photo, "safety.jpg")
        },
        headers=headers,
        content_type='multipart/form-data'
    )
    
    assert res.status_code == 500
    assert "업로드 실패" in res.get_json()["data"][0]["error"]


@patch('app.routes.bike_logs.upload_file_to_ncp')
def test_get_user_bike_logs(mock_upload, client, test_user):
    """사용자 활동 기록 조회 테스트"""
    # Mock 파일 업로드 성공
    mock_upload.side_effect = [
        ("https://test.com/bike1.jpg", None),
        ("https://test.com/safety1.jpg", None),
        ("https://test.com/bike2.jpg", None),
        ("https://test.com/safety2.jpg", None)
    ]
    
    token = get_test_jwt_token(test_user, f"user_{test_user}", f"user{test_user}@example.com")
    headers = get_auth_headers(token)
    
    # 두 개의 활동 기록 생성
    for i in range(2):
        bike_photo, _ = create_fake_image()
        safety_photo, _ = create_fake_image()
        
        client.post(
            "/users/bike-logs",
            data={
                "description": f"라이딩 {i+1}",
                "bike_photo": (bike_photo, f"bike{i+1}.jpg"),
                "safety_gear_photo": (safety_photo, f"safety{i+1}.jpg")
            },
            headers=headers,
            content_type='multipart/form-data'
        )
    
    # 전체 목록 조회
    res = client.get("/users/bike-logs", headers=headers)
    assert res.status_code == 200
    logs = res.get_json()["data"]
    assert len(logs) == 2
    
    # 상태별 필터링 조회
    res = client.get("/users/bike-logs?status=pending", headers=headers)
    assert res.status_code == 200
    logs = res.get_json()["data"]
    assert len(logs) == 2
    assert all(log["verification_status"] == "pending" for log in logs)


def test_get_user_bike_logs_auth_required(client):
    """인증 없이 활동 기록 조회 실패 테스트"""
    res = client.get("/users/bike-logs")
    assert res.status_code == 401


@patch('app.routes.bike_logs.upload_file_to_ncp')
def test_get_bike_log_detail(mock_upload, client, test_user):
    """활동 기록 상세 조회 테스트"""
    # Mock 파일 업로드 성공
    mock_upload.side_effect = [
        ("https://test.com/bike.jpg", None),
        ("https://test.com/safety.jpg", None)
    ]
    
    token = get_test_jwt_token(test_user, f"user_{test_user}", f"user{test_user}@example.com")
    headers = get_auth_headers(token)
    
    # 활동 기록 생성
    bike_photo, _ = create_fake_image()
    safety_photo, _ = create_fake_image()
    
    res = client.post(
        "/users/bike-logs",
        data={
            "description": "상세 조회 테스트",
            "bike_photo": (bike_photo, "bike.jpg"),
            "safety_gear_photo": (safety_photo, "safety.jpg")
        },
        headers=headers,
        content_type='multipart/form-data'
    )
    
    log_id = res.get_json()["data"][0]["id"]
    
    # 상세 조회
    res = client.get(f"/users/bike-logs/{log_id}", headers=headers)
    assert res.status_code == 200
    data = res.get_json()["data"][0]
    assert data["description"] == "상세 조회 테스트"
    assert data["verification_status"] == "pending"


def test_get_bike_log_detail_not_found(client, test_user):
    """존재하지 않는 활동 기록 조회 테스트"""
    token = get_test_jwt_token(test_user, f"user_{test_user}", f"user{test_user}@example.com")
    headers = get_auth_headers(token)
    
    res = client.get("/users/bike-logs/99999", headers=headers)
    assert res.status_code == 404


def test_get_pending_bike_logs_admin(client, admin_user):
    """관리자용 검증 대기 목록 조회 테스트"""
    token = get_test_jwt_token(admin_user, "admin", "admin@example.com", is_admin=True)
    headers = get_admin_headers(token)
    
    res = client.get("/admin/bike-logs", headers=headers)
    assert res.status_code == 200
    assert "data" in res.get_json()


def test_get_pending_bike_logs_non_admin(client, test_user):
    """비관리자 검증 대기 목록 조회 실패 테스트"""
    token = get_test_jwt_token(test_user, f"user_{test_user}", f"user{test_user}@example.com")
    headers = get_auth_headers(token)
    
    res = client.get("/admin/bike-logs", headers=headers)
    assert res.status_code == 403


@patch('app.routes.bike_logs.upload_file_to_ncp')
def test_verify_bike_log_success(mock_upload, client, test_user, admin_user):
    """활동 기록 검증 성공 테스트"""
    # Mock 파일 업로드 성공
    mock_upload.side_effect = [
        ("https://test.com/bike.jpg", None),
        ("https://test.com/safety.jpg", None)
    ]
    
    # 사용자 토큰으로 활동 기록 생성
    user_token = get_test_jwt_token(test_user, f"user_{test_user}", f"user{test_user}@example.com")
    user_headers = get_auth_headers(user_token)
    
    bike_photo, _ = create_fake_image()
    safety_photo, _ = create_fake_image()
    
    res = client.post(
        "/users/bike-logs",
        data={
            "description": "검증 테스트",
            "bike_photo": (bike_photo, "bike.jpg"),
            "safety_gear_photo": (safety_photo, "safety.jpg")
        },
        headers=user_headers,
        content_type='multipart/form-data'
    )
    
    log_id = res.get_json()["data"][0]["id"]
    
    # 관리자 토큰으로 검증
    admin_token = get_test_jwt_token(admin_user, "admin", "admin@example.com", is_admin=True)
    admin_headers = get_admin_headers(admin_token)
    
    res = client.post(
        f"/admin/bike-logs/{log_id}/verify",
        json={
            "status": "verified",
            "points": 10,
            "admin_notes": "안전 장비 착용 확인됨"
        },
        headers=admin_headers
    )
    
    assert res.status_code == 200
    data = res.get_json()["data"][0]
    assert data["verification_status"] == "verified"
    assert data["points_awarded"] == 10
    assert data["admin_notes"] == "안전 장비 착용 확인됨"
    assert "verified_at" in data


@patch('app.routes.bike_logs.upload_file_to_ncp')
def test_verify_bike_log_reject(mock_upload, client, test_user, admin_user):
    """활동 기록 거부 테스트"""
    # Mock 파일 업로드 성공
    mock_upload.side_effect = [
        ("https://test.com/bike.jpg", None),
        ("https://test.com/safety.jpg", None)
    ]
    
    # 사용자 토큰으로 활동 기록 생성
    user_token = get_test_jwt_token(test_user, f"user_{test_user}", f"user{test_user}@example.com")
    user_headers = get_auth_headers(user_token)
    
    bike_photo, _ = create_fake_image()
    safety_photo, _ = create_fake_image()
    
    res = client.post(
        "/users/bike-logs",
        data={
            "description": "거부 테스트",
            "bike_photo": (bike_photo, "bike.jpg"),
            "safety_gear_photo": (safety_photo, "safety.jpg")
        },
        headers=user_headers,
        content_type='multipart/form-data'
    )
    
    log_id = res.get_json()["data"][0]["id"]
    
    # 관리자 토큰으로 거부
    admin_token = get_test_jwt_token(admin_user, "admin", "admin@example.com", is_admin=True)
    admin_headers = get_admin_headers(admin_token)
    
    res = client.post(
        f"/admin/bike-logs/{log_id}/verify",
        json={
            "status": "rejected",
            "admin_notes": "안전 장비 미착용"
        },
        headers=admin_headers
    )
    
    assert res.status_code == 200
    data = res.get_json()["data"][0]
    assert data["verification_status"] == "rejected"
    assert data["points_awarded"] == 0
    assert data["admin_notes"] == "안전 장비 미착용"


def test_verify_bike_log_invalid_status(client, admin_user):
    """잘못된 검증 상태 테스트"""
    admin_token = get_test_jwt_token(admin_user, "admin", "admin@example.com", is_admin=True)
    admin_headers = get_admin_headers(admin_token)
    
    res = client.post(
        "/admin/bike-logs/1/verify",
        json={
            "status": "invalid_status",
            "points": 10
        },
        headers=admin_headers
    )
    
    assert res.status_code == 400
    assert "status must be 'verified' or 'rejected'" in res.get_json()["data"][0]["error"]


def test_verify_bike_log_missing_points(client, admin_user):
    """승인 시 포인트 누락 테스트"""
    admin_token = get_test_jwt_token(admin_user, "admin", "admin@example.com", is_admin=True)
    admin_headers = get_admin_headers(admin_token)
    
    res = client.post(
        "/admin/bike-logs/1/verify",
        json={
            "status": "verified",
            "points": 0
        },
        headers=admin_headers
    )
    
    assert res.status_code == 400
    assert "points must be greater than 0" in res.get_json()["data"][0]["error"]


def test_verify_bike_log_not_found(client, admin_user):
    """존재하지 않는 활동 기록 검증 테스트"""
    admin_token = get_test_jwt_token(admin_user, "admin", "admin@example.com", is_admin=True)
    admin_headers = get_admin_headers(admin_token)
    
    res = client.post(
        "/admin/bike-logs/99999/verify",
        json={
            "status": "verified",
            "points": 10
        },
        headers=admin_headers
    )
    
    assert res.status_code == 404


def test_verify_bike_log_non_admin(client, test_user):
    """비관리자 검증 시도 실패 테스트"""
    token = get_test_jwt_token(test_user, f"user_{test_user}", f"user{test_user}@example.com")
    headers = get_auth_headers(token)
    
    res = client.post(
        "/admin/bike-logs/1/verify",
        json={
            "status": "verified",
            "points": 10
        },
        headers=headers
    )
    
    assert res.status_code == 403


def test_bike_log_auth_required(client):
    """인증 없이 API 호출 실패 테스트"""
    # 활동 기록 생성
    res = client.post("/users/bike-logs")
    assert res.status_code == 401
    
    # 활동 기록 조회
    res = client.get("/users/bike-logs")
    assert res.status_code == 401
    
    # 활동 기록 상세 조회
    res = client.get("/users/bike-logs/1")
    assert res.status_code == 401
    
    # 관리자 API
    res = client.get("/admin/bike-logs")
    assert res.status_code == 401
    
    res = client.post("/admin/bike-logs/1/verify")
    assert res.status_code == 401
