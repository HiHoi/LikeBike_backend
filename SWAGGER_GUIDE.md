# LikeBike API Swagger 문서

## 📋 개요

LikeBike 백엔드 API는 Swagger UI를 통해 문서화되어 있으며, 쉽게 테스트하고 사용할 수 있습니다.

## 🔗 Swagger UI 접근

서버 실행 후 다음 URL에서 Swagger UI를 확인할 수 있습니다:

- **개발 환경**: http://localhost:3000/apidocs/
- **프로덕션 환경**: https://your-domain.com/apidocs/

## 🔐 인증 방법

### 1. JWT 토큰 획득

1. `/users` POST 엔드포인트로 카카오 토큰을 사용해 회원가입/로그인
2. 응답에서 `access_token` 획득

### 2. Swagger UI에서 인증 설정

1. Swagger UI 상단의 **Authorize** 버튼 클릭
2. **JWT** 섹션에 `Bearer {your_jwt_token}` 입력
3. **AdminHeader** 섹션에 관리자 API 사용시 `true` 입력

## 📚 API 카테고리

### Users (사용자 관리)

- 회원가입/로그인
- 프로필 조회/수정/삭제
- 로그아웃/토큰 새로고침

### Quizzes (퀴즈)

- 퀴즈 목록 조회
- 퀴즈 시도
- 퀴즈 생성/수정/삭제 (관리자)
- AI 퀴즈 생성 (관리자)
- 오늘 퀴즈 시도 여부 조회

### News (뉴스)

- 뉴스 목록 조회
- 뉴스 상세 조회
- 뉴스 생성/수정/삭제 (관리자)

### Bike Logs (자전거 로그)

- 자전거 이용 기록 생성
- 하루 한 번만 등록 가능
- 이용 기록 목록 조회
- 이용 기록 수정/삭제
- 보상 내역 조회
- 사이클링 목표 관리
- 사용자 통계 조회

### Course Recommendations (코스 추천)

- 코스 추천 등록
- 하루 두 번까지만 가능
- 코스 추천 목록 조회
- 오늘 등록 횟수 조회

### Storage (파일 업로드)

- 파일 업로드
- 파일 목록 조회 (관리자)
- 파일 삭제 (관리자)

### Community (커뮤니티)

- 게시글 목록 조회/작성
- 게시글 상세 조회
- 댓글 작성
- 좋아요 토글
- 안전 신고 관리

### System (시스템)

- 서버 상태 확인

## 🛠️ 사용 팁

### 1. 테스트 시나리오

1. **사용자 등록**: `/users` POST로 회원가입
2. **토큰 설정**: Authorize 버튼으로 JWT 토큰 설정
3. **기능 테스트**: 각 API 엔드포인트 테스트
4. **관리자 기능**: X-Admin 헤더와 함께 관리자 API 테스트

### 2. 공통 응답 형식

모든 API는 다음과 같은 일관된 응답 형식을 사용합니다:

```json
{
  "code": 200,
  "message": "OK",
  "data": [...]
}
```

### 3. 에러 처리

- `400 Bad Request`: 잘못된 요청 데이터
- `401 Unauthorized`: JWT 토큰 없음/무효
- `403 Forbidden`: 관리자 권한 필요
- `404 Not Found`: 리소스 없음
- `500 Internal Server Error`: 서버 오류

## 📖 추가 문서

- [API 명세서](./API_DOCUMENTATION.md): 상세한 API 문서
- [ERD](./docs/ERD.md): 데이터베이스 구조
- [README](./README.md): 프로젝트 개요

## 🔧 개발 모드에서 실행

```bash
# 서버 실행
python run.py

# Swagger UI 접근
open http://localhost:3000/apidocs/
```

## 📝 주의사항

1. **보안**: 프로덕션 환경에서는 HTTPS 사용 필수
2. **토큰 관리**: JWT 토큰은 7일 후 만료됨
3. **관리자 API**: X-Admin 헤더와 관리자 권한이 있는 JWT 토큰 필요
4. **테스트**: 개발 환경에서만 테스트용 데이터 사용

## 🆘 문제 해결

### 인증 오류

- JWT 토큰이 올바르게 설정되었는지 확인
- 토큰 만료 시 `/users/refresh`로 새로고침

### 관리자 권한 오류

- X-Admin 헤더가 'true'로 설정되었는지 확인
- 관리자 권한이 있는 사용자인지 확인

### API 응답 오류

- 요청 데이터 형식이 올바른지 확인
- 필수 파라미터가 누락되지 않았는지 확인
