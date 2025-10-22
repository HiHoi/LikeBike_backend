import io
import json
from unittest.mock import patch

import pytest

from app import create_app
from app.db import get_db
from tests.test_helpers import get_admin_headers, get_auth_headers, get_test_jwt_token


@pytest.fixture
def app():
    app = create_app(
        {"TESTING": True, "DATABASE_URL": "postgresql://localhost/likebike_test"}
    )
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def _courses_payload(
    label: str = "A코스",
    include_point_photos: bool = False,
    include_address: bool = False,
    include_point_descriptions: bool = False,
) -> str:
    points = [
        {"type": "start", "name": "출발지"},
        {"type": "finish", "name": "도착지"},
    ]

    if include_point_photos:
        for idx, point in enumerate(points, start=1):
            point["photo_field"] = f"point_photo_{idx}"

    if include_address:
        for idx, point in enumerate(points, start=1):
            point["address"] = f"서울시 테스트구 {idx}번지"

    if include_point_descriptions:
        for idx, point in enumerate(points, start=1):
            point["description"] = f"지점 설명 {idx}"

    return json.dumps(
        [
            {
                "label": label,
                "description": "기본 코스",
                "points": points,
            }
        ],
        ensure_ascii=False,
    )


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
    mock_upload.side_effect = [
        ("https://test.com/photo.jpg", None),
        ("https://test.com/point_start.jpg", None),
        ("https://test.com/point_finish.jpg", None),
    ]
    token = get_test_jwt_token(
        test_user, f"user_{test_user}", f"user{test_user}@example.com"
    )
    headers = get_auth_headers(token)

    route_photo = (io.BytesIO(b"route"), "photo.jpg")
    start_photo = (io.BytesIO(b"start"), "start.jpg")
    finish_photo = (io.BytesIO(b"finish"), "finish.jpg")
    res = client.post(
        "/users/course-recommendations",
        data={
            "title": "한강",
            "description": "설명",
            "review": "멋진 코스",
            "courses": _courses_payload(
                "한강 코스",
                include_point_photos=True,
                include_address=True,
                include_point_descriptions=True,
            ),
            "photo": route_photo,
            "point_photo_1": start_photo,
            "point_photo_2": finish_photo,
        },
        headers=headers,
        content_type="multipart/form-data",
    )
    assert res.status_code == 201
    created = res.get_json()["data"][0]
    created_points = created["courses"]
    assert created_points[0]["point_id"] == 0
    assert created_points[1]["point_id"] == 1
    assert created_points[0]["photo_url"] == "https://test.com/point_start.jpg"
    assert created_points[1]["photo_url"] == "https://test.com/point_finish.jpg"
    assert created_points[0]["address"] == "서울시 테스트구 1번지"
    assert created_points[1]["address"] == "서울시 테스트구 2번지"
    assert created_points[0]["description"] == "지점 설명 1"
    assert created_points[1]["description"] == "지점 설명 2"

    res = client.get("/users/course-recommendations", headers=headers)
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert len(data) == 1
    assert data[0]["title"] == "한강"
    assert data[0]["description"] == "설명"
    assert len(data[0]["courses"]) == 2
    list_points = data[0]["courses"]
    assert list_points[0]["point_id"] == 0
    assert list_points[1]["point_id"] == 1
    assert list_points[0]["photo_url"] == "https://test.com/point_start.jpg"
    assert list_points[1]["photo_url"] == "https://test.com/point_finish.jpg"
    assert list_points[0]["address"] == "서울시 테스트구 1번지"
    assert list_points[1]["address"] == "서울시 테스트구 2번지"
    assert list_points[0]["description"] == "지점 설명 1"
    assert list_points[1]["description"] == "지점 설명 2"


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
            "title": "한강",
            "review": "멋진 코스",
            "courses": _courses_payload("한강 코스", include_address=True),
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
        json={
            "status": "verified",
            "points": 5,
            "admin_notes": "좋은 코스",
        },
        headers=admin_headers,
    )
    assert res.status_code == 200
    data = res.get_json()["data"][0]
    assert data["status"] == "verified"
    assert data["points_awarded"] == 5
    assert data["admin_notes"] == "좋은 코스"
    assert data["user_id"] == test_user


@patch("app.routes.recommendations.upload_file_to_ncp")
def test_weekly_recommendation_limit(mock_upload, client, test_user):
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
                "title": f"코스{i}",
                "review": "굿",
                "courses": _courses_payload(f"코스{i} 루트"),
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
            "title": "코스3",
            "review": "굿",
            "courses": _courses_payload("코스3 루트"),
            "photo": (img, "p3.jpg"),
        },
        headers=headers,
        content_type="multipart/form-data",
    )
    assert res.status_code == 400
    assert "weekly course recommendation limit" in res.get_json()["data"][0]["error"]


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
            "title": "한강",
            "review": "멋진 코스",
            "courses": _courses_payload("한강 코스"),
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
    assert any(rec["username"] == "testuser" for rec in data)


def test_admin_list_requires_privileges(client, test_user):
    """관리자 권한 없이 모든 코스 추천을 조회할 수 없는지 확인"""
    token = get_test_jwt_token(test_user, "user", "user@example.com")
    headers = get_auth_headers(token)

    res = client.get("/admin/course-recommendations", headers=headers)
    assert res.status_code in (401, 403)


def test_admin_course_recommendations_pagination(client, app, admin_user, test_user):
    """관리자 코스 추천 목록 페이지네이션 테스트"""

    with app.app_context():
        db = get_db()
        with db.cursor() as cur:
            cur.execute("DELETE FROM course_recommendations")
            for i in range(3):
                cur.execute(
                    "INSERT INTO course_recommendations (user_id, title, review) VALUES (%s, %s, %s)",
                    (test_user, f"장소{i}", f"리뷰{i}"),
                )

    token = get_test_jwt_token(admin_user, "admin", "admin@example.com", is_admin=True)
    headers = get_admin_headers(token)

    res = client.get("/admin/course-recommendations?limit=1&offset=1", headers=headers)
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert len(data) == 1
    assert data[0]["title"] == "장소1"


@patch("app.routes.recommendations.upload_file_to_ncp")
def test_week_recommendation_count(mock_upload, client, test_user):
    mock_upload.return_value = ("https://test.com/photo.jpg", None)
    token = get_test_jwt_token(
        test_user, f"user_{test_user}", f"user{test_user}@example.com"
    )
    headers = get_auth_headers(token)

    res = client.get("/users/course-recommendations/week/count", headers=headers)
    assert res.status_code == 200
    assert res.get_json()["data"][0]["count"] == 0

    img, _ = create_fake_image()
    client.post(
        "/users/course-recommendations",
        data={
            "title": "한강",
            "review": "굿",
            "courses": _courses_payload("한강 루트"),
            "photo": (img, "p.jpg"),
        },
        headers=headers,
        content_type="multipart/form-data",
    )

    res = client.get("/users/course-recommendations/week/count", headers=headers)
    assert res.status_code == 200
    assert res.get_json()["data"][0]["count"] == 1


def test_export_course_recommendations_csv(client, app, test_user):
    with app.app_context():
        db = get_db()
        with db.cursor() as cur:
            cur.execute(
                "INSERT INTO course_recommendations (user_id, title, review, status) VALUES (%s, %s, %s, %s)",
                (test_user, "한강", "굿", "verified"),
            )
            cur.execute(
                "INSERT INTO course_recommendations (user_id, title, review, status) VALUES (%s, %s, %s, %s)",
                (test_user, "잠실", "보통", "pending"),
            )

    res = client.get(
        "/admin/course-recommendations/export", headers=get_admin_headers()
    )
    assert res.status_code == 200
    assert res.headers["Content-Type"].startswith("text/csv")
    content = res.data.decode()
    lines = [line for line in content.strip().split("\n") if line]
    assert len(lines) == 2
    assert "verified" in lines[1]
    assert "pending" not in content
