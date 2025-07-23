from flask import Blueprint

from ..db import get_db
from ..utils.auth import get_current_user_id, jwt_required
from ..utils.responses import make_response

bp = Blueprint("rewards", __name__)


@bp.route("/users/rewards", methods=["GET"])
@jwt_required
def get_user_rewards():
    """사용자 포인트 적립 내역 조회"""
    user_id = get_current_user_id()
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "SELECT * FROM rewards WHERE user_id = %s ORDER BY created_at DESC",
            (user_id,),
        )
        rewards = cur.fetchall()
    return make_response([dict(r) for r in rewards])
