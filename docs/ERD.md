# Entity Relationship Diagram

```mermaid
erDiagram
    users {
        integer id PK
        varchar kakao_id
        varchar username
        varchar email
        integer points
        integer level
        integer experience_points
        timestamp created_at
    }

    user_levels {
        integer level PK
        varchar level_name
        integer required_exp
        text description
        text benefits
    }

    user_settings {
        integer id PK
        integer user_id FK
        boolean notification_enabled
        boolean location_sharing
        varchar privacy_level
        text preferences
        timestamp updated_at
    }

    user_verifications {
        integer id PK
        integer user_id FK
        varchar verification_type
        integer source_id
        varchar status
        text proof_data
        timestamp verified_at
        timestamp created_at
    }

    quizzes {
        integer id PK
        string question
        enum quiz_type "'multiple_choice', 'ox', 'short_answer'"
        string correct_answer
        jsonb answers
        varchar hint_link
        text explanation
        date display_date
        timestamp created_at
    }

    user_quiz_attempts {
        integer id PK
        integer user_id FK
        integer quiz_id FK
        boolean is_correct
        timestamp attempted_at
    }

    quiz_explanations {
        integer id PK
        integer quiz_id FK
        text explanation
        timestamp created_at
    }

    user_quiz_explanation_views {
        integer id PK
        integer user_id FK
        integer quiz_id FK
        boolean reward_given
        timestamp viewed_at
    }

    bike_usage_logs {
        integer id PK
        integer user_id FK
        string description
        varchar bike_photo_url
        varchar safety_gear_photo_url
        varchar verification_status
        integer verified_by_admin_id FK
        text admin_notes
        integer points_awarded
        timestamp started_at
        timestamp verified_at
        timestamp created_at
    }

    course_recommendations {
        integer id PK
        integer user_id FK
        varchar title
        text summary
        text review
        varchar photo_url
        varchar status
        integer points_awarded
        integer reviewed_by_admin_id FK
        text admin_notes
        timestamp reviewed_at
        timestamp created_at
    }

    course_recommendation_places {
        integer id PK
        integer recommendation_id FK
        integer sequence_order
        varchar name
        varchar address_name
        text description
        decimal latitude
        decimal longitude
        text photo_url
        timestamp created_at
    }

    course_recommendation_assets {
        integer id PK
        integer recommendation_id FK
        varchar asset_type
        text url
        timestamp created_at
    }

    routes {
        integer id PK
        integer user_id FK
        varchar name
        string description
        decimal total_distance
        integer estimated_duration
        varchar difficulty_level
        timestamp created_at
    }

    route_points {
        integer id PK
        integer route_id FK
        decimal latitude
        decimal longitude
        integer sequence_order
        varchar point_type
        text description
        timestamp recorded_at
    }

    rewards {
        integer id PK
        integer user_id FK
        varchar source_type
        integer source_id
        integer points
        integer experience_points
        varchar reward_reason
        varchar status
        timestamp created_at
    }

    community_posts {
        integer id PK
        integer user_id FK
        varchar title
        text content
        varchar post_type
        integer likes_count
        integer comments_count
        varchar status
        timestamp created_at
        timestamp updated_at
    }

    post_comments {
        integer id PK
        integer post_id FK
        integer user_id FK
        text content
        integer parent_comment_id FK
        timestamp created_at
    }

    post_likes {
        integer id PK
        integer post_id FK
        integer user_id FK
        timestamp created_at
    }

    safety_reports {
        integer id PK
        integer user_id FK
        varchar report_type
        decimal latitude
        decimal longitude
        text description
        varchar status
        text admin_response
        timestamp resolved_at
        timestamp created_at
    }

    user_achievements {
        integer id PK
        integer user_id FK
        varchar achievement_type
        varchar title
        text description
        integer reward_points
        timestamp achieved_at
    }

    users ||--|| user_levels : "has level"
    users ||--o| user_settings : ""
    users ||--o{ user_verifications : ""
    users ||--o{ user_quiz_attempts : ""
    users ||--o{ user_quiz_explanation_views : ""
    users ||--o{ bike_usage_logs : "creates"
    users ||--o{ bike_usage_logs : "verifies as admin"
    users ||--o{ course_recommendations : "recommends"
    users ||--o{ course_recommendations : "reviews as admin"
    users ||--o{ routes : ""
    users ||--o{ rewards : ""
    users ||--o{ community_posts : "writes"
    users ||--o{ post_comments : "comments"
    users ||--o{ post_likes : "likes"
    users ||--o{ safety_reports : "reports"
    users ||--o{ user_achievements : "earns"

    quizzes ||--o{ user_quiz_attempts : ""
    quizzes ||--o{ quiz_explanations : "has"
    quizzes ||--o{ user_quiz_explanation_views : ""

    course_recommendations ||--o{ course_recommendation_places : "visits"
    course_recommendations ||--o{ course_recommendation_assets : "assets"

    routes ||--o{ route_points : "contains"

    community_posts ||--o{ post_comments : "has"
    community_posts ||--o{ post_likes : "receives"

    post_comments ||--o{ post_comments : "replies"
```

## 주요 기능들 (앱 플로우 기반)

### 1. 개인 자전거 이용 기록 시스템

- **bike_usage_logs**: 자전거 활동 기록 및 검증 시스템
  - 사용자: 활동 시작 체크, 자전거 사진 및 안전 장비 사진 업로드
  - 관리자: 사진 검토 후 포인트 지급 및 활동 승인
  - 검증 상태: pending(대기) → verified(승인) → points_awarded(포인트 지급)
  - 하루 최대 1회 등록 가능

### 2. 지도 & 경로 기능

- **routes**: 사용자 생성 경로 및 추천 경로
- **route_points**: GPS 좌표 기반 상세 경로 정보

### 3. 커뮤니티 기능

- **community_posts**: 게시글 (팁, 질문, 경로 공유 등)
- **post_comments**: 댓글 및 대댓글
- **post_likes**: 좋아요 시스템

### 4. 안전 기능

- **safety_reports**: 안전 관련 신고 (위험 구간, 사고 등)

### 5. 게이미피케이션

- **quizzes**: OX/객관식/단답형 등 다양한 유형의 퀴즈 문제와 채점 규칙
- **user_quiz_attempts**: 사용자 퀴즈 시도 기록 (1회만 가능, 정답 시 포인트 지급)
- **quiz_explanations**: 퀴즈 해설 (정답 시 보여지는 설명)
- **user_quiz_explanation_views**: 해설 조회 기록 및 포인트 지급 관리 (한 번만 지급)
- **user_achievements**: 업적 시스템 (첫 10km, 100km 달성 등)
- **rewards**: 포인트 및 경험치 시스템
- **user_levels**: 레벨 시스템

### 6. 개인 관리

- **user_settings**: 개인 설정 (알림, 프라이버시 등)

### 7. 코스 추천 기능
- **course_recommendations**: 추천 묶음의 메타데이터(제목, 요약, 후기, 검토 상태) 관리
- **course_recommendation_places**: 추천 코스에 포함된 장소 목록 (순서, 좌표, 사진 URL 관리)
- **course_recommendation_assets**: 추천에 첨부된 사진, GPX 등 추가 자료
  - 사용자는 주 2회까지만 추천 가능
  - 관리자 검토 시 admin_notes 기록 가능

이 ERD는 앱 플로우의 실제 기능에 맞춰:

- 🏠 홈화면 (이용 현황, 레벨 정보)
- 🗺️ 지도 (경로 안내, 안전 정보)
- 📊 이용 기록 (사진 업로드, 관리자 검증, 포인트 지급)
- 👥 커뮤니티 (게시글, 댓글, 좋아요)
- ⚙️ 설정 (개인화)
- 🏆 업적 시스템 (레벨업, 포인트)
- 🧠 퀴즈 (1회 도전, 정답 시 포인트 획득)
