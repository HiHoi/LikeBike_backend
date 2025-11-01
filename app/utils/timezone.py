from datetime import date, datetime, timezone, timedelta

# 한국 시간대 (UTC+9)
KST = timezone(timedelta(hours=9))


def get_kst_now():
    """현재 한국 시간을 반환합니다."""
    return datetime.now(KST)


def get_kst_today():
    """오늘 날짜를 한국 시간대 기준으로 반환합니다."""
    return get_kst_now().date()


def kst_datetime_to_utc(kst_dt):
    """한국 시간의 datetime을 UTC로 변환합니다."""
    if kst_dt.tzinfo is None:
        # naive datetime인 경우 KST로 가정
        kst_dt = kst_dt.replace(tzinfo=KST)
    return kst_dt.astimezone(timezone.utc)


def utc_datetime_to_kst(utc_dt):
    """UTC datetime을 한국 시간으로 변환합니다."""
    if utc_dt.tzinfo is None:
        # naive datetime인 경우 UTC로 가정
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)
    return utc_dt.astimezone(KST)


def get_kst_date_range_for_today():
    """
    오늘 하루의 시작과 끝을 UTC 시간으로 반환합니다.
    데이터베이스 쿼리에서 사용할 수 있습니다.
    """
    today_kst = get_kst_today()
    
    # 오늘 00:00:00 KST를 UTC로 변환
    start_of_day_kst = datetime.combine(today_kst, datetime.min.time()).replace(tzinfo=KST)
    start_of_day_utc = start_of_day_kst.astimezone(timezone.utc)
    
    # 내일 00:00:00 KST를 UTC로 변환 (하루 끝)
    end_of_day_kst = start_of_day_kst + timedelta(days=1)
    end_of_day_utc = end_of_day_kst.astimezone(timezone.utc)
    
    return start_of_day_utc, end_of_day_utc


def get_kst_week_start_for_sunday_reset(reference: datetime | None = None) -> datetime:
    """
    한국 시간(KST) 기준으로 일요일 00:00에 초기화되는 주간 시작 시각을 UTC로 반환합니다.

    Args:
        reference: 기준이 되는 시각. 지정하지 않으면 현재 UTC 시간을 사용합니다.

    Returns:
        datetime: 기준 시각이 속한 주의 시작(일요일 00:00 KST)을 UTC 시간으로 변환한 값.
    """

    if reference is None:
        reference = datetime.now(timezone.utc)
    elif reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)

    kst_now = reference.astimezone(KST)
    kst_midnight = (
        datetime.combine(kst_now.date(), datetime.min.time())
        .replace(tzinfo=KST)
    )
    days_since_sunday = (kst_midnight.weekday() + 1) % 7
    week_start_kst = kst_midnight - timedelta(days=days_since_sunday)
    return week_start_kst.astimezone(timezone.utc)
