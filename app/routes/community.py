from flask import Blueprint, request

from ..utils.responses import make_response
from ..utils.auth import jwt_required, get_current_user_id
from ..db import get_db

bp = Blueprint("community", __name__)


@bp.route("/community/posts", methods=["GET"])
@jwt_required
def list_posts():
    """
    커뮤니티 게시글 목록 조회
    ---
    tags:
      - Community
    summary: 커뮤니티 게시글 목록 조회
    description: 커뮤니티에 등록된 게시글들의 목록을 조회합니다.
    security:
      - JWT: []
    parameters:
      - in: query
        name: type
        type: string
        description: 게시글 타입 필터
        enum: [general, question, tip, review]
        example: general
      - in: query
        name: page
        type: integer
        description: 페이지 번호
        default: 1
        example: 1
      - in: query
        name: limit
        type: integer
        description: 페이지당 개수
        default: 20
        example: 20
    responses:
      200:
        description: 게시글 목록 조회 성공
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
                  title:
                    type: string
                    example: "자전거 추천 경로"
                  content:
                    type: string
                    example: "한강공원 라이딩 코스 추천합니다!"
                  post_type:
                    type: string
                    example: "general"
                  likes_count:
                    type: integer
                    example: 5
                  comments_count:
                    type: integer
                    example: 3
                  status:
                    type: string
                    example: "active"
                  created_at:
                    type: string
                    format: date-time
                    example: "2024-01-01T00:00:00Z"
                  username:
                    type: string
                    example: "작성자명"
                  level:
                    type: integer
                    example: 2
      401:
        description: 인증 실패
    """
    post_type = request.args.get("type")
    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 20))
    offset = (page - 1) * limit
    
    db = get_db()
    with db.cursor() as cur:
        where_clause = "WHERE cp.status = 'active'"
        params = []
        
        if post_type:
            where_clause += " AND cp.post_type = %s"
            params.append(post_type)
        
        cur.execute(f"""
            SELECT cp.*, u.username, u.level
            FROM community_posts cp
            JOIN users u ON cp.user_id = u.id
            {where_clause}
            ORDER BY cp.created_at DESC
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        posts = cur.fetchall()

    return make_response([dict(post) for post in posts])


@bp.route("/community/posts", methods=["POST"])
@jwt_required
def create_post():
    """
    커뮤니티 게시글 작성
    ---
    tags:
      - Community
    summary: 새로운 커뮤니티 게시글 작성
    description: 커뮤니티에 새로운 게시글을 작성하고 보상을 지급합니다.
    security:
      - JWT: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - title
            - content
          properties:
            title:
              type: string
              description: 게시글 제목
              example: "자전거 추천 경로"
            content:
              type: string
              description: 게시글 내용
              example: "한강공원 라이딩 코스 추천합니다!"
            post_type:
              type: string
              description: 게시글 타입
              enum: [general, question, tip, review]
              default: general
              example: "general"
    responses:
      201:
        description: 게시글 작성 성공
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
                  title:
                    type: string
                    example: "자전거 추천 경로"
                  content:
                    type: string
                    example: "한강공원 라이딩 코스 추천합니다!"
                  post_type:
                    type: string
                    example: "general"
                  likes_count:
                    type: integer
                    example: 0
                  comments_count:
                    type: integer
                    example: 0
                  status:
                    type: string
                    example: "active"
                  created_at:
                    type: string
                    format: date-time
                    example: "2024-01-01T00:00:00Z"
                  points_earned:
                    type: integer
                    example: 2
                  experience_earned:
                    type: integer
                    example: 1
      400:
        description: 잘못된 요청
      401:
        description: 인증 실패
    """
    user_id = get_current_user_id()
    data = request.get_json() or {}
    title = data.get("title")
    content = data.get("content")
    post_type = data.get("post_type", "general")
    
    if not all([title, content]):
        return make_response({"error": "title, content required"}, 400)
    
    db = get_db()
    with db.cursor() as cur:
        cur.execute("""
            INSERT INTO community_posts (user_id, title, content, post_type)
            VALUES (%s, %s, %s, %s)
            RETURNING *
        """, (user_id, title, content, post_type))
        post = cur.fetchone()
        
        # 게시글 작성 보상
        points = 2
        exp = 1
        
        cur.execute("""
            UPDATE users 
            SET points = points + %s, experience_points = experience_points + %s 
            WHERE id = %s
        """, (points, exp, user_id))
        
        cur.execute("""
            INSERT INTO rewards 
            (user_id, source_type, source_id, points, experience_points, reward_reason)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (user_id, "community_post", post["id"], points, exp, "게시글 작성"))

    response_data = dict(post)
    response_data.update({
        "points_earned": points,
        "experience_earned": exp
    })

    return make_response(response_data, 201)


@bp.route("/community/posts/<int:post_id>", methods=["GET"])
def get_post(post_id):
    """게시글 상세 조회"""
    db = get_db()
    with db.cursor() as cur:
        cur.execute("""
            SELECT cp.*, u.username, u.level
            FROM community_posts cp
            JOIN users u ON cp.user_id = u.id
            WHERE cp.id = %s AND cp.status = 'active'
        """, (post_id,))
        post = cur.fetchone()
        
        if not post:
            return make_response({"error": "post not found"}, 404)
        
        # 댓글 조회
        cur.execute("""
            SELECT pc.*, u.username, u.level
            FROM post_comments pc
            JOIN users u ON pc.user_id = u.id
            WHERE pc.post_id = %s
            ORDER BY pc.created_at ASC
        """, (post_id,))
        comments = cur.fetchall()

    post_data = dict(post)
    post_data["comments"] = [dict(comment) for comment in comments]

    return make_response(post_data)


@bp.route("/community/posts/<int:post_id>/comments", methods=["POST"])
@jwt_required
def create_comment(post_id):
    """댓글 작성"""
    user_id = get_current_user_id()
    data = request.get_json() or {}
    content = data.get("content")
    parent_comment_id = data.get("parent_comment_id")
    
    if not content:
        return make_response({"error": "content required"}, 400)
    
    db = get_db()
    with db.cursor() as cur:
        # 게시글 존재 확인
        cur.execute("SELECT id FROM community_posts WHERE id = %s", (post_id,))
        if not cur.fetchone():
            return make_response({"error": "post not found"}, 404)
        
        cur.execute("""
            INSERT INTO post_comments (post_id, user_id, content, parent_comment_id)
            VALUES (%s, %s, %s, %s)
            RETURNING *
        """, (post_id, user_id, content, parent_comment_id))
        comment = cur.fetchone()
        
        # 댓글 수 업데이트
        cur.execute("""
            UPDATE community_posts 
            SET comments_count = comments_count + 1 
            WHERE id = %s
        """, (post_id,))
        
        # 댓글 작성 보상
        points = 1
        exp = 1
        
        cur.execute("""
            UPDATE users 
            SET points = points + %s, experience_points = experience_points + %s 
            WHERE id = %s
        """, (points, exp, user_id))

    return make_response(dict(comment), 201)


@bp.route("/community/posts/<int:post_id>/like", methods=["POST"])
@jwt_required
def toggle_like(post_id):
    """좋아요 토글"""
    user_id = get_current_user_id()
    
    db = get_db()
    with db.cursor() as cur:
        # 기존 좋아요 확인
        cur.execute("""
            SELECT id FROM post_likes 
            WHERE post_id = %s AND user_id = %s
        """, (post_id, user_id))
        existing_like = cur.fetchone()
        
        if existing_like:
            # 좋아요 취소
            cur.execute("""
                DELETE FROM post_likes 
                WHERE post_id = %s AND user_id = %s
            """, (post_id, user_id))
            
            cur.execute("""
                UPDATE community_posts 
                SET likes_count = likes_count - 1 
                WHERE id = %s
            """, (post_id,))
            
            liked = False
        else:
            # 좋아요 추가
            cur.execute("""
                INSERT INTO post_likes (post_id, user_id)
                VALUES (%s, %s)
            """, (post_id, user_id))
            
            cur.execute("""
                UPDATE community_posts 
                SET likes_count = likes_count + 1 
                WHERE id = %s
            """, (post_id,))
            
            liked = True
        
        # 현재 좋아요 수 조회
        cur.execute("""
            SELECT likes_count FROM community_posts WHERE id = %s
        """, (post_id,))
        likes_count = cur.fetchone()["likes_count"]

    return make_response({
        "liked": liked,
        "likes_count": likes_count
    })


@bp.route("/users/safety-reports", methods=["GET"])
@jwt_required
def get_safety_reports():
    """
    안전 신고 내역 조회
    ---
    tags:
      - Community
    summary: 사용자의 안전 신고 내역 조회
    description: 현재 로그인한 사용자가 생성한 안전 신고 내역을 조회합니다.
    security:
      - JWT: []
    responses:
      200:
        description: 안전 신고 내역 조회 성공
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
                  report_type:
                    type: string
                    enum: ["accident", "hazard", "maintenance", "theft"]
                    example: "hazard"
                  latitude:
                    type: number
                    example: 37.5665
                  longitude:
                    type: number
                    example: 126.9780
                  description:
                    type: string
                    example: "도로에 구멍이 있어서 위험합니다"
                  status:
                    type: string
                    enum: ["pending", "reviewed", "resolved"]
                    example: "pending"
                  created_at:
                    type: string
                    format: date-time
                    example: "2024-01-15T10:30:00Z"
                  updated_at:
                    type: string
                    format: date-time
                    example: "2024-01-15T10:30:00Z"
      401:
        description: 인증 실패
    """
    user_id = get_current_user_id()
    db = get_db()
    with db.cursor() as cur:
        cur.execute("""
            SELECT * FROM safety_reports 
            WHERE user_id = %s 
            ORDER BY created_at DESC
        """, (user_id,))
        reports = cur.fetchall()

    return make_response([dict(report) for report in reports])


@bp.route("/users/safety-reports", methods=["POST"])
@jwt_required
def create_safety_report():
    """
    안전 신고 생성
    ---
    tags:
      - Community
    summary: 새로운 안전 신고 생성
    description: 현재 로그인한 사용자가 새로운 안전 신고를 생성합니다.
    security:
      - JWT: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - report_type
            - description
          properties:
            report_type:
              type: string
              enum: ["accident", "hazard", "maintenance", "theft"]
              description: 신고 유형
              example: "hazard"
            latitude:
              type: number
              description: 위도
              example: 37.5665
            longitude:
              type: number
              description: 경도
              example: 126.9780
            description:
              type: string
              description: 신고 내용 설명
              example: "도로에 구멍이 있어서 위험합니다"
    responses:
      201:
        description: 안전 신고 생성 성공
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
              type: object
              properties:
                id:
                  type: integer
                  example: 1
                user_id:
                  type: integer
                  example: 1
                report_type:
                  type: string
                  example: "hazard"
                latitude:
                  type: number
                  example: 37.5665
                longitude:
                  type: number
                  example: 126.9780
                description:
                  type: string
                  example: "도로에 구멍이 있어서 위험합니다"
                status:
                  type: string
                  example: "pending"
                created_at:
                  type: string
                  format: date-time
                  example: "2024-01-15T10:30:00Z"
      400:
        description: 잘못된 요청
        schema:
          type: object
          properties:
            error:
              type: string
              example: "report_type, description required"
      401:
        description: 인증 실패
    """
    user_id = get_current_user_id()
    data = request.get_json() or {}
    report_type = data.get("report_type")
    latitude = data.get("latitude")
    longitude = data.get("longitude")
    description = data.get("description")
    
    if not all([report_type, description]):
        return make_response({"error": "report_type, description required"}, 400)
    
    db = get_db()
    with db.cursor() as cur:
        cur.execute("""
            INSERT INTO safety_reports 
            (user_id, report_type, latitude, longitude, description)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING *
        """, (user_id, report_type, latitude, longitude, description))
        report = cur.fetchone()

    return make_response(dict(report), 201)
