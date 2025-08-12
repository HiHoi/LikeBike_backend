"""
JWT 인증 관련 유틸리티 모듈
"""
import jwt
import os
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, current_app
from app.utils.responses import make_response


# JWT 시크릿 키 (환경변수에서 읽어오고, 없으면 기본값 사용)
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-secret-key-here-change-in-production')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24 * 7  # 7일


def generate_jwt_token(user_id, username=None, email=None, is_admin=False):
    """
    JWT 토큰 생성
    
    Args:
        user_id (int): 사용자 ID
        username (str): 사용자명 (선택)
        email (str): 이메일 (선택)
        is_admin (bool): 관리자 여부
    
    Returns:
        str: JWT 토큰
    """
    payload = {
        'user_id': user_id,
        'username': username,
        'email': email,
        'is_admin': is_admin,
        'iat': datetime.utcnow(),
        'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token


def decode_jwt_token(token):
    """
    JWT 토큰 디코딩
    
    Args:
        token (str): JWT 토큰
    
    Returns:
        dict: 디코딩된 페이로드 또는 None (실패 시)
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def get_token_from_header():
    """
    Authorization 헤더에서 JWT 토큰 추출
    
    Returns:
        str: JWT 토큰 또는 None
    """
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        return auth_header.split(' ')[1]
    return None


def jwt_required(f):
    """
    JWT 인증이 필요한 엔드포인트를 위한 데코레이터
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = get_token_from_header()
        
        if not token:
            return make_response({"error": "Authorization token required"}, 401)
        
        payload = decode_jwt_token(token)
        if not payload:
            return make_response({"error": "Invalid or expired token"}, 401)
        
        # 현재 사용자 정보를 request context에 저장
        request.current_user = {
            'user_id': payload.get('user_id'),
            'username': payload.get('username'),
            'email': payload.get('email'),
            'is_admin': payload.get('is_admin', False)
        }
        
        return f(*args, **kwargs)
    
    return decorated_function


def admin_required(f):
    """
    관리자 권한이 필요한 엔드포인트를 위한 데코레이터
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 먼저 JWT 인증 확인
        token = get_token_from_header()
        
        if not token:
            return make_response({"error": "Authorization token required"}, 401)
        
        payload = decode_jwt_token(token)
        if not payload:
            return make_response({"error": "Invalid or expired token"}, 401)
        
        # 관리자 헤더 확인
        admin_header = request.headers.get('X-Admin')
        if admin_header != 'true':
            return make_response({"error": "Admin access required"}, 403)
        
        # 토큰에서 관리자 권한 확인 (추가 보안)
        if not payload.get('is_admin', False):
            return make_response({"error": "Admin privileges required"}, 403)
        
        # 현재 사용자 정보를 request context에 저장
        request.current_user = {
            'user_id': payload.get('user_id'),
            'username': payload.get('username'),
            'email': payload.get('email'),
            'is_admin': payload.get('is_admin', False)
        }
        
        return f(*args, **kwargs)
    
    return decorated_function


def get_current_user():
    """
    현재 로그인한 사용자 정보 반환
    
    Returns:
        dict: 사용자 정보 또는 None
    """
    return getattr(request, 'current_user', None)


def get_current_user_id():
    """
    현재 로그인한 사용자 ID 반환
    
    Returns:
        int: 사용자 ID 또는 None
    """
    user = get_current_user()
    return user.get('user_id') if user else None


def refresh_jwt_token(current_token):
    """
    JWT 토큰 새로고침
    
    Args:
        current_token (str): 현재 토큰
    
    Returns:
        str: 새로운 토큰 또는 None
    """
    payload = decode_jwt_token(current_token)
    if not payload:
        return None
    
    # 새로운 토큰 생성 (기존 정보 유지)
    new_token = generate_jwt_token(
        user_id=payload.get('user_id'),
        username=payload.get('username'),
        email=payload.get('email'),
        is_admin=payload.get('is_admin', False)
    )
    
    return new_token
