import pytest

from app import create_app
from app.db import get_db
from tests.test_helpers import get_auth_headers, get_test_jwt_token


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
                    "test_community_user",
                    "communityuser",
                    "community@example.com",
                    "https://k.kakaocdn.net/dn/community.jpg",
                ),
            )
            return cur.fetchone()["id"]


def test_community_post_crud(client, test_user):
    token = get_test_jwt_token(
        test_user, f"user_{test_user}", f"user{test_user}@example.com"
    )
    headers = get_auth_headers(token)

    # create post
    res = client.post(
        "/community/posts",
        json={
            "title": "자전거 추천 경로",
            "content": "한강공원 라이딩 코스 추천합니다!",
            "post_type": "route_share",
        },
        headers=headers,
    )
    assert res.status_code == 201
    post_data = res.get_json()["data"][0]
    post_id = post_data["id"]

    # 보상이 포함되어 있는지 확인 (경험치만 지급)
    assert "experience_earned" in post_data

    # get post detail
    res = client.get(f"/community/posts/{post_id}")
    assert res.status_code == 200
    post_detail = res.get_json()["data"][0]
    assert post_detail["title"] == "자전거 추천 경로"
    assert "comments" in post_detail

    # add comment
    res = client.post(
        f"/community/posts/{post_id}/comments",
        json={"content": "좋은 정보 감사합니다!"},
        headers=headers,
    )
    assert res.status_code == 201

    # 댓글 작성 보상 확인
    res = client.get("/users/rewards", headers=headers)
    assert res.status_code == 200
    rewards = res.get_json()["data"]
    reasons = [r["reward_reason"] for r in rewards]
    assert "게시글 작성" in reasons
    assert "댓글 작성" in reasons

    # toggle like
    res = client.post(f"/community/posts/{post_id}/like", headers=headers)
    assert res.status_code == 200
    like_data = res.get_json()["data"][0]
    assert like_data["liked"] == True
    assert like_data["likes_count"] == 1

    # toggle like again (unlike)
    res = client.post(f"/community/posts/{post_id}/like", headers=headers)
    assert res.status_code == 200
    unlike_data = res.get_json()["data"][0]
    assert unlike_data["liked"] == False
    assert unlike_data["likes_count"] == 0


def test_safety_report_crud(client, test_user):
    token = get_test_jwt_token(
        test_user, f"user_{test_user}", f"user{test_user}@example.com"
    )
    headers = get_auth_headers(token)

    # create safety report
    res = client.post(
        "/users/safety-reports",
        json={
            "report_type": "dangerous_road",
            "latitude": 37.5665,
            "longitude": 126.9780,
            "description": "도로에 큰 구멍이 있어 위험합니다",
        },
        headers=headers,
    )
    assert res.status_code == 201
    report_data = res.get_json()["data"][0]
    assert report_data["report_type"] == "dangerous_road"
    assert report_data["status"] == "pending"

    # get user's safety reports
    res = client.get("/users/safety-reports", headers=headers)
    assert res.status_code == 200
    reports = res.get_json()["data"]
    assert len(reports) == 1


def test_cycling_goals(client, test_user):
    token = get_test_jwt_token(
        test_user, f"user_{test_user}", f"user{test_user}@example.com"
    )
    headers = get_auth_headers(token)

    # create cycling goal
    res = client.post(
        "/users/cycling-goals",
        json={
            "goal_type": "distance",
            "target_value": 100.0,
            "period_type": "monthly",
            "start_date": "2025-07-01",
            "end_date": "2025-07-31",
        },
        headers=headers,
    )
    assert res.status_code == 201
    goal_data = res.get_json()["data"][0]
    assert goal_data["goal_type"] == "distance"
    assert float(goal_data["target_value"]) == 100.0

    # get cycling goals
    res = client.get("/users/cycling-goals", headers=headers)
    assert res.status_code == 200
    goals = res.get_json()["data"]
    assert len(goals) == 1


def test_user_stats(client, test_user):
    token = get_test_jwt_token(
        test_user, f"user_{test_user}", f"user{test_user}@example.com"
    )
    headers = get_auth_headers(token)

    # create some bike logs first
    client.post(
        "/users/bike-logs",
        json={"description": "test ride 1", "distance": 10.5, "duration_minutes": 45},
        headers=headers,
    )

    client.post(
        "/users/bike-logs",
        json={"description": "test ride 2", "distance": 8.3, "duration_minutes": 30},
        headers=headers,
    )

    # get user stats
    res = client.get("/users/stats", headers=headers)
    assert res.status_code == 200
    stats = res.get_json()["data"][0]

    assert stats["total_rides"] == 2
    assert float(stats["total_distance"]) == 18.8
    assert stats["total_duration"] == 75
    assert "goals_progress" in stats


def test_community_auth_required(client, test_user):
    # Test create post without JWT token
    res = client.post(
        "/community/posts",
        json={"title": "Test post", "content": "Test content", "post_type": "question"},
    )
    assert res.status_code == 401

    # Test create safety report without JWT token
    res = client.post(
        "/users/safety-reports",
        json={
            "report_type": "dangerous_road",
            "latitude": 37.5665,
            "longitude": 126.9780,
            "description": "Test report",
        },
    )
    assert res.status_code == 401

    # Test get cycling goals without JWT token
    res = client.get("/users/cycling-goals")
    assert res.status_code == 401
