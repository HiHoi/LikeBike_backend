"""
테스트를 위한 헬퍼 함수들
"""
import os
from app.utils.auth import generate_jwt_token


def get_test_jwt_token(user_id=1, username="test_user", email="test@example.com", is_admin=False):
    """테스트용 JWT 토큰 생성"""
    return generate_jwt_token(user_id, username, email, is_admin)


def get_admin_jwt_token(user_id=999, username="admin", email="admin@example.com"):
    """테스트용 관리자 JWT 토큰 생성"""
    return generate_jwt_token(user_id, username, email, is_admin=True)


def get_auth_headers(token=None):
    """인증 헤더 생성"""
    if token is None:
        token = get_test_jwt_token()
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }


def get_admin_headers(token=None):
    """관리자 인증 헤더 생성"""
    if token is None:
        token = get_admin_jwt_token()
    return {
        "Authorization": f"Bearer {token}",
        "X-Admin": "true",
        "Content-Type": "application/json"
    }
