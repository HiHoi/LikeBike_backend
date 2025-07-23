import io
from unittest.mock import patch

import pytest

from app import create_app
from app.db import get_db
from tests.test_helpers import (get_admin_headers, get_auth_headers,
                                get_test_jwt_token)


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
                (
                    "test_kakao_id",
                    "testuser",
                    "test@example.com",
                    "https://k.kakaocdn.net/dn/test.jpg",
                ),
            )
            return cur.fetchone()["id"]


@pytest.fixture
def admin_user(app):
    with app.app_context():
        db = get_db()
        with db.cursor() as cur:
            cur.execute(
                "INSERT INTO users (kakao_id, username, email, profile_image_url, is_admin) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (
                    "admin_kakao",
                    "admin",
                    "admin@example.com",
                    "https://k.kakaocdn.net/dn/admin.jpg",
                    True,
                ),
            )
            return cur.fetchone()["id"]


def create_fake_image():
    return (io.BytesIO(b"fake"), "photo.jpg")


@patch("app.routes.recommendations.upload_file_to_ncp")
def test_create_and_list_recommendations(mock_upload, client, test_user):
    mock_upload.return_value = ("https://test.com/photo.jpg", None)
    token = get_test_jwt_token(
        test_user, f"user_{test_user}", f"user{test_user}@example.com"
    )
    headers = get_auth_headers(token)

    img, _ = create_fake_image()
    res = client.post(
        "/users/course-recommendations",
        data={
            "location_name": "한강",
            "review": "멋진 코스",
            "photo": (img, "photo.jpg"),
        },
        headers=headers,
        content_type="multipart/form-data",
    )
    assert res.status_code == 201

    res = client.get("/users/course-recommendations", headers=headers)
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert len(data) == 1
    assert data[0]["location_name"] == "한강"


@patch("app.routes.recommendations.upload_file_to_ncp")
def test_verify_recommendation(mock_upload, client, test_user, admin_user):
    mock_upload.return_value = ("https://test.com/photo.jpg", None)
    user_token = get_test_jwt_token(
        test_user, f"user_{test_user}", f"user{test_user}@example.com"
    )
    user_headers = get_auth_headers(user_token)

    img, _ = create_fake_image()
    res = client.post(
        "/users/course-recommendations",
        data={
            "location_name": "한강",
            "review": "멋진 코스",
            "photo": (img, "photo.jpg"),
        },
        headers=user_headers,
        content_type="multipart/form-data",
    )
    rec_id = res.get_json()["data"][0]["id"]

    admin_token = get_test_jwt_token(
        admin_user, "admin", "admin@example.com", is_admin=True
    )
    admin_headers = get_admin_headers(admin_token)

    res = client.post(
        f"/admin/course-recommendations/{rec_id}/verify",
        json={"status": "approved", "points": 5},
        headers=admin_headers,
    )
    assert res.status_code == 200
    data = res.get_json()["data"][0]
    assert data["status"] == "approved"
    assert data["points_awarded"] == 5


@patch("app.routes.recommendations.upload_file_to_ncp")
def test_daily_recommendation_limit(mock_upload, client, test_user):
    mock_upload.return_value = ("https://test.com/photo.jpg", None)
    token = get_test_jwt_token(
        test_user, f"user_{test_user}", f"user{test_user}@example.com"
    )
    headers = get_auth_headers(token)

    for i in range(2):
        img, _ = create_fake_image()
        res = client.post(
            "/users/course-recommendations",
            data={
                "location_name": f"코스{i}",
                "review": "굿",
                "photo": (img, f"p{i}.jpg"),
            },
            headers=headers,
            content_type="multipart/form-data",
        )
        assert res.status_code == 201

    img, _ = create_fake_image()
    res = client.post(
        "/users/course-recommendations",
        data={
            "location_name": "코스3",
            "review": "굿",
            "photo": (img, "p3.jpg"),
        },
        headers=headers,
        content_type="multipart/form-data",
    )
    assert res.status_code == 400
    assert "daily course recommendation limit" in res.get_json()["data"][0]["error"]


@patch("app.routes.recommendations.upload_file_to_ncp")
def test_admin_list_all_recommendations(mock_upload, client, test_user, admin_user):
    """관리자가 모든 추천 코스를 조회할 수 있는지 확인"""
    mock_upload.return_value = ("https://test.com/photo.jpg", None)

    user_token = get_test_jwt_token(
        test_user, f"user_{test_user}", f"user{test_user}@example.com"
    )
    user_headers = get_auth_headers(user_token)

    img, _ = create_fake_image()
    client.post(
        "/users/course-recommendations",
        data={
            "location_name": "한강",
            "review": "멋진 코스",
            "photo": (img, "photo.jpg"),
        },
        headers=user_headers,
        content_type="multipart/form-data",
    )

    admin_token = get_test_jwt_token(
        admin_user, "admin", "admin@example.com", is_admin=True
    )
    admin_headers = get_admin_headers(admin_token)

    res = client.get("/admin/course-recommendations", headers=admin_headers)
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert len(data) >= 1


def test_admin_list_requires_privileges(client, test_user):
    """관리자 권한 없이 모든 코스 추천을 조회할 수 없는지 확인"""
    token = get_test_jwt_token(test_user, "user", "user@example.com")
    headers = get_auth_headers(token)

    res = client.get("/admin/course-recommendations", headers=headers)
    assert res.status_code in (401, 403)


@patch("app.routes.recommendations.upload_file_to_ncp")
def test_today_recommendation_count(mock_upload, client, test_user):
    mock_upload.return_value = ("https://test.com/photo.jpg", None)
    token = get_test_jwt_token(
        test_user, f"user_{test_user}", f"user{test_user}@example.com"
    )
    headers = get_auth_headers(token)

    res = client.get("/users/course-recommendations/today/count", headers=headers)
    assert res.status_code == 200
    assert res.get_json()["data"][0]["count"] == 0

    img, _ = create_fake_image()
    client.post(
        "/users/course-recommendations",
        data={
            "location_name": "한강",
            "review": "굿",
            "photo": (img, "p.jpg"),
        },
        headers=headers,
        content_type="multipart/form-data",
    )

    res = client.get("/users/course-recommendations/today/count", headers=headers)
    assert res.status_code == 200
    assert res.get_json()["data"][0]["count"] == 1
