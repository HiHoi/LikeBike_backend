from flask import Blueprint, request

from ..utils.responses import make_response
from ..db import get_db

bp = Blueprint("community", __name__)


@bp.route("/community/posts", methods=["GET"])
def list_posts():
    """커뮤니티 게시글 목록 조회"""
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
def create_post():
    """새 게시글 작성"""
    data = request.get_json() or {}
    user_id = data.get("user_id")
    title = data.get("title")
    content = data.get("content")
    post_type = data.get("post_type", "general")
    
    if not all([user_id, title, content]):
        return make_response({"error": "user_id, title, content required"}, 400)
    
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
def create_comment(post_id):
    """댓글 작성"""
    data = request.get_json() or {}
    user_id = data.get("user_id")
    content = data.get("content")
    parent_comment_id = data.get("parent_comment_id")
    
    if not all([user_id, content]):
        return make_response({"error": "user_id, content required"}, 400)
    
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
def toggle_like(post_id):
    """좋아요 토글"""
    data = request.get_json() or {}
    user_id = data.get("user_id")
    
    if not user_id:
        return make_response({"error": "user_id required"}, 400)
    
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


@bp.route("/users/<int:user_id>/safety-reports", methods=["GET"])
def get_safety_reports(user_id):
    """안전 신고 내역 조회"""
    db = get_db()
    with db.cursor() as cur:
        cur.execute("""
            SELECT * FROM safety_reports 
            WHERE user_id = %s 
            ORDER BY created_at DESC
        """, (user_id,))
        reports = cur.fetchall()

    return make_response([dict(report) for report in reports])


@bp.route("/users/<int:user_id>/safety-reports", methods=["POST"])
def create_safety_report(user_id):
    """안전 신고 생성"""
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
