"""Tests for weaver sweep line algorithm (Stage 2)."""

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
)
from app.modules.weaver.sweep import (
    sweep,
    collect_boundaries,
    create_atomic_periods,
    merge_consecutive_atoms,
    compute_duration,
    Atom,
)


def make_ep(id: str, start: date, end: date) -> EmploymentPeriod:
    """Helper to create employment period."""
    return EmploymentPeriod(id=id, start=start, end=end)


def make_wp(id: str, start: date, end: date, work_days: list[int] = None) -> WorkPattern:
    """Helper to create work pattern."""
    return WorkPattern(
        id=id,
        start=start,
        end=end,
        work_days=work_days or [0, 1, 2, 3, 4],
        default_shifts=[TimeRange(start_time=time(7, 0), end_time=time(16, 0))],
        default_breaks=[TimeRange(start_time=time(12, 0), end_time=time(12, 30))],
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
# collect_boundaries tests
# =============================================================================

def test_collect_boundaries_simple():
    """Test boundary collection from single items."""
    eps = [make_ep("EP1", date(2023, 1, 1), date(2023, 12, 31))]
    wps = [make_wp("WP1", date(2023, 1, 1), date(2023, 12, 31))]
    sts = [make_st("ST1", date(2023, 1, 1), date(2023, 12, 31))]

    boundaries = collect_boundaries(eps, wps, sts)
    assert date(2023, 1, 1) in boundaries
    assert date(2024, 1, 1) in boundaries  # end + 1


def test_collect_boundaries_multiple():
    """Test boundary collection with multiple axis items."""
    eps = [make_ep("EP1", date(2023, 1, 1), date(2023, 12, 31))]
    wps = [
        make_wp("WP1", date(2023, 1, 1), date(2023, 6, 30)),
        make_wp("WP2", date(2023, 7, 1), date(2023, 12, 31)),
    ]
    sts = [
        make_st("ST1", date(2023, 1, 1), date(2023, 8, 31)),
        make_st("ST2", date(2023, 9, 1), date(2023, 12, 31)),
    ]

    boundaries = collect_boundaries(eps, wps, sts)

    # Should have boundaries at all transitions
    assert date(2023, 1, 1) in boundaries
    assert date(2023, 7, 1) in boundaries
    assert date(2023, 9, 1) in boundaries


# =============================================================================
# compute_duration tests
# =============================================================================

def test_compute_duration_single_day():
    """Test duration of single day."""
    duration = compute_duration(date(2024, 3, 15), date(2024, 3, 15))
    assert duration.days == 1


def test_compute_duration_one_month():
    """Test duration of roughly one month."""
    duration = compute_duration(date(2024, 1, 1), date(2024, 1, 31))
    assert duration.days == 31
    assert duration.months_whole == 1


def test_compute_duration_one_year():
    """Test duration of one year."""
    duration = compute_duration(date(2023, 1, 1), date(2023, 12, 31))
    assert duration.days == 365
    assert duration.years_whole == 1


# =============================================================================
# merge_consecutive_atoms tests
# =============================================================================

def test_merge_consecutive_same_combo():
    """Test merging consecutive atoms with same combination."""
    atoms = [
        Atom(date(2023, 1, 1), date(2023, 3, 31), "EP1", "WP1", "ST1"),
        Atom(date(2023, 4, 1), date(2023, 6, 30), "EP1", "WP1", "ST1"),
    ]
    merged = merge_consecutive_atoms(atoms)
    assert len(merged) == 1
    assert merged[0].start == date(2023, 1, 1)
    assert merged[0].end == date(2023, 6, 30)


def test_no_merge_different_combo():
    """Test no merging when combination differs."""
    atoms = [
        Atom(date(2023, 1, 1), date(2023, 3, 31), "EP1", "WP1", "ST1"),
        Atom(date(2023, 4, 1), date(2023, 6, 30), "EP1", "WP1", "ST2"),  # Different ST
    ]
    merged = merge_consecutive_atoms(atoms)
    assert len(merged) == 2


def test_no_merge_different_ep():
    """Test no merging when employment period differs."""
    atoms = [
        Atom(date(2023, 1, 1), date(2023, 6, 30), "EP1", "WP1", "ST1"),
        Atom(date(2023, 7, 1), date(2023, 12, 31), "EP2", "WP1", "ST1"),  # Different EP
    ]
    merged = merge_consecutive_atoms(atoms)
    assert len(merged) == 2


def test_no_merge_non_consecutive():
    """Test no merging when atoms are not consecutive."""
    atoms = [
        Atom(date(2023, 1, 1), date(2023, 3, 31), "EP1", "WP1", "ST1"),
        Atom(date(2023, 5, 1), date(2023, 6, 30), "EP1", "WP1", "ST1"),  # Gap in April
    ]
    merged = merge_consecutive_atoms(atoms)
    assert len(merged) == 2


# =============================================================================
# Full sweep tests
# =============================================================================

def test_sweep_simple():
    """Test simple sweep with single items on all axes."""
    eps = [make_ep("EP1", date(2023, 1, 1), date(2023, 12, 31))]
    wps = [make_wp("WP1", date(2023, 1, 1), date(2023, 12, 31))]
    sts = [make_st("ST1", date(2023, 1, 1), date(2023, 12, 31))]

    effective_periods = sweep(eps, wps, sts)

    assert len(effective_periods) == 1
    assert effective_periods[0].start == date(2023, 1, 1)
    assert effective_periods[0].end == date(2023, 12, 31)
    assert effective_periods[0].employment_period_id == "EP1"
    assert effective_periods[0].work_pattern_id == "WP1"
    assert effective_periods[0].salary_tier_id == "ST1"


def test_sweep_salary_change_mid_month():
    """Test sweep with salary change mid-month (edge case from skill)."""
    eps = [make_ep("EMP_A", date(2023, 1, 1), date(2023, 12, 31))]
    wps = [make_wp("WP1", date(2023, 1, 1), date(2023, 12, 31))]
    sts = [
        make_st("ST1", date(2023, 1, 1), date(2023, 6, 15), Decimal("40")),
        make_st("ST2", date(2023, 6, 16), date(2023, 12, 31), Decimal("45")),
    ]

    effective_periods = sweep(eps, wps, sts)

    assert len(effective_periods) == 2
    assert effective_periods[0].end == date(2023, 6, 15)
    assert effective_periods[1].start == date(2023, 6, 16)


def test_sweep_pattern_change_mid_week():
    """Test sweep with pattern change mid-week (edge case from skill)."""
    eps = [make_ep("EMP_A", date(2024, 6, 15), date(2024, 6, 25))]
    wps = [
        make_wp("WP1", date(2024, 6, 15), date(2024, 6, 18)),  # Sat-Tue
        make_wp("WP2", date(2024, 6, 19), date(2024, 6, 25)),  # Wed onwards
    ]
    sts = [make_st("ST1", date(2024, 6, 15), date(2024, 6, 25))]

    effective_periods = sweep(eps, wps, sts)

    assert len(effective_periods) == 2
    assert effective_periods[0].end == date(2024, 6, 18)
    assert effective_periods[1].start == date(2024, 6, 19)


def test_sweep_multiple_eps_with_gap():
    """Test sweep with multiple employment periods and a gap."""
    eps = [
        make_ep("EMP_A", date(2023, 1, 1), date(2023, 6, 30)),
        make_ep("EMP_B", date(2023, 9, 1), date(2023, 12, 31)),  # Gap in July-Aug
    ]
    wps = [make_wp("WP1", date(2023, 1, 1), date(2023, 12, 31))]
    sts = [make_st("ST1", date(2023, 1, 1), date(2023, 12, 31))]

    effective_periods = sweep(eps, wps, sts)

    # Two separate effective periods (even though WP and ST are the same)
    assert len(effective_periods) == 2
    assert effective_periods[0].employment_period_id == "EMP_A"
    assert effective_periods[1].employment_period_id == "EMP_B"


def test_sweep_denormalizes_data():
    """Test that sweep denormalizes work pattern and salary data."""
    eps = [make_ep("EP1", date(2023, 1, 1), date(2023, 12, 31))]
    wps = [make_wp("WP1", date(2023, 1, 1), date(2023, 12, 31), work_days=[0, 1, 2, 3, 4])]
    sts = [make_st("ST1", date(2023, 1, 1), date(2023, 12, 31), Decimal("45"))]

    effective_periods = sweep(eps, wps, sts)

    assert len(effective_periods) == 1
    ep = effective_periods[0]
    assert ep.pattern_work_days == [0, 1, 2, 3, 4]
    assert len(ep.pattern_default_shifts) == 1
    assert ep.salary_amount == Decimal("45")
    assert ep.salary_type == SalaryType.HOURLY


def test_sweep_full_example_from_skill():
    """Test full example from skill documentation."""
    # From skill example:
    # EMP_A: 2023-01-01 → 2023-12-31
    # EMP_B: 2024-03-01 → 2024-12-31
    # WP1: 2023-01-01 → 2024-06-30
    # WP2: 2024-07-01 → 2024-12-31
    # ST1: 2023-01-01 → 2023-08-31
    # ST2: 2023-09-01 → 2024-12-31

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

    effective_periods = sweep(eps, wps, sts)

    # Expected: 4 effective periods
    # [2023-01-01 → 2023-08-31]  EMP_A + WP1 + ST1
    # [2023-09-01 → 2023-12-31]  EMP_A + WP1 + ST2
    # [2024-03-01 → 2024-06-30]  EMP_B + WP1 + ST2
    # [2024-07-01 → 2024-12-31]  EMP_B + WP2 + ST2

    assert len(effective_periods) == 4

    assert effective_periods[0].start == date(2023, 1, 1)
    assert effective_periods[0].end == date(2023, 8, 31)
    assert effective_periods[0].salary_tier_id == "ST1"

    assert effective_periods[1].start == date(2023, 9, 1)
    assert effective_periods[1].end == date(2023, 12, 31)
    assert effective_periods[1].salary_tier_id == "ST2"

    assert effective_periods[2].start == date(2024, 3, 1)
    assert effective_periods[2].end == date(2024, 6, 30)
    assert effective_periods[2].employment_period_id == "EMP_B"

    assert effective_periods[3].start == date(2024, 7, 1)
    assert effective_periods[3].work_pattern_id == "WP2"
