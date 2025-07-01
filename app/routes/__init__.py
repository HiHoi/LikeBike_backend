from flask import Blueprint

from ..utils.responses import make_response

main = Blueprint("main", __name__)


@main.route("/test")
def test_route():
    return make_response("hello world")
