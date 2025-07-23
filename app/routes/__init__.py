from flask import Blueprint

from ..utils.responses import make_response

main = Blueprint("main", __name__)


@main.route("/test")
def test_route():
    """
    테스트 엔드포인트
    ---
    tags:
      - System
    summary: 서버 상태 확인
    description: 서버가 정상적으로 동작하는지 확인하는 테스트 엔드포인트입니다.
    responses:
      200:
        description: 서버 정상 동작
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
                type: string
              example: ["hello world"]
    """
    return make_response("hello world")


# 모든 라우트 블루프린트를 등록하는 함수
def register_routes(app):
    """애플리케이션에 모든 라우트를 등록"""
    from . import users, bike_logs, community, news, quizzes, storage, rewards, recommendations

    app.register_blueprint(main)
    app.register_blueprint(users.bp)
    app.register_blueprint(bike_logs.bp)
    app.register_blueprint(community.bp)
    app.register_blueprint(news.bp)
    app.register_blueprint(quizzes.bp)
    app.register_blueprint(storage.bp
    app.register_blueprint(recommendations.bp)
    app.register_blueprint(rewards.bp)
