"""Integration tests for weaver orchestrator."""

from datetime import date, time
from decimal import Decimal

import pytest

from app.ssot import (
    EmploymentPeriod,
    WorkPattern,
    SalaryTier,
    SalaryType,
    NetOrGross,
    TimeRange,
    DayShifts,
)
from app.modules.weaver import run_weaver


def make_ep(id: str, start: date, end: date) -> EmploymentPeriod:
    """Helper to create employment period."""
    return EmploymentPeriod(id=id, start=start, end=end)


def make_wp(
    id: str,
    start: date,
    end: date,
    work_days: list[int] = None,
    shifts: list[TimeRange] = None,
    breaks: list[TimeRange] = None,
    per_day: dict = None,
) -> WorkPattern:
    """Helper to create work pattern."""
    return WorkPattern(
        id=id,
        start=start,
        end=end,
        work_days=work_days or [0, 1, 2, 3, 4],
        default_shifts=shifts or [TimeRange(time(7, 0), time(16, 0))],
        default_breaks=breaks or [TimeRange(time(12, 0), time(12, 30))],
        per_day=per_day,
    )


def make_st(id: str, start: date, end: date, amount: Decimal = Decimal("40")) -> SalaryTier:
    """Helper to create salary tier."""
    return SalaryTier(
        id=id,
        start=start,
        end=end,
        amount=amount,
        type=SalaryType.HOURLY,
        net_or_gross=NetOrGross.GROSS,
    )


# =============================================================================
# Normal path tests
# =============================================================================

def test_weaver_simple_case():
    """Test simple case with single items on all axes."""
    eps = [make_ep("EP1", date(2024, 1, 1), date(2024, 1, 7))]  # One week
    wps = [make_wp("WP1", date(2024, 1, 1), date(2024, 1, 7))]
    sts = [make_st("ST1", date(2024, 1, 1), date(2024, 1, 7))]

    result = run_weaver(eps, wps, sts, "saturday")

    assert result.success is True
    assert len(result.errors) == 0
    assert len(result.effective_periods) == 1
    assert len(result.daily_records) == 7
    assert len(result.employment_gaps) == 0


def test_weaver_full_example():
    """Test full example from skill documentation."""
    eps = [
        make_ep("EMP_A", date(2023, 1, 1), date(2023, 12, 31)),
        make_ep("EMP_B", date(2024, 3, 1), date(2024, 12, 31)),
    ]
    wps = [
        make_wp("WP1", date(2023, 1, 1), date(2024, 6, 30)),
        make_wp("WP2", date(2024, 7, 1), date(2024, 12, 31)),
    ]
    sts = [
        make_st("ST1", date(2023, 1, 1), date(2023, 8, 31), Decimal("40")),
        make_st("ST2", date(2023, 9, 1), date(2024, 12, 31), Decimal("45")),
    ]

    result = run_weaver(eps, wps, sts, "saturday")

    assert result.success is True

    # 4 effective periods
    assert len(result.effective_periods) == 4

    # Check effective periods
    ep1 = result.effective_periods[0]
    assert ep1.start == date(2023, 1, 1)
    assert ep1.end == date(2023, 8, 31)
    assert ep1.employment_period_id == "EMP_A"
    assert ep1.salary_tier_id == "ST1"

    # 1 employment gap (Jan 1 - Feb 29, 2024)
    assert len(result.employment_gaps) == 1
    gap = result.employment_gaps[0]
    assert gap.start == date(2024, 1, 1)
    assert gap.end == date(2024, 2, 29)

    # Total employment
    assert result.total_employment.first_day == date(2023, 1, 1)
    assert result.total_employment.last_day == date(2024, 12, 31)
    assert result.total_employment.periods_count == 2
    assert result.total_employment.gaps_count == 1


# =============================================================================
# Validation error tests (Anti-patterns from skill)
# =============================================================================

def test_weaver_fails_on_invalid_range():
    """Test weaver fails on invalid date range."""
    eps = [make_ep("EP1", date(2024, 12, 31), date(2024, 1, 1))]  # Start > End
    wps = [make_wp("WP1", date(2024, 1, 1), date(2024, 12, 31))]
    sts = [make_st("ST1", date(2024, 1, 1), date(2024, 12, 31))]

    result = run_weaver(eps, wps, sts)

    assert result.success is False
    assert len(result.errors) > 0
    assert any(e.type == "invalid_range" for e in result.errors)


def test_weaver_fails_on_uncovered_work_pattern():
    """Test weaver fails when work pattern doesn't cover employment period."""
    eps = [make_ep("EP1", date(2024, 1, 1), date(2024, 12, 31))]
    wps = [make_wp("WP1", date(2024, 3, 1), date(2024, 12, 31))]  # Missing Jan-Feb
    sts = [make_st("ST1", date(2024, 1, 1), date(2024, 12, 31))]

    result = run_weaver(eps, wps, sts)

    assert result.success is False
    assert any(
        e.type == "uncovered_range" and e.axis == "work_patterns"
        for e in result.errors
    )


def test_weaver_fails_on_uncovered_salary_tier():
    """Test weaver fails when salary tier doesn't cover employment period."""
    eps = [make_ep("EP1", date(2024, 1, 1), date(2024, 12, 31))]
    wps = [make_wp("WP1", date(2024, 1, 1), date(2024, 12, 31))]
    sts = [make_st("ST1", date(2024, 1, 1), date(2024, 9, 30))]  # Missing Oct-Dec

    result = run_weaver(eps, wps, sts)

    assert result.success is False
    assert any(
        e.type == "uncovered_range" and e.axis == "salary_tiers"
        for e in result.errors
    )


def test_weaver_fails_on_axis_overlap():
    """Test weaver fails on overlapping periods within axis."""
    eps = [
        make_ep("EP1", date(2024, 1, 1), date(2024, 6, 30)),
        make_ep("EP2", date(2024, 6, 15), date(2024, 12, 31)),  # Overlaps with EP1
    ]
    wps = [make_wp("WP1", date(2024, 1, 1), date(2024, 12, 31))]
    sts = [make_st("ST1", date(2024, 1, 1), date(2024, 12, 31))]

    result = run_weaver(eps, wps, sts)

    assert result.success is False
    assert any(e.type == "overlap_within_axis" for e in result.errors)


# =============================================================================
# Edge cases from skill
# =============================================================================

def test_single_day_employment():
    """Test single day employment period (edge case #5 from skill)."""
    eps = [make_ep("EP1", date(2024, 3, 15), date(2024, 3, 15))]
    wps = [make_wp("WP1", date(2024, 3, 15), date(2024, 3, 15))]
    sts = [make_st("ST1", date(2024, 3, 15), date(2024, 3, 15))]

    result = run_weaver(eps, wps, sts)

    assert result.success is True
    assert len(result.effective_periods) == 1
    assert result.effective_periods[0].duration.days == 1
    assert len(result.daily_records) == 1


def test_salary_change_mid_month():
    """Test salary change mid-month (edge case #1 from skill)."""
    eps = [make_ep("EP1", date(2024, 6, 1), date(2024, 6, 30))]
    wps = [make_wp("WP1", date(2024, 6, 1), date(2024, 6, 30))]
    sts = [
        make_st("ST1", date(2024, 6, 1), date(2024, 6, 15), Decimal("40")),
        make_st("ST2", date(2024, 6, 16), date(2024, 6, 30), Decimal("45")),
    ]

    result = run_weaver(eps, wps, sts)

    assert result.success is True
    assert len(result.effective_periods) == 2
    assert result.effective_periods[0].end == date(2024, 6, 15)
    assert result.effective_periods[1].start == date(2024, 6, 16)


def test_pattern_change_mid_week():
    """Test pattern change mid-week (edge case #2 from skill)."""
    # Tuesday June 18, Wednesday June 19
    eps = [make_ep("EP1", date(2024, 6, 16), date(2024, 6, 22))]  # Sun-Sat
    wps = [
        make_wp("WP1", date(2024, 6, 16), date(2024, 6, 18)),  # Sun-Tue
        make_wp("WP2", date(2024, 6, 19), date(2024, 6, 22)),  # Wed-Sat
    ]
    sts = [make_st("ST1", date(2024, 6, 16), date(2024, 6, 22))]

    result = run_weaver(eps, wps, sts)

    assert result.success is True
    assert len(result.effective_periods) == 2


def test_consecutive_eps_no_gap():
    """Test consecutive employment periods with no gap (edge case #3 from skill)."""
    eps = [
        make_ep("EMP_A", date(2023, 1, 1), date(2023, 6, 30)),
        make_ep("EMP_B", date(2023, 7, 1), date(2023, 12, 31)),
    ]
    wps = [make_wp("WP1", date(2023, 1, 1), date(2023, 12, 31))]
    sts = [make_st("ST1", date(2023, 1, 1), date(2023, 12, 31))]

    result = run_weaver(eps, wps, sts)

    assert result.success is True
    # Even though WP and ST are same, different EP = separate effective periods
    assert len(result.effective_periods) == 2
    assert len(result.employment_gaps) == 0


def test_pattern_includes_rest_day():
    """Test pattern including rest day (edge case #4 from skill)."""
    # Pattern includes Saturday and rest_day is Saturday
    # Worker works on their rest day - entitled to 150%/200% rates
    eps = [make_ep("EP1", date(2024, 1, 6), date(2024, 1, 6))]  # Just Saturday
    wps = [make_wp("WP1", date(2024, 1, 6), date(2024, 1, 6), work_days=[0, 1, 2, 3, 4, 5, 6])]
    sts = [make_st("ST1", date(2024, 1, 6), date(2024, 1, 6))]

    result = run_weaver(eps, wps, sts, "saturday")

    assert result.success is True
    # Should have warning about pattern including rest day
    assert len(result.warnings) == 1
    assert result.warnings[0].type == "pattern_includes_rest_day"

    # Daily record should show Saturday as BOTH work day AND rest day
    # OT pipeline will apply rest-day rates (150%/200%)
    assert len(result.daily_records) == 1
    assert result.daily_records[0].is_work_day is True  # Pattern includes it
    assert result.daily_records[0].is_rest_day is True  # It's the rest day


def test_per_day_shifts():
    """Test pattern with different shifts per day (edge case #6 from skill)."""
    per_day = {
        4: DayShifts(shifts=[TimeRange(time(7, 0), time(13, 0))])  # Thursday short day
    }
    eps = [make_ep("EP1", date(2024, 1, 7), date(2024, 1, 11))]  # Sun-Thu
    wps = [make_wp("WP1", date(2024, 1, 7), date(2024, 1, 11), per_day=per_day)]
    sts = [make_st("ST1", date(2024, 1, 7), date(2024, 1, 11))]

    result = run_weaver(eps, wps, sts)

    assert result.success is True
    # Find Thursday's record
    thu_records = [r for r in result.daily_records if r.day_of_week == 4]
    assert len(thu_records) == 1
    assert thu_records[0].shift_templates[0].end_time == time(13, 0)


def test_two_shifts_per_day():
    """Test pattern with two shifts per day (edge case #7 from skill)."""
    eps = [make_ep("EP1", date(2024, 1, 7), date(2024, 1, 7))]
    wps = [make_wp(
        "WP1",
        date(2024, 1, 7),
        date(2024, 1, 7),
        shifts=[
            TimeRange(time(6, 0), time(14, 0)),
            TimeRange(time(16, 0), time(22, 0)),
        ],
    )]
    sts = [make_st("ST1", date(2024, 1, 7), date(2024, 1, 7))]

    result = run_weaver(eps, wps, sts)

    assert result.success is True
    assert len(result.daily_records[0].shift_templates) == 2


def test_non_work_days_have_records():
    """Test non-work days have records (edge case #8 from skill)."""
    eps = [make_ep("EP1", date(2024, 1, 7), date(2024, 1, 13))]  # Sun-Sat
    wps = [make_wp("WP1", date(2024, 1, 7), date(2024, 1, 13))]  # 5-day work week
    sts = [make_st("ST1", date(2024, 1, 7), date(2024, 1, 13))]

    result = run_weaver(eps, wps, sts)

    assert result.success is True
    assert len(result.daily_records) == 7  # All days, not just work days

    # Friday (not in pattern)
    fri_records = [r for r in result.daily_records if r.day_of_week == 5]
    assert len(fri_records) == 1
    assert fri_records[0].is_work_day is False
    assert fri_records[0].is_rest_day is False
    assert fri_records[0].shift_templates == []

    # Saturday (rest day)
    sat_records = [r for r in result.daily_records if r.day_of_week == 6]
    assert len(sat_records) == 1
    assert sat_records[0].is_work_day is False
    assert sat_records[0].is_rest_day is True


def test_day_segments_null():
    """Test day_segments is null (filled by OT stage 3.5)."""
    eps = [make_ep("EP1", date(2024, 1, 7), date(2024, 1, 7))]
    wps = [make_wp("WP1", date(2024, 1, 7), date(2024, 1, 7))]
    sts = [make_st("ST1", date(2024, 1, 7), date(2024, 1, 7))]

    result = run_weaver(eps, wps, sts)

    assert result.success is True
    assert result.daily_records[0].day_segments is None


def test_duration_display_empty():
    """Test duration.display is empty (filled by Phase 4)."""
    eps = [make_ep("EP1", date(2024, 1, 1), date(2024, 1, 31))]
    wps = [make_wp("WP1", date(2024, 1, 1), date(2024, 1, 31))]
    sts = [make_st("ST1", date(2024, 1, 1), date(2024, 1, 31))]

    result = run_weaver(eps, wps, sts)

    assert result.success is True
    assert result.effective_periods[0].duration.display == ""
    assert result.total_employment.total_duration.display == ""
