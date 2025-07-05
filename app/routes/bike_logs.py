from flask import Blueprint, request

from ..utils.responses import make_response
from ..utils.auth import jwt_required, get_current_user_id

from ..db import get_db

bp = Blueprint("bike_logs", __name__)


@bp.route("/users/bike-logs", methods=["POST"])
@jwt_required
def create_bike_log():
    """
    자전거 이용 로그 생성
    ---
    tags:
      - Bike Logs
    summary: 자전거 이용 기록 생성
    description: 자전거 이용 기록을 생성하고 보상을 지급합니다.
    security:
      - JWT: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - description
          properties:
            description:
              type: string
              description: 라이딩 설명
              example: "한강 라이딩"
            start_latitude:
              type: number
              format: float
              description: 시작점 위도
              example: 37.5665
            start_longitude:
              type: number
              format: float
              description: 시작점 경도
              example: 126.978
            end_latitude:
              type: number
              format: float
              description: 도착점 위도
              example: 37.5702
            end_longitude:
              type: number
              format: float
              description: 도착점 경도
              example: 126.9861
            distance:
              type: number
              format: float
              description: 이동 거리 (km)
              example: 5.2
            duration_minutes:
              type: integer
              description: 소요 시간 (분)
              example: 45
            start_time:
              type: string
              format: date-time
              description: 시작 시간
              example: "2024-01-01T09:00:00Z"
            end_time:
              type: string
              format: date-time
              description: 종료 시간
              example: "2024-01-01T09:45:00Z"
    responses:
      201:
        description: 자전거 로그 생성 성공
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 201
            message:
              type: string
              example: "Created"
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
                  description:
                    type: string
                    example: "한강 라이딩"
                  start_latitude:
                    type: number
                    example: 37.5665
                  start_longitude:
                    type: number
                    example: 126.978
                  end_latitude:
                    type: number
                    example: 37.5702
                  end_longitude:
                    type: number
                    example: 126.9861
                  distance:
                    type: number
                    example: 5.2
                  duration_minutes:
                    type: integer
                    example: 45
                  start_time:
                    type: string
                    example: "2024-01-01T09:00:00Z"
                  end_time:
                    type: string
                    example: "2024-01-01T09:45:00Z"
                  usage_time:
                    type: string
                    example: "2024-01-01T09:00:00Z"
                  points_earned:
                    type: integer
                    example: 15
                  experience_earned:
                    type: integer
                    example: 8
      400:
        description: 잘못된 요청
      401:
        description: 인증 실패
    """
    user_id = get_current_user_id()
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


@bp.route("/users/bike-logs", methods=["GET"])
@jwt_required
def list_bike_logs():
    """
    자전거 이용 로그 목록 조회
    ---
    tags:
      - Bike Logs
    summary: 사용자의 자전거 이용 기록 목록 조회
    description: 현재 사용자의 자전거 이용 기록들을 조회합니다.
    security:
      - JWT: []
    responses:
      200:
        description: 자전거 로그 목록 조회 성공
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
                  description:
                    type: string
                    example: "한강 라이딩"
                  usage_time:
                    type: string
                    format: date-time
                    example: "2024-01-01T09:00:00Z"
      401:
        description: 인증 실패
    """
    user_id = get_current_user_id()
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "SELECT id, user_id, description, usage_time FROM bike_usage_logs WHERE user_id = %s ORDER BY usage_time DESC",
            (user_id,),
        )
        logs = cur.fetchall()

    return make_response(logs)


@bp.route("/bike-logs/<int:log_id>", methods=["PUT"])
@jwt_required
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
@jwt_required
def delete_bike_log(log_id):
    db = get_db()
    with db.cursor() as cur:
        cur.execute("DELETE FROM bike_usage_logs WHERE id = %s", (log_id,))
        if cur.rowcount == 0:
            return make_response({"error": "log not found"}, 404)

    return make_response(None, 204)


@bp.route("/users/rewards", methods=["GET"])
@jwt_required
def get_user_rewards():
    """사용자 포인트 적립 내역 조회"""
    user_id = get_current_user_id()
    db = get_db()
    with db.cursor() as cur:
        cur.execute("""
            SELECT * FROM rewards 
            WHERE user_id = %s 
            ORDER BY created_at DESC
        """, (user_id,))
        rewards = cur.fetchall()

    return make_response([dict(reward) for reward in rewards])


@bp.route("/users/cycling-goals", methods=["GET"])
@jwt_required
def get_cycling_goals():
    """사용자 사이클링 목표 조회"""
    user_id = get_current_user_id()
    db = get_db()
    with db.cursor() as cur:
        cur.execute("""
            SELECT * FROM cycling_goals 
            WHERE user_id = %s 
            ORDER BY created_at DESC
        """, (user_id,))
        goals = cur.fetchall()

    return make_response([dict(goal) for goal in goals])


@bp.route("/users/cycling-goals", methods=["POST"])
@jwt_required
def create_cycling_goal():
    """새로운 사이클링 목표 생성"""
    user_id = get_current_user_id()
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


@bp.route("/users/achievements", methods=["GET"])
@jwt_required
def get_user_achievements():
    """사용자 업적 조회"""
    user_id = get_current_user_id()
    db = get_db()
    with db.cursor() as cur:
        cur.execute("""
            SELECT * FROM user_achievements 
            WHERE user_id = %s 
            ORDER BY achieved_at DESC
        """, (user_id,))
        achievements = cur.fetchall()

    return make_response([dict(achievement) for achievement in achievements])


@bp.route("/users/stats", methods=["GET"])
@jwt_required
def get_user_stats():
    """사용자 통계 조회"""
    user_id = get_current_user_id()
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
