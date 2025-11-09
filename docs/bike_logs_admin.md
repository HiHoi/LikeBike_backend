# 관리자 자전거 활동 등록 가이드

LikeBike 관리자 패널에서는 이용자 대신 자전거 활동을 수기로 등록할 수 있습니다. 이 문서는 새로 추가된 엔드포인트와
검증 흐름을 정리합니다.

## 엔드포인트 요약

| Method | Path | 설명 |
| ------ | ---- | ---- |
| `POST` | `/admin/users/{user_id}/bike-logs` | 관리자가 특정 사용자의 활동을 직접 등록 |

### 요청 본문

```json
{
  "description": "필수. 활동 설명",
  "bike_photo": "선택. data URL(base64) 자전거 사진",
  "safety_gear_photo": "선택. data URL(base64) 안전 장비 사진",
  "verification_status": "선택. pending/verified/rejected 중 하나 (기본 verified)",
  "points_awarded": "선택. verified 상태일 때 지급할 경험치 (기본 30)",
  "admin_notes": "선택. 관리자 메모",
  "started_at": "선택. 활동 시작 시각 (ISO 8601)"
}
```

### 응답

- `201 Created` + 생성된 로그 정보를 반환합니다. 응답에는 업로드된 이미지의 퍼블릭 URL이 포함됩니다.
- `400 Bad Request` + 필수 항목 누락, 상태/포인트 값이 잘못된 경우
- `404 Not Found` + 대상 사용자가 존재하지 않는 경우

## 경험치 및 보상 처리

- 상태가 `verified`이고 경험치가 0보다 크면 즉시 사용자 경험치를 누적하고 `rewards` 테이블에 `bike_usage` 유형으로 기록합니다.
- `pending` 또는 `rejected` 상태로 생성하면 경험치가 지급되지 않으며, 이후 `/admin/bike-logs/{log_id}/verify`로 상태를 변경할 수
  있습니다.

## 참고

- 사용자당 하루 한 번의 자가 인증 제한은 여전히 `/users/bike-logs` 엔드포인트에 적용됩니다.
- 이미지는 `data:<mime>;base64,<data>` 형식의 data URL로 전달해야 하며, JPG/PNG/GIF/BMP/WebP 형식을 지원합니다.
- 주간 초기화 시점은 `app.utils.timezone.get_kst_week_start_for_sunday_reset` 함수를 활용해 일요일 00:00 KST 기준으로 계산합니다.
