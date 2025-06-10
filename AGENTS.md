# AGENTS.md

> **이 문서는 OpenAI Codex/Assistant가 이 Flask 코드베이스를 이해하고 일관된 방식으로 작업하도록 안내하기 위한 가이드입니다.** 프로젝트 특성에 맞게 자유롭게 수정·확장하십시오.

---

## 🏗️ 프로젝트 개요

* **스택**: Python 3.12, Flask 2.3.x, psycopg2‑binary, PyTest
* **데이터베이스**: PostgreSQL (DDL → `schema.sql`)
* **아키텍처**: *애플리케이션 팩토리 패턴* — `app/__init__.py` 가 `create_app()` 반환
* **라우팅**: 모든 엔드포인트는 `/app/routes/` 블루프린트에 정의
* **배포 목표**: Docker + Gunicorn + Nginx (Reverse Proxy)

---

## 📁 디렉터리 구조

```
.
├── app
│   ├── __init__.py          # application factory (create_app)
│   └── routes
│       └── __init__.py      # blueprint with routes
├── run.py                   # dev server entry (FLASK_ENV=development)
├── requirements.txt         # Python dependencies
├── schema.sql               # PostgreSQL schema (source of truth)
├── docs/ERD.md              # ER diagram & data dictionary
└── tests
    └── test_routes.py       # sample tests
```

> **규칙**
>
> 1. 새 API 추가 → `/app/routes/` 하위에 함수형 뷰 또는 `MethodView` 작성 후 Blueprint 등록.
> 2. DB 스키마 변경 시 `schema.sql`ㆍ`docs/ERD.md` 동시 업데이트.
> 3. 테스트 케이스는 `tests/` 동일 경로 레이아웃 사용 (`tests/test_<module>.py`).

---

## 🔍 코드 스타일 & 린트

* **Black** (line length 88) → `black .`
* **isort** → `isort .`
* **flake8** + **mypy --strict** (0 error)
* 네이밍: 변수·함수 → `snake_case`, 클래스 → `PascalCase`, 상수 → `UPPER_SNAKE_CASE`

### Jinja 템플릿

* 템플릿 파일은 120 columns 이하, 들여쓰기 2 spaces
* XSS 예방을 위해 auto‑escape (Flask Jinja 기본치) 유지

---

## 🛠️ Python 버전 & 종속성 관리

**pyenv + pyenv‑virtualenv**를 사용하여 Python 버전 고정과 가상환경을 간편하게 관리합니다.

### 1. 사전 요구

* `pyenv` ≥ 2.3
* `pyenv-virtualenv` 플러그인 설치

### 2. 설치 & 설정 절차

```bash
# 원하는 버전(예: 3.12.3) 설치
pyenv install 3.11.0

# 프로젝트 전용 가상환경 생성
pyenv virtualenv 3.11.0 likebike

# 현재 디렉터리에서 해당 버전 사용 설정
pyenv local likebike  # .python-version 파일이 생성됨

# 패키지 설치
pip install -r requirements.txt
```

> **Tip**: `.python-version` 파일은 레포에 커밋하여 팀원들이 동일한 버전을 사용하도록 합니다.

### 3. 의존성 추가 방법

```bash
pip install <pkg>
# requirements.txt 갱신
pip freeze > requirements.txt
```

---

## 🚀 실행 & 빌드

| 목적         | 명령                                            |
| ---------- | --------------------------------------------- |
| 로컬 개발      | `python run.py` *(debug mode)*                |
| 전체 테스트     | `pytest -q`                                   |
| 코드 포맷 & 린트 | `make lint` *(black + isort + flake8 + mypy)* |
| Docker 빌드  | `docker compose up --build`                   |

**`run.py` 샘플** (Codex가 새 프로젝트에 자동 생성할 때 참고):

```python
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
```

---

## ✅ CI / 테스트 정책

1. `pytest` 커버리지 ≥ 90 % (`pytest --cov=app`)
2. `make lint` 통과 (Black, isort, flake8, mypy)
3. GitHub Actions (`.github/workflows/ci.yml`) 실패 시 PR 병합 금지

---

## 🔖 커밋 / PR 규칙

* **Conventional Commits** (`feat:`, `fix:`, `docs:`, `test:` …)
* PR 제목: `<scope>: <요약>` 예) `feat(routes): add user signup`
* PR 본문 Template:

  ```md
  ### Description
  ### Testing Done
  ### Screenshots / Logs (optional)
  ```
* 대규모 변경은 **draft PR** 먼저 올려 초기 피드백 확보

---

## 🛡️ 보안 & 성능 지침

* **.env** 또는 Secret Manager로 민감 정보 보호 (절대 커밋 금지)
* 외부 HTTP 호출은 `requests` 대신 **aiohttp** 사용 ↔ async 지원
* N + 1 쿼리 방지 — 쿼리 리뷰 요청
* 경계 조건: 각 요청 200 ms 초과 시 `after_request` 로깅

---

## 🧩 기능 확장 시 가이드

| 항목          | 위치                         | 동반 테스트                    |
| ----------- | -------------------------- | ------------------------- |
| 새 API 엔드포인트 | `/app/routes/<feature>.py` | `tests/test_<feature>.py` |
| 커스텀 CLI 명령  | `/app/cli/<command>.py`    | `tests/cli/`              |
| 스크립트/잡      | `/scripts/` *(루트 추가)*      | `tests/scripts/`          |

---

## ❓ FAQ

| 질문                       | 답변                                                                  |
| ------------------------ | ------------------------------------------------------------------- |
| Codex에게 이 문서를 무시시키려면?    | 실행 시 `--no-project-doc` 플래그 사용 또는 env `CODEX_DISABLE_PROJECT_DOC=1` |
| 여러 AGENTS.md 충돌 시 우선순위는? | **더 깊은 경로(하위 폴더)** 문서가 우선 적용                                        |
| 테스트 커버리지 목표 조정?          | 본 파일의 `CI / 테스트 정책` 섹션을 업데이트하고 CI 설정 동기화                            |

---

> **변경 이력**
>
> * 2025‑06‑10 — 프로젝트 디렉터리 구조 기반 초기화 (by Codex Assistant)
