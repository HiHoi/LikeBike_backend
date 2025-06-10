import pytest

from app import create_app


@pytest.fixture
def client():
    app = create_app({"TESTING": True})
    with app.test_client() as client:
        yield client


def test_test_route(client):
    response = client.get("/test")
    assert response.status_code == 200
    assert response.data.decode("utf-8") == "hello world"
