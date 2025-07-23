# LikeBike 백엔드

LikeBike는 자전거 이용 활성화를 위한 게이미피케이션 플랫폼입니다. 이 저장소는 Flask 2.3 기반의 REST API 서버이며 Swagger UI로 모든 엔드포인트를 문서화합니다. 현재 버전은 **1.0.0**입니다.

## 프로젝트 구조

```
.
├── app
│   ├── __init__.py          # 애플리케이션 팩토리
│   └── routes               # 각 기능별 블루프린트
│       └── __init__.py
├── run.py                   # 개발 서버 진입점
├── requirements.txt         # 파이썬 의존성 목록
├── schema.sql               # PostgreSQL 스키마
├── docs/ERD.md              # ER 다이어그램
└── tests                    # PyTest 테스트 모음
    └── test_routes.py
```

- `app/__init__.py`에서 `create_app` 함수가 앱을 생성합니다.
- `/app/routes/` 하위 모듈에 사용자 관리, 커뮤니티, 퀴즈, 추천 코스, 파일 업로드 등 여러 API가 정의되어 있습니다.
- `tests/` 디렉터리에는 각 라우트에 대한 단위 테스트가 포함되어 있습니다.

## 실행 방법

가상환경을 활성화한 뒤 의존성을 설치합니다.

```bash
pip install -r requirements.txt
```

개발 서버를 실행하려면 다음 명령을 사용합니다.

```bash
python run.py
```

서버가 실행되면 `http://localhost:3000/test` 에 접속해 "hello world" 응답을 확인할 수 있습니다.

## 환경 변수

서비스 구동 전 다음 환경 변수를 설정하세요(예: `.env` 파일).

- `DATABASE_URL` 혹은 `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
- `JWT_SECRET_KEY`
- `KAKAO_REST_API_KEY` / `KAKAO_REDIRECT_URI`
- `CLOVA_API_KEY`
- `NCP_ACCESS_KEY` / `NCP_SECRET_KEY` / `NCP_BUCKET_NAME`
- `NCP_REGION` (기본값 `kr-standard`), `NCP_ENDPOINT` (기본값 `https://kr.object.ncloudstorage.com`)
- `PORT` (기본값 `3000`)

## API 문서

Swagger UI를 통해 모든 API를 손쉽게 테스트할 수 있습니다.

- **Swagger UI**: <http://localhost:3000/apidocs/>
- **API 스펙 JSON**: <http://localhost:3000/apispec.json>

자세한 사용 방법은 [SWAGGER_GUIDE.md](./SWAGGER_GUIDE.md)를 참고하세요.

### 인증

대부분의 엔드포인트는 JWT 인증이 필요합니다.

1. `POST /users` 엔드포인트로 카카오 토큰을 전송해 회원가입/로그인
2. 응답으로 받은 `access_token`을 Swagger UI의 "Authorize" 버튼에 입력
3. 형식: `Bearer {발급받은_토큰}`

관리자용 API는 추가로 `X-Admin: true` 헤더를 요구합니다.

### Clova X를 활용한 퀴즈 생성

관리자 엔드포인트 `/admin/quizzes/generate`에 `prompt` 값을 담아 POST 요청하면 Clova X를 이용해 퀴즈를 생성합니다. `CLOVA_API_KEY`가 설정되어 있어야 합니다.

### 일일 사용 제한

일부 기능은 남용을 방지하기 위해 다음과 같이 일일 호출 횟수가 제한됩니다.

- **자전거 활동 기록**: 하루 1회만 등록 가능
- **코스 추천**: 하루 2회만 등록 가능

## 데이터베이스 스키마

`schema.sql` 파일에 PostgreSQL 스키마가 정의되어 있으며, 사용자, 퀴즈, 뉴스, 자전거 기록, 커뮤니티 게시글 등 여러 테이블을 포함합니다. 자세한 테이블 구조는 `docs/ERD.md`에서 확인할 수 있습니다.

## 테스트 실행

```bash
pytest -q
```

## 코드 스타일 검사

```bash
black .
isort .
flake8
mypy --strict
```
