# LikeBike Backend

This project provides a small Flask backend with a simple project structure that is easy to extend and test. It includes an example route and a basic test suite using `pytest`.

## Project Structure

```
.
├── app
│   ├── __init__.py          # application factory
│   └── routes
│       └── __init__.py      # blueprint with routes
├── run.py                   # entry point for development server
├── requirements.txt         # Python dependencies
├── schema.sql               # PostgreSQL schema
├── docs/ERD.md              # ER diagram
└── tests
    └── test_routes.py       # sample tests
```

- `app/__init__.py` defines the `create_app` factory which creates and configures the Flask application.
- `app/routes/__init__.py` contains a blueprint with a single route `/test` that returns `hello world`.
- `run.py` can be executed to run the server locally.
- `tests/` includes a pytest-based test that verifies the `/test` route.

## Running the Application

Install dependencies (preferably in a virtual environment):

```bash
pip install -r requirements.txt
```

Run the development server:

```bash
python run.py
```

Visit `http://localhost:5000/test` and you should see `hello world`.

### Generating quizzes with Clova X

There is an administrative endpoint that generates a quiz using Naver Clova X.
Send a POST request to `/admin/quizzes/generate` with a JSON body containing a
`prompt` field. The service will call Clova X, create a quiz record and return
the created question and answer. Set the `CLOVA_API_KEY` environment variable to
your Clova API key.

## Database Schema

The PostgreSQL schema is defined in `schema.sql`. It outlines tables for users,
quizzes, bike usage logs, news, user routes and reward tracking. See
`docs/ERD.md` for the entity relationship diagram.

## Running Tests

```
pytest
```
