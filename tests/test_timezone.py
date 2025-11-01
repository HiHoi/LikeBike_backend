from datetime import datetime, timezone

from app.utils.timezone import (
    KST,
    get_kst_week_start_for_sunday_reset,
    utc_datetime_to_kst,
)


def test_week_start_returns_sunday_midnight_for_midweek_reference():
    reference = datetime(2024, 7, 10, 12, 0, tzinfo=timezone.utc)

    week_start_utc = get_kst_week_start_for_sunday_reset(reference)
    week_start_kst = utc_datetime_to_kst(week_start_utc)

    assert week_start_kst.tzinfo == KST
    assert week_start_kst.weekday() == 6  # Sunday
    assert week_start_kst.hour == 0
    assert week_start_kst.minute == 0
    assert week_start_kst.second == 0
    assert week_start_kst.date().isoformat() == "2024-07-07"


def test_week_start_handles_sunday_reference_correctly():
    reference = datetime(2024, 7, 7, 3, 0, tzinfo=timezone.utc)

    week_start_utc = get_kst_week_start_for_sunday_reset(reference)
    week_start_kst = utc_datetime_to_kst(week_start_utc)

    assert week_start_kst.tzinfo == KST
    assert week_start_kst.date().isoformat() == "2024-07-07"
    assert week_start_kst.hour == 0
    assert week_start_kst.minute == 0
    assert week_start_kst.second == 0
