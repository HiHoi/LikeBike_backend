"""Timezone helpers used throughout the LikeBike backend."""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import Optional, Tuple

__all__ = [
    "KST",
    "get_kst_now",
    "get_kst_today",
    "kst_datetime_to_utc",
    "utc_datetime_to_kst",
    "get_kst_date_range_for_today",
    "get_kst_week_start_for_sunday_reset",
]


# 한국 시간대 (UTC+9)
KST = timezone(timedelta(hours=9))


def _ensure_timezone(dt: datetime, tz: timezone) -> datetime:
    """Ensure *dt* carries *tz* information before conversions."""

    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz)
    return dt


def get_kst_now() -> datetime:
    """현재 한국 시간을 반환합니다."""

    return datetime.now(KST)


def get_kst_today():
    """오늘 날짜를 한국 시간대 기준으로 반환합니다."""

    return get_kst_now().date()


def kst_datetime_to_utc(kst_dt: datetime) -> datetime:
    """한국 시간의 datetime을 UTC로 변환합니다."""

    aware_kst = _ensure_timezone(kst_dt, KST)
    return aware_kst.astimezone(timezone.utc)


def utc_datetime_to_kst(utc_dt: datetime) -> datetime:
    """UTC datetime을 한국 시간으로 변환합니다."""

    aware_utc = _ensure_timezone(utc_dt, timezone.utc)
    return aware_utc.astimezone(KST)


def get_kst_date_range_for_today() -> Tuple[datetime, datetime]:
    """오늘 하루의 시작과 끝을 UTC 시간으로 반환합니다."""

    today_kst = get_kst_today()

    start_of_day_kst = datetime.combine(today_kst, time.min, tzinfo=KST)
    start_of_day_utc = start_of_day_kst.astimezone(timezone.utc)

    end_of_day_kst = start_of_day_kst + timedelta(days=1)
    end_of_day_utc = end_of_day_kst.astimezone(timezone.utc)

    return start_of_day_utc, end_of_day_utc


def get_kst_week_start_for_sunday_reset(
    reference: Optional[datetime] = None,
) -> datetime:
    """Return the weekly reset boundary (Sunday 00:00 KST) in UTC.

    Args:
        reference: 기준 시각. 지정하지 않으면 현재 UTC 시간이 사용됩니다.
    """

    if reference is None:
        reference = datetime.now(timezone.utc)

    aware_reference = _ensure_timezone(reference, timezone.utc).astimezone(KST)

    days_since_sunday = (aware_reference.weekday() + 1) % 7
    sunday_date = aware_reference.date() - timedelta(days=days_since_sunday)
    sunday_start_kst = datetime.combine(sunday_date, time.min, tzinfo=KST)

    return sunday_start_kst.astimezone(timezone.utc)
