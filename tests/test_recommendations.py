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


def test_get_course_recommendation_request_fields(client, test_user):
    token = get_test_jwt_token(
        test_user, f"user_{test_user}", f"user{test_user}@example.com"
    )
    headers = get_auth_headers(token)

    res = client.get(
        "/users/course-recommendations/request-fields",
        headers=headers,
    )
    assert res.status_code == 200
    payload = res.get_json()["data"][0]

    assert payload["content_type"] == "multipart/form-data"
    field_names = {field["name"] for field in payload["fields"]}
    assert {"places", "cover_photo", "place_photo_{index}"}.issubset(field_names)
    assert "photo" not in field_names

    place_schema = payload["place_item_schema"]
    assert set(place_schema["required"]) == {"name", "address_name", "x", "y"}
    assert "photo" in place_schema["properties"]
    assert "description" in place_schema["properties"]


def _places_payload(include_photos: bool = False) -> str:
    places = [
        {
            "name": "출발지",
            "address_name": "서울",
            "x": "127.0",
            "y": "37.5",
            "description": "출발지 설명",
        },
        {
            "name": "도착지",
            "address_name": "부산",
            "x": "129.0",
            "y": "35.1",
            "description": "도착지 설명",
        },
    ]

    if include_photos:
        for idx, place in enumerate(places, start=1):
            place["photo"] = f"place_photo_{idx}"

    return json.dumps(places, ensure_ascii=False)


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
def test_create_and_list_recommendations_with_cover_photo_field(
    mock_upload, client, test_user
):
    """코스 생성 시 cover_photo 필드로 대표 사진을 지정하는 경우 테스트"""
    mock_upload.side_effect = [
        ("https://test.com/point_start.jpg", None),
        ("https://test.com/point_finish.jpg", None),
    ]
    token = get_test_jwt_token(
        test_user, f"user_{test_user}", f"user{test_user}@example.com"
    )
    headers = get_auth_headers(token)

    start_photo = (io.BytesIO(b"start"), "start.jpg")
    finish_photo = (io.BytesIO(b"finish"), "finish.jpg")
    res = client.post(
        "/users/course-recommendations",
        data={
            "places": _places_payload(include_photos=True),
            "cover_photo": "place_photo_2",  # 두 번째 사진을 대표 사진으로 지정
            "place_photo_1": start_photo,
            "place_photo_2": finish_photo,
        },
        headers=headers,
        content_type="multipart/form-data",
    )
    assert res.status_code == 201
    created = res.get_json()["data"][0]
    assert created["photo_url"] == "https://test.com/point_finish.jpg"  # 대표 사진 확인
    assert created["course_name"] == "출발지"
    assert created["course_description"] == "서울"

    created_places = created["places"]
    assert created_places[0]["photo_url"] == "https://test.com/point_start.jpg"
    assert created_places[1]["photo_url"] == "https://test.com/point_finish.jpg"


@patch("app.routes.recommendations.upload_file_to_ncp")
def test_create_and_list_recommendations_default_cover_photo(
    mock_upload, client, test_user
):
    """코스 생성 시 cover_photo 필드 생략 시 첫 장소 사진이 대표 사진이 되는지 테스트"""
    mock_upload.side_effect = [
        ("https://test.com/point_start.jpg", None),
        ("https://test.com/point_finish.jpg", None),
    ]
    token = get_test_jwt_token(
        test_user, f"user_{test_user}", f"user{test_user}@example.com"
    )
    headers = get_auth_headers(token)

    start_photo = (io.BytesIO(b"start"), "start.jpg")
    finish_photo = (io.BytesIO(b"finish"), "finish.jpg")
    res = client.post(
        "/users/course-recommendations",
        data={
            "places": _places_payload(include_photos=True),
            # cover_photo 필드 생략
            "place_photo_1": start_photo,
            "place_photo_2": finish_photo,
        },
        headers=headers,
        content_type="multipart/form-data",
    )
    assert res.status_code == 201
    created = res.get_json()["data"][0]
    assert created["photo_url"] == "https://test.com/point_start.jpg"  # 첫 장소 사진 확인
    assert created["course_name"] == "출발지"

    # 목록 조회 테스트
    res = client.get("/users/course-recommendations", headers=headers)
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert len(data) >= 1
    assert data[0]["photo_url"] == "https://test.com/point_start.jpg"
    assert data[0]["course_name"] == "출발지"
    assert len(data[0]["places"]) == 2
    list_places = data[0]["places"]
    assert list_places[0]["photo_url"] == "https://test.com/point_start.jpg"
    assert list_places[1]["photo_url"] == "https://test.com/point_finish.jpg"


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
            "places": _places_payload(include_photos=True),
            "place_photo_1": (img, "p1.jpg"),
            "place_photo_2": (img, "p2.jpg"),
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
                "places": _places_payload(include_photos=True),
                "place_photo_1": (img, f"p1_{i}.jpg"),
                "place_photo_2": (img, f"p2_{i}.jpg"),
            },
            headers=headers,
            content_type="multipart/form-data",
        )
        assert res.status_code == 201

    img, _ = create_fake_image()
    res = client.post(
        "/users/course-recommendations",
        data={
            "places": _places_payload(include_photos=True),
            "place_photo_1": (img, "p1_3.jpg"),
            "place_photo_2": (img, "p2_3.jpg"),
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
            "places": _places_payload(include_photos=True),
            "place_photo_1": (img, "p1.jpg"),
            "place_photo_2": (img, "p2.jpg"),
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
            "places": _places_payload(include_photos=True),
            "place_photo_1": (img, "p1.jpg"),
            "place_photo_2": (img, "p2.jpg"),
        },
        headers=headers,
        content_type="multipart/form-data",
    )

    res = client.get("/users/course-recommendations/week/count", headers=headers)
    assert res.status_code == 200
    assert res.get_json()["data"][0]["count"] >= 1


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
