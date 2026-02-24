"""Tests for weaver gaps detection and total employment (Stage 4)."""

from datetime import date
from decimal import Decimal

import pytest

from app.ssot import EmploymentPeriod, Duration
from app.modules.weaver.gaps import (
    detect_gaps,
    compute_total_employment,
    sum_durations,
)


def make_ep(id: str, start: date, end: date) -> EmploymentPeriod:
    """Helper to create employment period."""
    return EmploymentPeriod(id=id, start=start, end=end)


# =============================================================================
# detect_gaps tests
# =============================================================================

def test_no_gaps_single_period():
    """Test no gaps with single employment period."""
    eps = [make_ep("EP1", date(2023, 1, 1), date(2023, 12, 31))]
    gaps = detect_gaps(eps)
    assert len(gaps) == 0


def test_no_gaps_consecutive_periods():
    """Test no gaps when periods are consecutive (edge case from skill)."""
    eps = [
        make_ep("EMP_A", date(2023, 1, 1), date(2023, 6, 30)),
        make_ep("EMP_B", date(2023, 7, 1), date(2023, 12, 31)),
    ]
    gaps = detect_gaps(eps)
    assert len(gaps) == 0


def test_gap_detected():
    """Test gap detection between periods."""
    eps = [
        make_ep("EMP_A", date(2023, 1, 1), date(2023, 6, 30)),
        make_ep("EMP_B", date(2023, 9, 1), date(2023, 12, 31)),
    ]
    gaps = detect_gaps(eps)

    assert len(gaps) == 1
    assert gaps[0].start == date(2023, 7, 1)
    assert gaps[0].end == date(2023, 8, 31)
    assert gaps[0].before_period_id == "EMP_A"
    assert gaps[0].after_period_id == "EMP_B"


def test_gap_from_skill_example():
    """Test gap from skill example (2024-01-01 to 2024-02-29)."""
    eps = [
        make_ep("EMP_A", date(2023, 1, 1), date(2023, 12, 31)),
        make_ep("EMP_B", date(2024, 3, 1), date(2024, 12, 31)),
    ]
    gaps = detect_gaps(eps)

    assert len(gaps) == 1
    assert gaps[0].start == date(2024, 1, 1)
    assert gaps[0].end == date(2024, 2, 29)  # 2024 is leap year


def test_multiple_gaps():
    """Test multiple gaps detection."""
    eps = [
        make_ep("EP1", date(2023, 1, 1), date(2023, 3, 31)),
        make_ep("EP2", date(2023, 6, 1), date(2023, 8, 31)),
        make_ep("EP3", date(2023, 11, 1), date(2023, 12, 31)),
    ]
    gaps = detect_gaps(eps)

    assert len(gaps) == 2
    assert gaps[0].start == date(2023, 4, 1)
    assert gaps[0].end == date(2023, 5, 31)
    assert gaps[1].start == date(2023, 9, 1)
    assert gaps[1].end == date(2023, 10, 31)


def test_gap_has_duration():
    """Test gap includes duration calculation."""
    eps = [
        make_ep("EP1", date(2023, 1, 1), date(2023, 1, 31)),
        make_ep("EP2", date(2023, 3, 1), date(2023, 3, 31)),
    ]
    gaps = detect_gaps(eps)

    assert len(gaps) == 1
    # February 2023 has 28 days
    assert gaps[0].duration.days == 28


def test_unsorted_periods_handled():
    """Test that unsorted periods are handled correctly."""
    # Periods in wrong order
    eps = [
        make_ep("EP2", date(2023, 9, 1), date(2023, 12, 31)),
        make_ep("EP1", date(2023, 1, 1), date(2023, 6, 30)),
    ]
    gaps = detect_gaps(eps)

    # Should still find the gap correctly
    assert len(gaps) == 1
    assert gaps[0].start == date(2023, 7, 1)


# =============================================================================
# compute_total_employment tests
# =============================================================================

def test_total_employment_single_period():
    """Test total employment with single period."""
    eps = [make_ep("EP1", date(2023, 1, 1), date(2023, 12, 31))]
    gaps = []

    total = compute_total_employment(eps, gaps)

    assert total.first_day == date(2023, 1, 1)
    assert total.last_day == date(2023, 12, 31)
    assert total.periods_count == 1
    assert total.gaps_count == 0


def test_total_employment_with_gap():
    """Test total employment with gap."""
    eps = [
        make_ep("EMP_A", date(2023, 1, 1), date(2023, 6, 30)),
        make_ep("EMP_B", date(2023, 9, 1), date(2023, 12, 31)),
    ]
    gaps = detect_gaps(eps)

    total = compute_total_employment(eps, gaps)

    assert total.first_day == date(2023, 1, 1)
    assert total.last_day == date(2023, 12, 31)
    assert total.periods_count == 2
    assert total.gaps_count == 1


def test_total_duration_includes_gaps():
    """Test total_duration includes gap time."""
    eps = [
        make_ep("EP1", date(2023, 1, 1), date(2023, 6, 30)),
        make_ep("EP2", date(2023, 9, 1), date(2023, 12, 31)),
    ]
    gaps = detect_gaps(eps)

    total = compute_total_employment(eps, gaps)

    # Total: Jan 1 to Dec 31 = 365 days
    assert total.total_duration.days == 365


def test_worked_duration_excludes_gaps():
    """Test worked_duration excludes gap time."""
    eps = [
        make_ep("EP1", date(2023, 1, 1), date(2023, 1, 31)),  # 31 days
        make_ep("EP2", date(2023, 3, 1), date(2023, 3, 31)),  # 31 days
    ]
    gaps = detect_gaps(eps)

    total = compute_total_employment(eps, gaps)

    # Worked: 31 + 31 = 62 days
    assert total.worked_duration.days == 62


def test_gap_duration_correct():
    """Test gap_duration is calculated correctly."""
    eps = [
        make_ep("EP1", date(2023, 1, 1), date(2023, 1, 31)),
        make_ep("EP2", date(2023, 3, 1), date(2023, 3, 31)),
    ]
    gaps = detect_gaps(eps)

    total = compute_total_employment(eps, gaps)

    # Gap: February 2023 = 28 days
    assert total.gap_duration.days == 28


def test_empty_periods():
    """Test empty periods returns default TotalEmployment."""
    eps = []
    gaps = []

    total = compute_total_employment(eps, gaps)

    assert total.first_day is None
    assert total.last_day is None
    assert total.periods_count == 0


# =============================================================================
# sum_durations tests
# =============================================================================

def test_sum_durations_single():
    """Test sum of single period."""
    eps = [make_ep("EP1", date(2023, 1, 1), date(2023, 1, 31))]
    duration = sum_durations(eps)
    assert duration.days == 31


def test_sum_durations_multiple():
    """Test sum of multiple periods."""
    eps = [
        make_ep("EP1", date(2023, 1, 1), date(2023, 1, 31)),  # 31
        make_ep("EP2", date(2023, 3, 1), date(2023, 3, 31)),  # 31
    ]
    duration = sum_durations(eps)
    assert duration.days == 62


def test_sum_durations_empty():
    """Test sum of empty list."""
    duration = sum_durations([])
    assert duration.days == 0
