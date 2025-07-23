from flask import Blueprint

from ..db import get_db
from ..utils.auth import get_current_user_id, jwt_required
from ..utils.responses import make_response

bp = Blueprint("rewards", __name__)


@bp.route("/users/rewards", methods=["GET"])
@jwt_required
def get_user_rewards():
    """
    사용자 포인트 적립 내역 조회
    ---
    tags:
      - Rewards
    summary: 로그인한 사용자의 포인트 적립 내역 조회
    description: 현재 로그인한 사용자의 포인트 적립(리워드) 내역을 최근 순으로 반환합니다.
    security:
      - JWT: []
    responses:
      200:
        description: 포인트 적립 내역 조회 성공
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 200
            message:
              type: string
              example: "OK"
            data:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: integer
                    example: 1
                  user_id:
                    type: integer
                    example: 1
                  source_type:
                    type: string
                    example: "quiz"
                  points:
                    type: integer
                    example: 10
                  reward_reason:
                    type: string
                    example: "퀴즈 정답"
                  created_at:
                    type: string
                    format: date-time
                    example: "2024-01-01T12:00:00Z"
      401:
        description: 인증 실패
    """
    user_id = get_current_user_id()
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "SELECT * FROM rewards WHERE user_id = %s ORDER BY created_at DESC",
            (user_id,),
        )
        rewards = cur.fetchall()
    return make_response([dict(r) for r in rewards])
