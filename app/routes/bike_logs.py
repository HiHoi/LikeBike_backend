from flask import Blueprint, request

from ..utils.responses import make_response

from ..db import get_db

bp = Blueprint("bike_logs", __name__)


@bp.route("/users/<int:user_id>/bike-logs", methods=["POST"])
def create_bike_log(user_id):
    data = request.get_json() or {}
    description = data.get("description")
    if not description:
        return make_response({"error": "description required"}, 400)

    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO bike_usage_logs (user_id, description) VALUES (%s, %s) RETURNING id, user_id, description, usage_time",
            (user_id, description),
        )
        log = cur.fetchone()

    return make_response(dict(log), 201)


@bp.route("/users/<int:user_id>/bike-logs", methods=["GET"])
def list_bike_logs(user_id):
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "SELECT id, user_id, description, usage_time FROM bike_usage_logs WHERE user_id = %s ORDER BY usage_time DESC",
            (user_id,),
        )
        logs = cur.fetchall()

    return make_response(logs)


@bp.route("/bike-logs/<int:log_id>", methods=["PUT"])
def update_bike_log(log_id):
    data = request.get_json() or {}
    description = data.get("description")
    if description is None:
        return make_response({"error": "description required"}, 400)

    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "UPDATE bike_usage_logs SET description = %s WHERE id = %s RETURNING id, user_id, description, usage_time",
            (description, log_id),
        )
        log = cur.fetchone()
        if not log:
            return make_response({"error": "log not found"}, 404)

    return make_response(dict(log))


@bp.route("/bike-logs/<int:log_id>", methods=["DELETE"])
def delete_bike_log(log_id):
    db = get_db()
    with db.cursor() as cur:
        cur.execute("DELETE FROM bike_usage_logs WHERE id = %s", (log_id,))
        if cur.rowcount == 0:
            return make_response({"error": "log not found"}, 404)

    return make_response(None, 204)
