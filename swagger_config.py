"""
Swagger 설정 및 공통 스키마 정의
"""

# 공통 응답 스키마
COMMON_RESPONSES = {
    '401': {
        'description': 'Unauthorized - JWT 토큰이 없거나 유효하지 않음',
        'schema': {
            'type': 'object',
            'properties': {
                'code': {'type': 'integer', 'example': 401},
                'message': {'type': 'string', 'example': 'Unauthorized'},
                'data': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'error': {'type': 'string', 'example': 'Token required'}
                        }
                    }
                }
            }
        }
    },
    '403': {
        'description': 'Forbidden - 관리자 권한 필요',
        'schema': {
            'type': 'object',
            'properties': {
                'code': {'type': 'integer', 'example': 403},
                'message': {'type': 'string', 'example': 'Forbidden'},
                'data': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'error': {'type': 'string', 'example': 'Admin access required'}
                        }
                    }
                }
            }
        }
    },
    '400': {
        'description': 'Bad Request - 잘못된 요청',
        'schema': {
            'type': 'object',
            'properties': {
                'code': {'type': 'integer', 'example': 400},
                'message': {'type': 'string', 'example': 'Bad Request'},
                'data': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'error': {'type': 'string', 'example': 'Invalid request data'}
                        }
                    }
                }
            }
        }
    },
    '404': {
        'description': 'Not Found - 리소스를 찾을 수 없음',
        'schema': {
            'type': 'object',
            'properties': {
                'code': {'type': 'integer', 'example': 404},
                'message': {'type': 'string', 'example': 'Not Found'},
                'data': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'error': {'type': 'string', 'example': 'Resource not found'}
                        }
                    }
                }
            }
        }
    }
}

# 공통 보안 스키마
SECURITY_SCHEMES = {
    "JWT": {
        "type": "apiKey",
        "name": "Authorization",
        "in": "header",
        "description": 'JWT Authorization header using the Bearer scheme. Example: "Authorization: Bearer {token}"'
    },
    "AdminHeader": {
        "type": "apiKey",
        "name": "X-Admin",
        "in": "header",
        "description": "Admin header for admin-only endpoints. Use 'true' as value."
    }
}

# 공통 데이터 모델
USER_MODEL = {
    'type': 'object',
    'properties': {
        'id': {'type': 'integer', 'example': 1},
        'username': {'type': 'string', 'example': '사용자명'},
        'email': {'type': 'string', 'example': 'user@example.com'},
        'points': {'type': 'integer', 'example': 150},
        'level': {'type': 'integer', 'example': 2},
        'experience_points': {'type': 'integer', 'example': 250},
        'created_at': {'type': 'string', 'format': 'date-time', 'example': '2024-01-01T00:00:00Z'}
    }
}

BIKE_LOG_MODEL = {
    'type': 'object',
    'properties': {
        'id': {'type': 'integer', 'example': 1},
        'user_id': {'type': 'integer', 'example': 1},
        'description': {'type': 'string', 'example': '한강 라이딩'},
        'distance': {'type': 'number', 'example': 5.2},
        'duration_minutes': {'type': 'integer', 'example': 45},
        'usage_time': {'type': 'string', 'format': 'date-time', 'example': '2024-01-01T09:00:00Z'}
    }
}

QUIZ_MODEL = {
    'type': 'object',
    'properties': {
        'id': {'type': 'integer', 'example': 1},
        'question': {'type': 'string', 'example': '자전거 안전을 위해 반드시 착용해야 하는 것은?'},
        'correct_answer': {'type': 'string', 'example': '헬멧'},
        'answers': {
            'type': 'array',
            'items': {'type': 'string'},
            'example': ['모자', '선글라스', '헬멧', '장갑']
        }
    }
}

NEWS_MODEL = {
    'type': 'object',
    'properties': {
        'id': {'type': 'integer', 'example': 1},
        'title': {'type': 'string', 'example': '새로운 자전거 도로 개통'},
        'content': {'type': 'string', 'example': '한강변에 새로운 자전거 전용 도로가 개통되었습니다...'},
        'published_at': {'type': 'string', 'format': 'date-time', 'example': '2024-01-01T00:00:00Z'}
    }
}

POST_MODEL = {
    'type': 'object',
    'properties': {
        'id': {'type': 'integer', 'example': 1},
        'user_id': {'type': 'integer', 'example': 1},
        'title': {'type': 'string', 'example': '자전거 추천 경로'},
        'content': {'type': 'string', 'example': '한강공원 라이딩 코스 추천합니다!'},
        'post_type': {'type': 'string', 'example': 'general'},
        'likes_count': {'type': 'integer', 'example': 5},
        'comments_count': {'type': 'integer', 'example': 3},
        'status': {'type': 'string', 'example': 'active'},
        'created_at': {'type': 'string', 'format': 'date-time', 'example': '2024-01-01T00:00:00Z'}
    }
}
