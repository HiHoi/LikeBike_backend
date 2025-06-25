from http import HTTPStatus
from typing import Any

from flask import jsonify


def make_response(data: Any = None, code: int = 200):
    """Return a standardized JSON response with data always as a list."""
    if data is None:
        payload = []
    elif isinstance(data, list):
        payload = data
    else:
        payload = [data]

    message = HTTPStatus(code).phrase
    return jsonify({"code": code, "message": message, "data": payload}), code
