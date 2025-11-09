# 관리자 자전거 활동 등록 가이드

LikeBike 관리자 패널에서는 이용자 대신 자전거 활동을 수기로 등록할 수 있습니다. 이 문서는 새로 추가된 엔드포인트와
검증 흐름을 정리합니다.

## 엔드포인트 요약

| Method | Path | 설명 |
| ------ | ---- | ---- |
| `POST` | `/admin/users/{user_id}/bike-logs` | 관리자가 특정 사용자의 활동을 직접 등록 |

### 요청 본문

- **Content-Type**: `multipart/form-data`
- 파일 업로드와 URL 전달을 모두 지원합니다. 둘 중 하나만 제공해도 됩니다.

| 필드 | 형식 | 필수 | 설명 |
| ---- | ---- | ---- | ---- |
| `description` | text | 예 | 활동 설명 |
| `bike_photo` | file | 아니오 | 자전거 사진 파일. URL과 중복 사용 불필요 |
| `safety_gear_photo` | file | 아니오 | 안전 장비 사진 파일 |
| `bike_photo_url` | text | 아니오 | 업로드 대신 사용할 자전거 사진 URL |
| `safety_gear_photo_url` | text | 아니오 | 업로드 대신 사용할 안전 장비 사진 URL |
| `verification_status` | text | 아니오 | `pending`\|`verified`\|`rejected` (기본 `verified`) |
| `points_awarded` | integer | 아니오 | 검증 완료 시 지급할 경험치 (기본 30) |
| `admin_notes` | text | 아니오 | 관리자 메모 |
| `started_at` | text | 아니오 | 활동 시작 시각 (ISO 8601) |

> JSON 본문(`application/json`)도 하위 호환으로 지원하지만, 파일 업로드가 필요한 경우에는 반드시 `multipart/form-data`를 사용해야 합니다.

#### cURL 예시 — 파일 업로드

```bash
curl -X POST "https://api.likebike.local/admin/users/42/bike-logs" \
  -H "Authorization: Bearer <ADMIN_JWT>" \
  -H "X-Admin: true" \
  -F "description=한강 야간 라이딩" \
  -F "verification_status=verified" \
  -F "points_awarded=30" \
  -F "bike_photo=@/path/to/bike.jpg" \
  -F "safety_gear_photo=@/path/to/helmet.jpg"
```

#### cURL 예시 — URL만 전달

```bash
curl -X POST "https://api.likebike.local/admin/users/42/bike-logs" \
  -H "Authorization: Bearer <ADMIN_JWT>" \
  -H "X-Admin: true" \
  -H "Content-Type: application/json" \
  -d '{
        "description": "출근 전 인증",
        "bike_photo_url": "https://cdn.example.com/uploads/bike.jpg",
        "safety_gear_photo_url": "https://cdn.example.com/uploads/helmet.jpg",
        "verification_status": "verified",
        "points_awarded": 30,
        "admin_notes": "출근길 인증"
      }'
```

### 응답

- `201 Created` + 생성된 로그 정보를 반환합니다.
- `400 Bad Request` + 필수 항목 누락, 상태/포인트 값이 잘못된 경우
- `404 Not Found` + 대상 사용자가 존재하지 않는 경우

## 경험치 및 보상 처리

- 상태가 `verified`이고 경험치가 0보다 크면 즉시 사용자 경험치를 누적하고 `rewards` 테이블에 `bike_usage` 유형으로 기록합니다.
- `pending` 또는 `rejected` 상태로 생성하면 경험치가 지급되지 않으며, 이후 `/admin/bike-logs/{log_id}/verify`로 상태를 변경할 수
  있습니다.

## 참고

- 사용자당 하루 한 번의 자가 인증 제한은 여전히 `/users/bike-logs` 엔드포인트에 적용됩니다.
- 주간 초기화 시점은 `app.utils.timezone.get_kst_week_start_for_sunday_reset` 함수를 활용해 일요일 00:00 KST 기준으로 계산합니다.
