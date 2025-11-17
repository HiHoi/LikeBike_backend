"""Activity summary endpoints."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from flask import Blueprint

from ..db import get_db
from ..utils.auth import get_current_user, get_current_user_id, jwt_required
from ..utils.responses import make_response

bp = Blueprint("activity_summary", __name__)


def _get_period_range() -> tuple[datetime, datetime]:
    """Return the UTC datetime range covering the last 14 days."""

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=14)
    return start, end


@bp.route("/users/<int:user_id>/activity-summary", methods=["GET"])
@jwt_required
def get_biweekly_activity_summary(user_id: int):
    """Return a human-readable activity summary for the last two weeks."""

    current_user = get_current_user()
    current_user_id = get_current_user_id()
    if current_user_id != user_id and not (current_user and current_user.get("is_admin")):
        return make_response({"error": "Forbidden"}, 403)

    db = get_db()
    with db.cursor() as cur:
        cur.execute("SELECT username FROM users WHERE id = %s", (user_id,))
        user_row = cur.fetchone()
        if not user_row:
            return make_response({"error": "user not found"}, 404)

        username: str = user_row["username"] if isinstance(user_row, dict) else user_row[0]

        start, end = _get_period_range()

        cur.execute(
            """
            SELECT
                COUNT(*) AS attempts,
                COALESCE(SUM(CASE WHEN is_correct THEN 1 ELSE 0 END), 0) AS correct
            FROM user_quiz_attempts
            WHERE user_id = %s AND attempted_at >= %s AND attempted_at < %s
            """,
            (user_id, start, end),
        )
        quiz_row = cur.fetchone() or {"attempts": 0, "correct": 0}
        quiz_attempts = int(quiz_row.get("attempts", 0))
        quiz_correct = int(quiz_row.get("correct", 0))
        quiz_accuracy = (quiz_correct / quiz_attempts) * 100 if quiz_attempts else 0.0

        cur.execute(
            """
            SELECT
                COUNT(*) AS total,
                COALESCE(SUM(CASE WHEN verification_status = 'verified' THEN 1 ELSE 0 END), 0) AS approved
            FROM bike_usage_logs
            WHERE user_id = %s AND created_at >= %s AND created_at < %s
            """,
            (user_id, start, end),
        )
        bike_row = cur.fetchone() or {"total": 0, "approved": 0}
        bike_attempts = int(bike_row.get("total", 0))
        bike_approved = int(bike_row.get("approved", 0))

        cur.execute(
            """
            SELECT
                COUNT(*) AS total,
                COALESCE(SUM(CASE WHEN status = 'verified' THEN 1 ELSE 0 END), 0) AS approved,
                COALESCE(SUM(CASE WHEN status = 'verified' THEN points_awarded ELSE 0 END), 0) AS points
            FROM course_recommendations
            WHERE user_id = %s AND created_at >= %s AND created_at < %s
            """,
            (user_id, start, end),
        )
        course_row = cur.fetchone() or {"total": 0, "approved": 0, "points": 0}
        course_total = int(course_row.get("total", 0))
        course_approved = int(course_row.get("approved", 0))
        course_points = int(course_row.get("points", 0))

    summary_text = (
        f"지난 2주 동안 {username}님은 안전 퀴즈를 {quiz_attempts}문제 풀었고, "
        f"정답률은 {quiz_accuracy:.0f}%였어요.\n"
        f"자전거 활동 인증은 {bike_attempts}회 시도했고, 이 중 {bike_approved}회가 승인되었어요.\n"
        f"코스 추천은 {course_total}개를 등록해서 {course_approved}개가 승인되었고, 총 {course_points}포인트를 획득했습니다!"
    )

    payload: Dict[str, Any] = {
        "user_id": user_id,
        "username": username,
        "period": {
            "start": start.isoformat(),
            "end": end.isoformat(),
        },
        "quizzes": {
            "attempts": quiz_attempts,
            "correct": quiz_correct,
            "accuracy": round(quiz_accuracy, 2),
        },
        "bike_logs": {
            "attempts": bike_attempts,
            "approved": bike_approved,
        },
        "course_recommendations": {
            "submitted": course_total,
            "approved": course_approved,
            "points": course_points,
        },
        "summary_text": summary_text,
    }

    return make_response(payload)
