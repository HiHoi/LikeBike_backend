from flask import Blueprint, request

from ..utils.responses import make_response

from ..db import get_db

bp = Blueprint("bike_logs", __name__)


@bp.route("/users/<int:user_id>/bike-logs", methods=["POST"])
def create_bike_log(user_id):
    data = request.get_json() or {}
    description = data.get("description")
    start_latitude = data.get("start_latitude")
    start_longitude = data.get("start_longitude")
    end_latitude = data.get("end_latitude")
    end_longitude = data.get("end_longitude")
    distance = data.get("distance")
    duration_minutes = data.get("duration_minutes")
    start_time = data.get("start_time")
    end_time = data.get("end_time")
    
    if not description:
        return make_response({"error": "description required"}, 400)

    db = get_db()
    with db.cursor() as cur:
        cur.execute("""
            INSERT INTO bike_usage_logs 
            (user_id, description, start_latitude, start_longitude, end_latitude, end_longitude, 
             distance, duration_minutes, start_time, end_time) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) 
            RETURNING id, user_id, description, start_latitude, start_longitude, 
                      end_latitude, end_longitude, distance, duration_minutes, 
                      start_time, end_time, usage_time
        """, (user_id, description, start_latitude, start_longitude, end_latitude, 
              end_longitude, distance, duration_minutes, start_time, end_time))
        log = cur.fetchone()
        
        # 자전거 이용 보상 지급
        points = 5   # 자전거 이용 시 5포인트
        exp = 3      # 자전거 이용 시 3경험치
        
        # 거리 기반 추가 보상
        if distance:
            bonus_points = int(distance * 2)  # 1km당 2포인트 추가
            bonus_exp = int(distance)         # 1km당 1경험치 추가
            points += bonus_points
            exp += bonus_exp
        
        # 포인트 업데이트
        cur.execute("""
            UPDATE users 
            SET points = points + %s, experience_points = experience_points + %s 
            WHERE id = %s
        """, (points, exp, user_id))
        
        # 보상 기록
        cur.execute("""
            INSERT INTO rewards 
            (user_id, source_type, source_id, points, experience_points, reward_reason)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (user_id, "bike_usage", log["id"], points, exp, f"자전거 이용 ({distance}km)" if distance else "자전거 이용"))
        
        # 목표 업데이트 (거리 목표가 있다면)
        if distance:
            cur.execute("""
                UPDATE cycling_goals 
                SET current_value = current_value + %s 
                WHERE user_id = %s AND goal_type = 'distance' AND status = 'active'
                  AND start_date <= CURRENT_DATE AND end_date >= CURRENT_DATE
            """, (distance, user_id))

    response_data = dict(log)
    response_data.update({
        "points_earned": points,
        "experience_earned": exp
    })

    return make_response(response_data, 201)


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


@bp.route("/users/<int:user_id>/rewards", methods=["GET"])
def get_user_rewards(user_id):
    """사용자 포인트 적립 내역 조회"""
    db = get_db()
    with db.cursor() as cur:
        cur.execute("""
            SELECT * FROM rewards 
            WHERE user_id = %s 
            ORDER BY created_at DESC
        """, (user_id,))
        rewards = cur.fetchall()

    return make_response([dict(reward) for reward in rewards])


@bp.route("/users/<int:user_id>/cycling-goals", methods=["GET"])
def get_cycling_goals(user_id):
    """사용자 사이클링 목표 조회"""
    db = get_db()
    with db.cursor() as cur:
        cur.execute("""
            SELECT * FROM cycling_goals 
            WHERE user_id = %s 
            ORDER BY created_at DESC
        """, (user_id,))
        goals = cur.fetchall()

    return make_response([dict(goal) for goal in goals])


@bp.route("/users/<int:user_id>/cycling-goals", methods=["POST"])
def create_cycling_goal(user_id):
    """새로운 사이클링 목표 생성"""
    data = request.get_json() or {}
    goal_type = data.get("goal_type")  # distance, duration, frequency
    target_value = data.get("target_value")
    period_type = data.get("period_type")  # daily, weekly, monthly
    start_date = data.get("start_date")
    end_date = data.get("end_date")
    
    if not all([goal_type, target_value, period_type, start_date, end_date]):
        return make_response({"error": "missing required fields"}, 400)
    
    db = get_db()
    with db.cursor() as cur:
        cur.execute("""
            INSERT INTO cycling_goals 
            (user_id, goal_type, target_value, period_type, start_date, end_date)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING *
        """, (user_id, goal_type, target_value, period_type, start_date, end_date))
        goal = cur.fetchone()
    
    return make_response(dict(goal), 201)


@bp.route("/users/<int:user_id>/achievements", methods=["GET"])
def get_user_achievements(user_id):
    """사용자 업적 조회"""
    db = get_db()
    with db.cursor() as cur:
        cur.execute("""
            SELECT * FROM user_achievements 
            WHERE user_id = %s 
            ORDER BY achieved_at DESC
        """, (user_id,))
        achievements = cur.fetchall()

    return make_response([dict(achievement) for achievement in achievements])


@bp.route("/users/<int:user_id>/stats", methods=["GET"])
def get_user_stats(user_id):
    """사용자 통계 조회"""
    db = get_db()
    with db.cursor() as cur:
        # 총 이용 통계
        cur.execute("""
            SELECT 
                COUNT(*) as total_rides,
                COALESCE(SUM(distance), 0) as total_distance,
                COALESCE(SUM(duration_minutes), 0) as total_duration,
                COALESCE(AVG(distance), 0) as avg_distance
            FROM bike_usage_logs 
            WHERE user_id = %s AND status = 'completed'
        """, (user_id,))
        stats = cur.fetchone()
        
        # 이번 주 통계
        cur.execute("""
            SELECT 
                COUNT(*) as weekly_rides,
                COALESCE(SUM(distance), 0) as weekly_distance,
                COALESCE(SUM(duration_minutes), 0) as weekly_duration
            FROM bike_usage_logs 
            WHERE user_id = %s AND status = 'completed'
              AND usage_time >= DATE_TRUNC('week', CURRENT_DATE)
        """, (user_id,))
        weekly_stats = cur.fetchone()
        
        # 목표 달성률
        cur.execute("""
            SELECT goal_type, target_value, current_value,
                   CASE WHEN target_value > 0 THEN (current_value / target_value * 100) ELSE 0 END as progress_percent
            FROM cycling_goals 
            WHERE user_id = %s AND status = 'active'
              AND start_date <= CURRENT_DATE AND end_date >= CURRENT_DATE
        """, (user_id,))
        goals_progress = cur.fetchall()

    combined_stats = dict(stats)
    combined_stats.update(dict(weekly_stats))
    combined_stats["goals_progress"] = [dict(goal) for goal in goals_progress]

    return make_response(combined_stats)
