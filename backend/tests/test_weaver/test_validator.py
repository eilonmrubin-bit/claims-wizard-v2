"""Tests for weaver validator (Stage 1)."""

from datetime import date
from decimal import Decimal

import pytest

from app.ssot import (
    EmploymentPeriod,
    WorkPattern,
    SalaryTier,
    SalaryType,
    NetOrGross,
    TimeRange,
)
from app.modules.weaver.validator import (
    validate,
    validate_axis_ranges,
    validate_axis_no_overlaps,
    validate_coverage,
    find_uncovered_ranges,
)
from datetime import time


def make_ep(id: str, start: date, end: date) -> EmploymentPeriod:
    """Helper to create employment period."""
    return EmploymentPeriod(id=id, start=start, end=end)


def make_wp(id: str, start: date, end: date, work_days: list[int] = None) -> WorkPattern:
    """Helper to create work pattern."""
    return WorkPattern(
        id=id,
        start=start,
        end=end,
        work_days=work_days or [0, 1, 2, 3, 4],  # Sun-Thu
        default_shifts=[TimeRange(start_time=time(7, 0), end_time=time(16, 0))],
    )


def make_st(id: str, start: date, end: date) -> SalaryTier:
    """Helper to create salary tier."""
    return SalaryTier(
        id=id,
        start=start,
        end=end,
        amount=Decimal("40"),
        type=SalaryType.HOURLY,
        net_or_gross=NetOrGross.GROSS,
    )


# =============================================================================
# validate_axis_ranges tests
# =============================================================================

def test_valid_range():
    """Test valid date range."""
    items = [make_ep("EP1", date(2024, 1, 1), date(2024, 12, 31))]
    errors = validate_axis_ranges(items, "employment_periods", "תקופות העסקה")
    assert len(errors) == 0


def test_single_day_range():
    """Test single day employment period."""
    items = [make_ep("EP1", date(2024, 3, 15), date(2024, 3, 15))]
    errors = validate_axis_ranges(items, "employment_periods", "תקופות העסקה")
    assert len(errors) == 0


def test_invalid_range_start_after_end():
    """Test start date after end date."""
    items = [make_ep("EP1", date(2024, 12, 31), date(2024, 1, 1))]
    errors = validate_axis_ranges(items, "employment_periods", "תקופות העסקה")
    assert len(errors) == 1
    assert errors[0].type == "invalid_range"


# =============================================================================
# validate_axis_no_overlaps tests
# =============================================================================

def test_no_overlaps():
    """Test non-overlapping periods."""
    items = [
        make_ep("EP1", date(2023, 1, 1), date(2023, 6, 30)),
        make_ep("EP2", date(2023, 7, 1), date(2023, 12, 31)),
    ]
    errors = validate_axis_no_overlaps(items, "employment_periods", "תקופות העסקה")
    assert len(errors) == 0


def test_consecutive_no_overlap():
    """Test consecutive periods (adjacent days) do not overlap."""
    items = [
        make_ep("EP1", date(2023, 1, 1), date(2023, 6, 30)),
        make_ep("EP2", date(2023, 7, 1), date(2023, 12, 31)),
    ]
    errors = validate_axis_no_overlaps(items, "employment_periods", "תקופות העסקה")
    assert len(errors) == 0


def test_overlap_detected():
    """Test overlapping periods are detected."""
    items = [
        make_ep("EP1", date(2023, 1, 1), date(2023, 6, 30)),
        make_ep("EP2", date(2023, 6, 15), date(2023, 12, 31)),  # Overlaps with EP1
    ]
    errors = validate_axis_no_overlaps(items, "employment_periods", "תקופות העסקה")
    assert len(errors) == 1
    assert errors[0].type == "overlap_within_axis"


def test_same_day_overlap():
    """Test same-day boundary is considered overlap."""
    items = [
        make_ep("EP1", date(2023, 1, 1), date(2023, 6, 30)),
        make_ep("EP2", date(2023, 6, 30), date(2023, 12, 31)),  # Same day boundary
    ]
    errors = validate_axis_no_overlaps(items, "employment_periods", "תקופות העסקה")
    assert len(errors) == 1


# =============================================================================
# find_uncovered_ranges tests
# =============================================================================

def test_full_coverage():
    """Test full coverage returns no gaps."""
    items = [
        make_wp("WP1", date(2023, 1, 1), date(2023, 12, 31)),
    ]
    gaps = find_uncovered_ranges(date(2023, 1, 1), date(2023, 12, 31), items)
    assert len(gaps) == 0


def test_gap_at_start():
    """Test gap at the start of range."""
    items = [
        make_wp("WP1", date(2023, 3, 1), date(2023, 12, 31)),
    ]
    gaps = find_uncovered_ranges(date(2023, 1, 1), date(2023, 12, 31), items)
    assert len(gaps) == 1
    assert gaps[0] == (date(2023, 1, 1), date(2023, 2, 28))


def test_gap_at_end():
    """Test gap at the end of range."""
    items = [
        make_wp("WP1", date(2023, 1, 1), date(2023, 9, 30)),
    ]
    gaps = find_uncovered_ranges(date(2023, 1, 1), date(2023, 12, 31), items)
    assert len(gaps) == 1
    assert gaps[0] == (date(2023, 10, 1), date(2023, 12, 31))


def test_gap_in_middle():
    """Test gap in the middle of range."""
    items = [
        make_wp("WP1", date(2023, 1, 1), date(2023, 3, 31)),
        make_wp("WP2", date(2023, 6, 1), date(2023, 12, 31)),
    ]
    gaps = find_uncovered_ranges(date(2023, 1, 1), date(2023, 12, 31), items)
    assert len(gaps) == 1
    assert gaps[0] == (date(2023, 4, 1), date(2023, 5, 31))


def test_no_coverage():
    """Test no coverage at all."""
    items = []
    gaps = find_uncovered_ranges(date(2023, 1, 1), date(2023, 12, 31), items)
    assert len(gaps) == 1
    assert gaps[0] == (date(2023, 1, 1), date(2023, 12, 31))


# =============================================================================
# validate_coverage tests
# =============================================================================

def test_full_cross_axis_coverage():
    """Test full coverage across all axes."""
    eps = [make_ep("EP1", date(2023, 1, 1), date(2023, 12, 31))]
    wps = [make_wp("WP1", date(2023, 1, 1), date(2023, 12, 31))]
    sts = [make_st("ST1", date(2023, 1, 1), date(2023, 12, 31))]

    errors = validate_coverage(eps, wps, sts)
    assert len(errors) == 0


def test_missing_work_pattern_coverage():
    """Test missing work pattern coverage is detected."""
    eps = [make_ep("EP1", date(2023, 1, 1), date(2023, 12, 31))]
    wps = [make_wp("WP1", date(2023, 3, 1), date(2023, 12, 31))]  # Missing Jan-Feb
    sts = [make_st("ST1", date(2023, 1, 1), date(2023, 12, 31))]

    errors = validate_coverage(eps, wps, sts)
    assert len(errors) == 1
    assert errors[0].type == "uncovered_range"
    assert errors[0].axis == "work_patterns"


def test_missing_salary_tier_coverage():
    """Test missing salary tier coverage is detected."""
    eps = [make_ep("EP1", date(2023, 1, 1), date(2023, 12, 31))]
    wps = [make_wp("WP1", date(2023, 1, 1), date(2023, 12, 31))]
    sts = [make_st("ST1", date(2023, 1, 1), date(2023, 9, 30))]  # Missing Oct-Dec

    errors = validate_coverage(eps, wps, sts)
    assert len(errors) == 1
    assert errors[0].type == "uncovered_range"
    assert errors[0].axis == "salary_tiers"


# =============================================================================
# Full validate function tests
# =============================================================================

def test_valid_input():
    """Test valid input passes validation."""
    eps = [make_ep("EP1", date(2023, 1, 1), date(2023, 12, 31))]
    wps = [make_wp("WP1", date(2023, 1, 1), date(2023, 12, 31))]
    sts = [make_st("ST1", date(2023, 1, 1), date(2023, 12, 31))]

    errors, warnings = validate(eps, wps, sts)
    assert len(errors) == 0


def test_pattern_includes_rest_day_warning():
    """Test warning when pattern includes rest day."""
    eps = [make_ep("EP1", date(2023, 1, 1), date(2023, 12, 31))]
    wps = [make_wp("WP1", date(2023, 1, 1), date(2023, 12, 31), work_days=[0, 1, 2, 3, 4, 5, 6])]
    sts = [make_st("ST1", date(2023, 1, 1), date(2023, 12, 31))]

    errors, warnings = validate(eps, wps, sts, rest_day="saturday")
    assert len(errors) == 0
    assert len(warnings) == 1
    assert warnings[0].type == "pattern_includes_rest_day"


def test_multiple_errors():
    """Test multiple errors are collected."""
    eps = [
        make_ep("EP1", date(2023, 6, 30), date(2023, 1, 1)),  # Invalid range
        make_ep("EP2", date(2023, 7, 1), date(2023, 12, 31)),
    ]
    wps = [make_wp("WP1", date(2023, 1, 1), date(2023, 12, 31))]
    sts = [make_st("ST1", date(2023, 1, 1), date(2023, 12, 31))]

    errors, warnings = validate(eps, wps, sts)
    assert len(errors) >= 1
