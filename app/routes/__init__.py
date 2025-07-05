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
