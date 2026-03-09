"""Tests for weaver daily records generation (Stage 3)."""

from datetime import date, time
from decimal import Decimal

import pytest

from app.ssot import (
    EffectivePeriod,
    TimeRange,
    DayShifts,
    Duration,
    SalaryType,
    NetOrGross,
)
from app.modules.weaver.daily_records import (
    generate_daily_records,
    day_of_week,
    is_rest_day,
    is_work_day,
    get_shifts_for_day,
)


def make_ep(
    id: str,
    start: date,
    end: date,
    work_days: list[int] = None,
    default_shifts: list[TimeRange] = None,
    default_breaks: list[TimeRange] = None,
    per_day: dict = None,
    daily_overrides: dict = None,
) -> EffectivePeriod:
    """Helper to create effective period."""
    return EffectivePeriod(
        id=id,
        start=start,
        end=end,
        duration=Duration(),
        employment_period_id="EMP1",
        work_pattern_id="WP1",
        salary_tier_id="ST1",
        pattern_work_days=work_days or [0, 1, 2, 3, 4],  # Sun-Thu
        pattern_default_shifts=default_shifts or [TimeRange(time(7, 0), time(16, 0))],
        pattern_default_breaks=default_breaks or [TimeRange(time(12, 0), time(12, 30))],
        pattern_per_day=per_day,
        pattern_daily_overrides=daily_overrides,
        salary_amount=Decimal("40"),
        salary_type=SalaryType.HOURLY,
        salary_net_or_gross=NetOrGross.GROSS,
    )


# =============================================================================
# day_of_week tests
# =============================================================================

def test_day_of_week_sunday():
    """Test Sunday is day 0."""
    # 2024-01-07 is a Sunday
    assert day_of_week(date(2024, 1, 7)) == 0


def test_day_of_week_saturday():
    """Test Saturday is day 6."""
    # 2024-01-06 is a Saturday
    assert day_of_week(date(2024, 1, 6)) == 6


def test_day_of_week_wednesday():
    """Test Wednesday is day 3."""
    # 2024-01-03 is a Wednesday
    assert day_of_week(date(2024, 1, 3)) == 3


# =============================================================================
# is_rest_day tests
# =============================================================================

def test_is_rest_day_saturday():
    """Test Saturday is rest day when rest_day=saturday."""
    assert is_rest_day(6, "saturday") is True
    assert is_rest_day(0, "saturday") is False


def test_is_rest_day_friday():
    """Test Friday is rest day when rest_day=friday."""
    assert is_rest_day(5, "friday") is True
    assert is_rest_day(6, "friday") is False


def test_is_rest_day_sunday():
    """Test Sunday is rest day when rest_day=sunday."""
    assert is_rest_day(0, "sunday") is True
    assert is_rest_day(6, "sunday") is False


# =============================================================================
# is_work_day tests
# =============================================================================

def test_is_work_day_in_pattern():
    """Test work day when in pattern (simple weekly, no daily_overrides)."""
    # Sunday (0) is in work_days [0,1,2,3,4]
    assert is_work_day(date(2024, 1, 7), 0, [0, 1, 2, 3, 4], None) is True


def test_is_work_day_not_in_pattern():
    """Test non-work day when not in pattern (simple weekly, no daily_overrides)."""
    # Friday (5) is not in work_days [0,1,2,3,4]
    assert is_work_day(date(2024, 1, 12), 5, [0, 1, 2, 3, 4], None) is False


def test_is_work_day_rest_does_not_override_pattern():
    """Test rest day does NOT override pattern - both flags can be True."""
    # Saturday (6) in pattern with rest=True still means work day
    # The OT pipeline applies rest-day rates (150%/200%)
    assert is_work_day(date(2024, 1, 6), 6, [0, 1, 2, 3, 4, 5, 6], None) is True


def test_is_work_day_with_daily_overrides():
    """Test work day determined by daily_overrides when present (cyclic patterns)."""
    # When daily_overrides is present, it's authoritative for work days
    daily_overrides = {
        date(2024, 1, 7): DayShifts(shifts=[], breaks=[]),  # Sunday
        date(2024, 1, 8): DayShifts(shifts=[], breaks=[]),  # Monday
    }
    # Jan 7 is in daily_overrides → work day
    assert is_work_day(date(2024, 1, 7), 0, [0, 1, 2, 3, 4], daily_overrides) is True
    # Jan 8 is in daily_overrides → work day
    assert is_work_day(date(2024, 1, 8), 1, [0, 1, 2, 3, 4], daily_overrides) is True
    # Jan 9 is NOT in daily_overrides → NOT a work day (even though dow=2 is in work_days)
    assert is_work_day(date(2024, 1, 9), 2, [0, 1, 2, 3, 4], daily_overrides) is False


# =============================================================================
# generate_daily_records tests
# =============================================================================

def test_generate_records_for_week():
    """Test generating records for a full week."""
    # 2024-01-07 (Sun) to 2024-01-13 (Sat)
    ep = make_ep("EP1", date(2024, 1, 7), date(2024, 1, 13))

    records = generate_daily_records([ep], "saturday")

    assert len(records) == 7

    # Sunday (Jan 7) - work day
    assert records[0].date == date(2024, 1, 7)
    assert records[0].day_of_week == 0
    assert records[0].is_work_day is True
    assert records[0].is_rest_day is False

    # Friday (Jan 12) - not work day (not in pattern)
    assert records[5].date == date(2024, 1, 12)
    assert records[5].day_of_week == 5
    assert records[5].is_work_day is False
    assert records[5].is_rest_day is False

    # Saturday (Jan 13) - rest day
    assert records[6].date == date(2024, 1, 13)
    assert records[6].day_of_week == 6
    assert records[6].is_work_day is False
    assert records[6].is_rest_day is True


def test_records_include_shift_templates():
    """Test work days include shift templates."""
    ep = make_ep("EP1", date(2024, 1, 7), date(2024, 1, 7))  # Just Sunday

    records = generate_daily_records([ep], "saturday")

    assert len(records) == 1
    assert records[0].is_work_day is True
    assert len(records[0].shift_templates) == 1
    assert records[0].shift_templates[0].start_time == time(7, 0)
    assert records[0].shift_templates[0].end_time == time(16, 0)


def test_records_non_work_days_no_shifts():
    """Test non-work days have empty shift templates."""
    ep = make_ep("EP1", date(2024, 1, 12), date(2024, 1, 13))  # Fri-Sat

    records = generate_daily_records([ep], "saturday")

    assert len(records) == 2
    # Friday - not work day
    assert records[0].is_work_day is False
    assert records[0].shift_templates == []
    # Saturday - rest day
    assert records[1].is_work_day is False
    assert records[1].shift_templates == []


def test_records_single_day_employment():
    """Test single day employment period (edge case from skill)."""
    ep = make_ep("EP1", date(2024, 3, 15), date(2024, 3, 15))

    records = generate_daily_records([ep], "saturday")

    assert len(records) == 1
    assert records[0].date == date(2024, 3, 15)


def test_per_day_shifts():
    """Test per-day shift overrides (edge case from skill)."""
    # Pattern with different shifts for Thursday (day 4)
    per_day = {
        4: DayShifts(
            shifts=[TimeRange(time(7, 0), time(13, 0))],  # Shorter Thursday
            breaks=[]
        )
    }

    ep = make_ep(
        "EP1",
        date(2024, 1, 7),
        date(2024, 1, 11),  # Sun-Thu
        per_day=per_day,
    )

    records = generate_daily_records([ep], "saturday")

    # Thursday should have shorter shift
    thursday_record = [r for r in records if r.day_of_week == 4][0]
    assert len(thursday_record.shift_templates) == 1
    assert thursday_record.shift_templates[0].end_time == time(13, 0)

    # Other days should have regular shift
    sunday_record = [r for r in records if r.day_of_week == 0][0]
    assert sunday_record.shift_templates[0].end_time == time(16, 0)


def test_daily_override_shifts():
    """Test daily override shifts are used for cyclic patterns.

    When daily_overrides is present, it's authoritative for:
    1. Which days are work days (only dates in daily_overrides)
    2. What shifts those days have
    """
    # Complete daily_overrides for all work days (like cyclic pattern output)
    daily_overrides = {
        date(2024, 1, 7): DayShifts(
            shifts=[TimeRange(time(7, 0), time(16, 0))],  # Default-like
            breaks=[]
        ),
        date(2024, 1, 8): DayShifts(
            shifts=[TimeRange(time(6, 0), time(14, 0))],  # Different shift
            breaks=[]
        ),
        date(2024, 1, 9): DayShifts(
            shifts=[TimeRange(time(8, 0), time(17, 0))],  # Another different shift
            breaks=[]
        ),
    }

    ep = make_ep(
        "EP1",
        date(2024, 1, 7),
        date(2024, 1, 9),
        daily_overrides=daily_overrides,
    )

    records = generate_daily_records([ep], "saturday")

    # All 3 days are work days (in daily_overrides)
    work_records = [r for r in records if r.is_work_day]
    assert len(work_records) == 3

    # Jan 7 (Sunday) - 07:00-16:00
    jan7_record = [r for r in records if r.date == date(2024, 1, 7)][0]
    assert jan7_record.is_work_day is True
    assert jan7_record.shift_templates[0].start_time == time(7, 0)
    assert jan7_record.shift_templates[0].end_time == time(16, 0)

    # Jan 8 (Monday) - 06:00-14:00
    jan8_record = [r for r in records if r.date == date(2024, 1, 8)][0]
    assert jan8_record.is_work_day is True
    assert jan8_record.shift_templates[0].start_time == time(6, 0)
    assert jan8_record.shift_templates[0].end_time == time(14, 0)

    # Jan 9 (Tuesday) - 08:00-17:00
    jan9_record = [r for r in records if r.date == date(2024, 1, 9)][0]
    assert jan9_record.is_work_day is True
    assert jan9_record.shift_templates[0].start_time == time(8, 0)
    assert jan9_record.shift_templates[0].end_time == time(17, 0)


def test_day_segments_null_initially():
    """Test day_segments is None (filled by OT stage 3.5)."""
    ep = make_ep("EP1", date(2024, 1, 7), date(2024, 1, 7))

    records = generate_daily_records([ep], "saturday")

    assert records[0].day_segments is None


def test_pattern_includes_rest_day():
    """Test pattern including rest day - both flags True, shifts loaded."""
    # Pattern includes Saturday (6) and rest_day is Saturday
    # Worker works on their rest day - entitled to 150%/200% rates
    ep = make_ep(
        "EP1",
        date(2024, 1, 6),
        date(2024, 1, 6),  # Just Saturday
        work_days=[0, 1, 2, 3, 4, 5, 6],  # All days
    )

    records = generate_daily_records([ep], "saturday")

    # Both is_work_day AND is_rest_day are True
    # Shift templates are loaded (OT pipeline applies rest-day rates)
    assert records[0].is_work_day is True
    assert records[0].is_rest_day is True
    assert len(records[0].shift_templates) == 1  # Shifts loaded, not empty


def test_two_shifts_per_day():
    """Test pattern with two shifts per day (edge case from skill)."""
    ep = make_ep(
        "EP1",
        date(2024, 1, 7),
        date(2024, 1, 7),
        default_shifts=[
            TimeRange(time(6, 0), time(14, 0)),
            TimeRange(time(16, 0), time(22, 0)),
        ],
    )

    records = generate_daily_records([ep], "saturday")

    assert len(records[0].shift_templates) == 2


def test_rest_day_in_pattern_with_per_day_shifts():
    """Test rest day work with per_day shifts - full scenario."""
    # Pattern: work_days=[0,1,2,3,4,5,6], rest_day=saturday
    # Saturday has specific per_day shifts
    per_day = {
        6: DayShifts(
            shifts=[TimeRange(time(6, 30), time(18, 0))],
            breaks=[TimeRange(time(12, 0), time(12, 30))]
        )
    }

    ep = make_ep(
        "EP1",
        date(2024, 1, 6),
        date(2024, 1, 6),  # Just Saturday
        work_days=[0, 1, 2, 3, 4, 5, 6],  # All days including Saturday
        per_day=per_day,
    )

    records = generate_daily_records([ep], "saturday")

    # Saturday with rest_day=saturday but pattern includes it
    assert records[0].is_work_day is True
    assert records[0].is_rest_day is True
    # Shift templates from per_day, not empty
    assert len(records[0].shift_templates) == 1
    assert records[0].shift_templates[0].start_time == time(6, 30)
    assert records[0].shift_templates[0].end_time == time(18, 0)
    # Break templates loaded
    assert len(records[0].break_templates) == 1
