# LikeBike Backend API 명세서

## 📋 목차

1. [개요](#개요)
2. [사용자 관리 API](#사용자-관리-api)
3. [퀴즈 API](#퀴즈-api)
4. [뉴스 API](#뉴스-api)
5. [자전거 이용 로그 API](#자전거-이용-로그-api)
6. [커뮤니티 API](#커뮤니티-api)
7. [공통 응답 형식](#공통-응답-형식)

---

## 📖 개요

### Base URL

- **Production**: `https://port-0-likebike-backend-mc4iz1js1403f457.sel5.cloudtype.app`
- **Development**: `http://localhost:3000`

### 인증

이 API는 JWT(JSON Web Token) 기반 인증을 사용합니다.

- **사용자 인증**: 대부분의 API에서 `Authorization: Bearer {jwt_token}` 헤더 필요
- **관리자 API**: JWT 토큰과 함께 `X-Admin: true` 헤더 필요
- **토큰 만료**: JWT 토큰은 7일 후 만료됨
- **공개 엔드포인트**: 일부 엔드포인트는 인증 없이 접근 가능 (회원가입, 일부 목록 조회 등)

#### 인증이 필요 없는 API

- `POST /users` (회원가입/로그인)
- `GET /test` (테스트 엔드포인트)

#### JWT 토큰 획득

1. 카카오 로그인을 통해 `POST /users`로 회원가입/로그인
2. 응답에서 `access_token` 획득
3. 이후 모든 API 요청 시 `Authorization: Bearer {access_token}` 헤더 포함

### 응답 형식

모든 API는 JSON 형식으로 응답하며, 다음과 같은 구조를 가집니다:

```json
{
  "code": 200,
  "message": "OK",
  "data": [...]
}
```

- `code`: HTTP 상태 코드
- `message`: HTTP 상태 메시지
- `data`: 응답 데이터 (항상 배열 형태)

---

## 👤 사용자 관리 API

### 1. 사용자 등록/로그인

**POST** `/users`

카카오 토큰을 사용하여 사용자를 등록하거나 로그인합니다.

**Request Body:**

```json
{
  "access_token": "카카오 액세스 토큰"
}
```

**Response (201):**

```json
{
  "code": 201,
  "message": "Created",
  "data": [
    {
      "id": 1,
      "username": "사용자명",
      "email": "user@kakao.com",
      "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    }
  ]
}
```

**Error (400):**

```json
{
  "code": 400,
  "message": "Bad Request",
  "data": [
    {
      "error": "access_token required"
    }
  ]
}
```

### 2. 사용자 정보 수정

**PUT** `/users/profile`

**Headers:** `Authorization: Bearer {jwt_token}`

**Request Body:**

```json
{
  "username": "새로운 사용자명",
  "email": "새로운 이메일"
}
```

**Response (200):**

```json
{
  "code": 200,
  "message": "OK",
  "data": [
    {
      "id": 1,
      "username": "새로운 사용자명",
      "email": "새로운 이메일"
    }
  ]
}
```

### 3. 사용자 삭제

**DELETE** `/users/profile`

**Headers:** `Authorization: Bearer {jwt_token}`

**Response (204):**

```json
{
  "code": 204,
  "message": "No Content",
  "data": []
}
```

### 4. 로그아웃

**POST** `/users/logout`

**Headers:** `Authorization: Bearer {jwt_token}`

현재 세션을 종료합니다. 클라이언트에서 토큰을 삭제해야 합니다.

**Response (200):**

```json
{
  "code": 200,
  "message": "OK",
  "data": [
    {
      "message": "Successfully logged out"
    }
  ]
}
```

### 5. 토큰 새로고침

**POST** `/users/refresh`

**Headers:** `Authorization: Bearer {jwt_token}`

기존 토큰을 새로운 토큰으로 갱신합니다.

**Response (200):**

```json
{
  "code": 200,
  "message": "OK",
  "data": [
    {
      "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    }
  ]
}
```

### 6. 사용자 프로필 조회

**GET** `/users/profile`

**Headers:** `Authorization: Bearer {jwt_token}`

현재 로그인한 사용자의 프로필 정보를 조회합니다.

**Response (200):**

```json
{
  "code": 200,
  "message": "OK",
  "data": [
    {
      "id": 1,
      "username": "사용자명",
      "email": "user@example.com",
      "points": 150,
      "level": 2,
      "experience_points": 250,
      "level_name": "중급자",
      "description": "레벨 설명",
      "benefits": "혜택 정보",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

### 5. 사용자 레벨 업데이트

**PUT** `/users/level`

**Headers:** `Authorization: Bearer {jwt_token}`

경험치를 추가하고 레벨을 업데이트합니다.

**Request Body:**

```json
{
  "experience_points": 50
}
```

**Response (200):**

```json
{
  "code": 200,
  "message": "OK",
  "data": [
    {
      "level": 3,
      "experience_points": 300,
      "level_up": true
    }
  ]
}
```

### 7. 사용자 설정 조회

**GET** `/users/settings`

**Headers:** `Authorization: Bearer {jwt_token}`

**Response (200):**

```json
{
  "code": 200,
  "message": "OK",
  "data": [
    {
      "user_id": 1,
      "notification_enabled": true,
      "location_sharing": false,
      "privacy_level": "public",
      "preferences": {},
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

### 8. 사용자 설정 업데이트

**PUT** `/users/settings`

**Headers:** `Authorization: Bearer {jwt_token}`

**Request Body:**

```json
{
  "notification_enabled": true,
  "location_sharing": true,
  "privacy_level": "private",
  "preferences": { "theme": "dark" }
}
```

**Response (200):**

```json
{
  "code": 200,
  "message": "OK",
  "data": [
    {
      "user_id": 1,
      "notification_enabled": true,
      "location_sharing": true,
      "privacy_level": "private",
      "preferences": { "theme": "dark" },
      "updated_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

### 9. 사용자 인증 내역 조회

**GET** `/users/verifications`

**Headers:** `Authorization: Bearer {jwt_token}`

**Response (200):**

```json
{
  "code": 200,
  "message": "OK",
  "data": [
    {
      "id": 1,
      "user_id": 1,
      "verification_type": "email",
      "source_id": "source123",
      "proof_data": {},
      "status": "verified",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

### 10. 인증 요청 생성

**POST** `/users/verifications`

**Headers:** `Authorization: Bearer {jwt_token}`

**Request Body:**

```json
{
  "verification_type": "email",
  "source_id": "source123",
  "proof_data": { "code": "123456" }
}
```

**Response (201):**

```json
{
  "code": 201,
  "message": "Created",
  "data": [
    {
      "id": 1,
      "user_id": 1,
      "verification_type": "email",
      "source_id": "source123",
      "proof_data": { "code": "123456" },
      "status": "pending",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

### 11. 모든 레벨 정보 조회

**GET** `/levels`

**Headers:** `Authorization: Bearer {jwt_token}`

**Response (200):**

```json
{
  "code": 200,
  "message": "OK",
  "data": [
    {
      "level": 1,
      "level_name": "초보자",
      "description": "자전거를 시작한 초보자",
      "required_exp": 0,
      "benefits": "기본 혜택"
    }
  ]
}
```

---

## 🧩 퀴즈 API

### 1. 퀴즈 생성 (관리자)

**POST** `/admin/quizzes`

**Headers:**

- `Authorization: Bearer {jwt_token}`
- `X-Admin: true`

**Request Body:**

```json
{
  "question": "퀴즈 질문",
  "correct_answer": "정답",
  "answers": ["선택지1", "선택지2", "선택지3", "정답"]
}
```

**Response (201):**

```json
{
  "code": 201,
  "message": "Created",
  "data": [
    {
      "id": 1,
      "question": "퀴즈 질문",
      "correct_answer": "정답",
      "answers": ["선택지1", "선택지2", "선택지3", "정답"]
    }
  ]
}
```

### 2. 퀴즈 수정 (관리자)

**PUT** `/admin/quizzes/{quiz_id}`

**Headers:**

- `Authorization: Bearer {jwt_token}`
- `X-Admin: true`

**Request Body:**

```json
{
  "question": "수정된 퀴즈 질문",
  "correct_answer": "수정된 정답",
  "answers": ["선택지1", "선택지2", "선택지3", "수정된 정답"]
}
```

**Response (200):**

```json
{
  "code": 200,
  "message": "OK",
  "data": [
    {
      "id": 1,
      "question": "수정된 퀴즈 질문",
      "correct_answer": "수정된 정답",
      "answers": ["선택지1", "선택지2", "선택지3", "수정된 정답"]
    }
  ]
}
```

### 3. 퀴즈 삭제 (관리자)

**DELETE** `/admin/quizzes/{quiz_id}`

**Headers:**

- `Authorization: Bearer {jwt_token}`
- `X-Admin: true`

**Response (204):**

````json
{
  "code": 204,
  "message": "No Content",
  "data": []
}

### 4. 퀴즈 목록 조회

**GET** `/quizzes`

**Headers:** `Authorization: Bearer {jwt_token}`

**Response (200):**

```json
{
  "code": 200,
  "message": "OK",
  "data": [
    {
      "id": 1,
      "question": "퀴즈 질문"
    },
    {
      "id": 2,
      "question": "또 다른 퀴즈 질문"
    }
  ]
}
````

### 5. 퀴즈 시도

**POST** `/quizzes/{quiz_id}/attempt`

**Headers:** `Authorization: Bearer {jwt_token}`

**Request Body:**

```json
{
  "answer": "사용자 답변"
}
```

**Response (200):**

```json
{
  "code": 200,
  "message": "OK",
  "data": [
    {
      "is_correct": true,
      "reward_given": true,
      "points_earned": 10,
      "experience_earned": 5
    }
  ]
}
```

### 6. AI 퀴즈 생성 (관리자)

**POST** `/admin/quizzes/generate`

**Headers:**

- `Authorization: Bearer {jwt_token}`
- `X-Admin: true`

**Request Body:**

```json
{
  "prompt": "자전거 안전에 관한 퀴즈를 만들어주세요"
}
```

**Response (201):**

```json
{
  "code": 201,
  "message": "Created",
  "data": [
    {
      "id": 1,
      "question": "생성된 퀴즈 질문",
      "correct_answer": "생성된 정답"
    }
  ]
}
```

---

## 📰 뉴스 API

### 1. 뉴스 생성 (관리자)

**POST** `/admin/news`

**Headers:**

- `Authorization: Bearer {jwt_token}`
- `X-Admin: true`

**Request Body:**

```json
{
  "title": "뉴스 제목",
  "content": "뉴스 내용"
}
```

**Response (201):**

```json
{
  "code": 201,
  "message": "Created",
  "data": [
    {
      "id": 1,
      "title": "뉴스 제목",
      "content": "뉴스 내용",
      "published_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

### 2. 뉴스 수정 (관리자)

**PUT** `/admin/news/{news_id}`

**Headers:**

- `Authorization: Bearer {jwt_token}`
- `X-Admin: true`

**Request Body:**

```json
{
  "title": "수정된 뉴스 제목",
  "content": "수정된 뉴스 내용"
}
```

**Response (200):**

```json
{
  "code": 200,
  "message": "OK",
  "data": [
    {
      "id": 1,
      "title": "수정된 뉴스 제목",
      "content": "수정된 뉴스 내용",
      "published_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

### 3. 뉴스 삭제 (관리자)

**DELETE** `/admin/news/{news_id}`

**Headers:**

- `Authorization: Bearer {jwt_token}`
- `X-Admin: true`

**Response (204):**

````json
{
  "code": 204,
  "message": "No Content",
  "data": []
}

### 4. 뉴스 목록 조회

**GET** `/news`

**Headers:** `Authorization: Bearer {jwt_token}`

**Response (200):**

```json
{
  "code": 200,
  "message": "OK",
  "data": [
    {
      "id": 1,
      "title": "뉴스 제목",
      "content": "뉴스 내용",
      "published_at": "2024-01-01T00:00:00Z"
    }
  ]
}
````

### 5. 뉴스 상세 조회

**GET** `/news/{news_id}`

**Headers:** `Authorization: Bearer {jwt_token}`

**Response (200):**

```json
{
  "code": 200,
  "message": "OK",
  "data": [
    {
      "id": 1,
      "title": "뉴스 제목",
      "content": "뉴스 내용",
      "published_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

---

## 🚴 자전거 이용 로그 API

### 1. 자전거 이용 로그 생성

**POST** `/users/bike-logs`

**Headers:** `Authorization: Bearer {jwt_token}`

자전거 이용 기록을 생성하고 보상을 지급합니다.

**Request Body:**

```json
{
  "description": "한강 라이딩",
  "start_latitude": 37.5665,
  "start_longitude": 126.978,
  "end_latitude": 37.5702,
  "end_longitude": 126.9861,
  "distance": 5.2,
  "duration_minutes": 45,
  "start_time": "2024-01-01T09:00:00Z",
  "end_time": "2024-01-01T09:45:00Z"
}
```

**Response (201):**

```json
{
  "code": 201,
  "message": "Created",
  "data": [
    {
      "id": 1,
      "user_id": 1,
      "description": "한강 라이딩",
      "start_latitude": 37.5665,
      "start_longitude": 126.978,
      "end_latitude": 37.5702,
      "end_longitude": 126.9861,
      "distance": 5.2,
      "duration_minutes": 45,
      "start_time": "2024-01-01T09:00:00Z",
      "end_time": "2024-01-01T09:45:00Z",
      "usage_time": "2024-01-01T09:00:00Z",
      "points_earned": 15,
      "experience_earned": 8
    }
  ]
}
```

### 2. 자전거 이용 로그 목록 조회

**GET** `/users/bike-logs`

**Headers:** `Authorization: Bearer {jwt_token}`

**Response (200):**

```json
{
  "code": 200,
  "message": "OK",
  "data": [
    {
      "id": 1,
      "user_id": 1,
      "description": "한강 라이딩",
      "usage_time": "2024-01-01T09:00:00Z"
    }
  ]
}
```

### 3. 자전거 이용 로그 수정

**PUT** `/bike-logs/{log_id}`

**Headers:** `Authorization: Bearer {jwt_token}`

**Request Body:**

```json
{
  "description": "수정된 설명"
}
```

**Response (200):**

```json
{
  "code": 200,
  "message": "OK",
  "data": [
    {
      "id": 1,
      "user_id": 1,
      "description": "수정된 설명",
      "usage_time": "2024-01-01T09:00:00Z"
    }
  ]
}
```

### 4. 자전거 이용 로그 삭제

**DELETE** `/bike-logs/{log_id}`

**Headers:** `Authorization: Bearer {jwt_token}`

**Response (204):**

```json
{
  "code": 204,
  "message": "No Content",
  "data": []
}
```

### 5. 사용자 보상 내역 조회

**GET** `/users/rewards`

**Headers:** `Authorization: Bearer {jwt_token}`

**Response (200):**

```json
{
  "code": 200,
  "message": "OK",
  "data": [
    {
      "id": 1,
      "user_id": 1,
      "source_type": "bike_usage",
      "source_id": 1,
      "points": 15,
      "experience_points": 8,
      "reward_reason": "자전거 이용 (5.2km)",
      "created_at": "2024-01-01T09:45:00Z"
    }
  ]
}
```

### 6. 사이클링 목표 조회

**GET** `/users/cycling-goals`

**Headers:** `Authorization: Bearer {jwt_token}`

**Response (200):**

```json
{
  "code": 200,
  "message": "OK",
  "data": [
    {
      "id": 1,
      "user_id": 1,
      "goal_type": "distance",
      "target_value": 100,
      "current_value": 45.2,
      "period_type": "monthly",
      "status": "active",
      "start_date": "2024-01-01",
      "end_date": "2024-01-31",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

### 7. 사이클링 목표 생성

**POST** `/users/cycling-goals`

**Headers:** `Authorization: Bearer {jwt_token}`

**Request Body:**

```json
{
  "goal_type": "distance",
  "target_value": 100,
  "period_type": "monthly",
  "start_date": "2024-01-01",
  "end_date": "2024-01-31"
}
```

**Response (201):**

```json
{
  "code": 201,
  "message": "Created",
  "data": [
    {
      "id": 1,
      "user_id": 1,
      "goal_type": "distance",
      "target_value": 100,
      "current_value": 0,
      "period_type": "monthly",
      "status": "active",
      "start_date": "2024-01-01",
      "end_date": "2024-01-31",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

### 8. 사용자 업적 조회

**GET** `/users/achievements`

**Headers:** `Authorization: Bearer {jwt_token}`

**Response (200):**

```json
{
  "code": 200,
  "message": "OK",
  "data": [
    {
      "id": 1,
      "user_id": 1,
      "achievement_type": "distance",
      "achievement_name": "첫 10km 달성",
      "description": "총 10km 이상 라이딩 완료",
      "achieved_at": "2024-01-05T15:30:00Z"
    }
  ]
}
```

### 9. 사용자 통계 조회

**GET** `/users/stats`

**Headers:** `Authorization: Bearer {jwt_token}`

**Response (200):**

```json
{
  "code": 200,
  "message": "OK",
  "data": [
    {
      "total_rides": 15,
      "total_distance": 127.5,
      "total_duration": 680,
      "avg_distance": 8.5,
      "weekly_rides": 3,
      "weekly_distance": 25.2,
      "weekly_duration": 150,
      "goals_progress": [
        {
          "goal_type": "distance",
          "target_value": 100,
          "current_value": 45.2,
          "progress_percent": 45.2
        }
      ]
    }
  ]
}
```

---

## 💬 커뮤니티 API

### 1. 게시글 목록 조회

**GET** `/community/posts`

**Headers:** `Authorization: Bearer {jwt_token}`

**Query Parameters:**

- `type`: 게시글 타입 (optional)
- `page`: 페이지 번호 (default: 1)
- `limit`: 페이지당 개수 (default: 20)

**Response (200):**

```json
{
  "code": 200,
  "message": "OK",
  "data": [
    {
      "id": 1,
      "user_id": 1,
      "title": "게시글 제목",
      "content": "게시글 내용",
      "post_type": "general",
      "likes_count": 5,
      "comments_count": 3,
      "status": "active",
      "created_at": "2024-01-01T00:00:00Z",
      "username": "작성자명",
      "level": 2
    }
  ]
}
```

### 2. 게시글 작성

**POST** `/community/posts`

**Headers:** `Authorization: Bearer {jwt_token}`

**Request Body:**

```json
{
  "title": "게시글 제목",
  "content": "게시글 내용",
  "post_type": "general"
}
```

**Response (201):**

```json
{
  "code": 201,
  "message": "Created",
  "data": [
    {
      "id": 1,
      "user_id": 1,
      "title": "게시글 제목",
      "content": "게시글 내용",
      "post_type": "general",
      "likes_count": 0,
      "comments_count": 0,
      "status": "active",
      "created_at": "2024-01-01T00:00:00Z",
      "points_earned": 2,
      "experience_earned": 1
    }
  ]
}
```

### 3. 게시글 상세 조회

**GET** `/community/posts/{post_id}`

**Headers:** `Authorization: Bearer {jwt_token}`

**Response (200):**

```json
{
  "code": 200,
  "message": "OK",
  "data": [
    {
      "id": 1,
      "user_id": 1,
      "title": "게시글 제목",
      "content": "게시글 내용",
      "post_type": "general",
      "likes_count": 5,
      "comments_count": 3,
      "status": "active",
      "created_at": "2024-01-01T00:00:00Z",
      "username": "작성자명",
      "level": 2,
      "comments": [
        {
          "id": 1,
          "post_id": 1,
          "user_id": 2,
          "content": "댓글 내용",
          "parent_comment_id": null,
          "created_at": "2024-01-01T01:00:00Z",
          "username": "댓글작성자",
          "level": 1
        }
      ]
    }
  ]
}
```

### 4. 댓글 작성

**POST** `/community/posts/{post_id}/comments`

**Headers:** `Authorization: Bearer {jwt_token}`

**Request Body:**

```json
{
  "content": "댓글 내용",
  "parent_comment_id": null
}
```

**Response (201):**

```json
{
  "code": 201,
  "message": "Created",
  "data": [
    {
      "id": 1,
      "post_id": 1,
      "user_id": 2,
      "content": "댓글 내용",
      "parent_comment_id": null,
      "created_at": "2024-01-01T01:00:00Z"
    }
  ]
}
```

### 5. 게시글 좋아요 토글

**POST** `/community/posts/{post_id}/like`

**Headers:** `Authorization: Bearer {jwt_token}`

**Response (200):**

```json
{
  "code": 200,
  "message": "OK",
  "data": [
    {
      "liked": true,
      "likes_count": 6
    }
  ]
}
```

### 6. 안전 신고 내역 조회

**GET** `/users/safety-reports`

**Headers:** `Authorization: Bearer {jwt_token}`

**Response (200):**

```json
{
  "code": 200,
  "message": "OK",
  "data": [
    {
      "id": 1,
      "user_id": 1,
      "report_type": "pothole",
      "latitude": 37.5665,
      "longitude": 126.978,
      "description": "도로에 큰 구멍이 있어요",
      "status": "pending",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

### 7. 안전 신고 생성

**POST** `/users/safety-reports`

**Headers:** `Authorization: Bearer {jwt_token}`

**Request Body:**

```json
{
  "report_type": "pothole",
  "latitude": 37.5665,
  "longitude": 126.978,
  "description": "도로에 큰 구멍이 있어요"
}
```

**Response (201):**

```json
{
  "code": 201,
  "message": "Created",
  "data": [
    {
      "id": 1,
      "user_id": 1,
      "report_type": "pothole",
      "latitude": 37.5665,
      "longitude": 126.978,
      "description": "도로에 큰 구멍이 있어요",
      "status": "pending",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

---

## 🔧 기타 API

### 테스트 엔드포인트

**GET** `/test`

서버 상태를 확인하는 테스트 엔드포인트입니다.

**Response (200):**

```json
{
  "code": 200,
  "message": "OK",
  "data": ["hello world"]
}
```

---

## 📊 공통 응답 형식

### 성공 응답

모든 성공한 API 요청은 다음과 같은 형식으로 응답됩니다:

```json
{
  "code": 200,
  "message": "OK",
  "data": [
    {
      "id": 1,
      "name": "example"
    }
  ]
}
```

### 에러 응답

모든 에러 응답은 다음과 같은 형식을 가집니다:

```json
{
  "code": 400,
  "message": "Bad Request",
  "data": [
    {
      "error": "에러 메시지"
    }
  ]
}
```

### HTTP 상태 코드

- `200 OK`: 요청 성공
- `201 Created`: 리소스 생성 성공
- `204 No Content`: 성공 (응답 내용 없음)
- `400 Bad Request`: 잘못된 요청 (필수 파라미터 누락, 형식 오류 등)
- `403 Forbidden`: 권한 없음 (관리자 권한 필요)
- `404 Not Found`: 리소스를 찾을 수 없음
- `500 Internal Server Error`: 서버 내부 오류
- `502 Bad Gateway`: 외부 API 호출 실패 (Clova API 등)

### 보상 시스템

#### 포인트 및 경험치 지급 기준

- **자전거 이용 로그 생성**:
  - 기본: 5포인트 + 3경험치
  - 거리별 추가 보상: 1km당 2포인트 + 1경험치
- **퀴즈 정답**: 10포인트 + 5경험치 (처음 정답 시에만)
- **게시글 작성**: 2포인트 + 1경험치
- **댓글 작성**: 1포인트 + 1경험치

#### 레벨 시스템

- 경험치 누적에 따라 자동으로 레벨업
- 각 레벨별로 다른 혜택 제공
- 레벨업 시 `level_up: true` 응답

### 데이터 타입 설명

#### 게시글 타입 (post_type)

- `general`: 일반 게시글
- `question`: 질문 게시글
- `tip`: 팁 공유 게시글
- `review`: 리뷰 게시글

#### 목표 타입 (goal_type)

- `distance`: 거리 목표 (km)
- `duration`: 시간 목표 (분)
- `frequency`: 횟수 목표 (회)

#### 기간 타입 (period_type)

- `daily`: 일일 목표
- `weekly`: 주간 목표
- `monthly`: 월간 목표

#### 신고 타입 (report_type)

- `pothole`: 도로 구멍
- `obstacle`: 장애물
- `dangerous_area`: 위험 지역
- `traffic`: 교통 문제
- `other`: 기타

### 페이지네이션

목록 조회 API는 다음 파라미터를 지원합니다:

- `page`: 페이지 번호 (1부터 시작, 기본값: 1)
- `limit`: 페이지당 항목 수 (기본값: 20, 최대: 100)

### 날짜 형식

모든 날짜는 ISO 8601 형식을 사용합니다:

- `YYYY-MM-DDTHH:mm:ssZ` (UTC 기준)
- 예: `2024-01-01T09:00:00Z`

### 위치 정보

위도/경도는 WGS84 좌표계를 사용합니다:

- `latitude`: 위도 (-90 ~ 90)
- `longitude`: 경도 (-180 ~ 180)

---

## 📝 업데이트 이력

### v1.0.0 (2025-07-05)

- 초기 API 명세서 작성
- 사용자, 퀴즈, 뉴스, 자전거 로그, 커뮤니티 API 정의
- 보상 시스템 및 레벨 시스템 구현
- 실제 응답 형식에 맞게 문서 업데이트

---

## 🔗 관련 링크

- [GitHub Repository](https://github.com/HiHoi/LikeBike_backend)
- [ERD 문서](./docs/ERD.md)
- [프로젝트 README](./README.md)

---

## 📞 문의

API 사용 중 문제가 발생하거나 문의사항이 있으시면 다음으로 연락해 주세요:

- 이메일: [개발팀 이메일]
- GitHub Issues: [Repository Issues 페이지]

---

_본 문서는 2025년 7월 5일 기준으로 작성되었습니다._
