"""Tests for limitation module.

Test fixtures from docs/skills/limitation/LIMITATION_TEST_FIXTURES.md
"""

import pytest
from datetime import date, timedelta
from decimal import Decimal

from app.modules.limitation import (
    compute_effective_window,
    compute_limitation_window,
    compute_general_base_window,
    compute_vacation_base_window,
    merge_freeze_periods,
    filter_period_by_window,
    filter_monthly_results,
    days_between,
    FreezePeriod,
    LimitationType,
    LimitationConfig,
    GENERAL_LIMITATION,
    VACATION_LIMITATION,
    DEFAULT_WAR_FREEZE,
)


class TestDaysBetween:
    """Test days_between helper."""

    def test_same_day(self):
        """Same day = 1 day."""
        assert days_between(date(2024, 1, 1), date(2024, 1, 1)) == 1

    def test_consecutive_days(self):
        """Two consecutive days = 2 days."""
        assert days_between(date(2024, 1, 1), date(2024, 1, 2)) == 2

    def test_year(self):
        """Full year 2024 (leap) = 366 days."""
        assert days_between(date(2024, 1, 1), date(2024, 12, 31)) == 366


class TestMergeFreezePeriods:
    """Test merging of overlapping freeze periods."""

    def test_no_overlap(self):
        """Non-overlapping periods stay separate."""
        freezes = [
            FreezePeriod("a", "A", date(2023, 1, 1), date(2023, 3, 31)),
            FreezePeriod("b", "B", date(2023, 6, 1), date(2023, 8, 31)),
        ]
        merged = merge_freeze_periods(freezes)
        assert len(merged) == 2

    def test_overlapping_merge(self):
        """Overlapping periods are merged."""
        freezes = [
            FreezePeriod("a", "A", date(2023, 8, 1), date(2024, 1, 31)),
            FreezePeriod("b", "B", date(2023, 10, 7), date(2024, 4, 6)),
        ]
        merged = merge_freeze_periods(freezes)

        assert len(merged) == 1
        assert merged[0].start_date == date(2023, 8, 1)
        assert merged[0].end_date == date(2024, 4, 6)
        # 2023-08-01 to 2024-04-06 = 250 days
        assert merged[0].days == 250

    def test_adjacent_merge(self):
        """Adjacent periods (end + 1 = start) are merged."""
        freezes = [
            FreezePeriod("a", "A", date(2023, 1, 1), date(2023, 1, 31)),
            FreezePeriod("b", "B", date(2023, 2, 1), date(2023, 2, 28)),
        ]
        merged = merge_freeze_periods(freezes)

        assert len(merged) == 1
        assert merged[0].start_date == date(2023, 1, 1)
        assert merged[0].end_date == date(2023, 2, 28)

    def test_empty_list(self):
        """Empty list returns empty."""
        assert merge_freeze_periods([]) == []


class TestBaseWindowCalculation:
    """Test base window calculation for each limitation type."""

    def test_general_7_years(self):
        """General limitation: 7 years back."""
        result = compute_general_base_window(date(2025, 6, 1))
        assert result == date(2018, 6, 1)

    def test_general_leap_year(self):
        """General limitation handles Feb 29."""
        # Feb 29, 2024 - 7 years = Feb 28, 2017 (not Feb 29)
        result = compute_general_base_window(date(2024, 2, 29))
        assert result == date(2017, 2, 28)

    def test_vacation_3_plus_current(self):
        """Vacation limitation: January 1 of (filing_year - 3)."""
        result = compute_vacation_base_window(date(2025, 3, 15))
        assert result == date(2022, 1, 1)

    def test_vacation_december(self):
        """Vacation limitation: December filing still uses same formula."""
        result = compute_vacation_base_window(date(2025, 12, 31))
        assert result == date(2022, 1, 1)


class TestFixture1BasicNoFreezes:
    """Test 1: Basic general limitation, no freezes."""

    def test_no_freezes(self):
        """Filing 2025-06-01, no freezes → base = effective."""
        filing = date(2025, 6, 1)
        base_start = compute_general_base_window(filing)

        effective, applied = compute_effective_window(filing, base_start, [])

        assert base_start == date(2018, 6, 1)
        assert effective == date(2018, 6, 1)
        assert applied == []


class TestFixture2GeneralWithOneFreeze:
    """Test 2: General limitation with one fully-contained freeze."""

    def test_war_freeze(self):
        """Filing 2025-06-01, war freeze → effective extends back."""
        filing = date(2025, 6, 1)
        base_start = compute_general_base_window(filing)

        freeze = FreezePeriod(
            "war", "הקפאת מלחמת התקומה",
            date(2023, 10, 7), date(2024, 4, 6)
        )

        effective, applied = compute_effective_window(filing, base_start, [freeze])

        # Base: 2018-06-01
        # Freeze: 183 days
        # Effective: 2018-06-01 - 183 days = 2017-11-30
        assert base_start == date(2018, 6, 1)
        assert effective == date(2017, 11, 30)
        assert len(applied) == 1


class TestFixture3TwoFreezesPartialOutside:
    """Test 3: Two freezes, one partially outside base window."""

    def test_two_freezes(self):
        """Two freezes, one extends beyond base window."""
        filing = date(2025, 6, 1)
        base_start = compute_general_base_window(filing)

        freezes = [
            FreezePeriod("a", "A", date(2023, 10, 7), date(2024, 4, 6)),
            FreezePeriod("b", "B", date(2017, 6, 1), date(2018, 1, 31)),
        ]

        effective, applied = compute_effective_window(filing, base_start, freezes)

        # Per algorithm trace in fixture:
        # Gap 1: 421 days, Gap 2: 2073 days, Final: 63 days
        # Effective: 2017-03-30
        assert effective == date(2017, 3, 30)


class TestFixture4VacationNoFreezes:
    """Test 4: Vacation limitation (3+שוטף), no freezes."""

    def test_vacation_no_freezes(self):
        """Vacation limitation without freezes."""
        filing = date(2025, 3, 15)
        base_start = compute_vacation_base_window(filing)

        effective, applied = compute_effective_window(filing, base_start, [])

        assert base_start == date(2022, 1, 1)
        assert effective == date(2022, 1, 1)


class TestFixture5VacationWithFreeze:
    """Test 5: Vacation limitation with freeze."""

    def test_vacation_with_freeze(self):
        """Vacation limitation with war freeze."""
        filing = date(2025, 3, 15)
        base_start = compute_vacation_base_window(filing)

        freeze = FreezePeriod(
            "war", "הקפאת מלחמת התקומה",
            date(2023, 10, 7), date(2024, 4, 6)
        )

        effective, applied = compute_effective_window(filing, base_start, [freeze])

        # Per algorithm trace: effective = 2021-07-02
        assert effective == date(2021, 7, 2)


class TestFixture6VacationEdgeDecemberJanuary:
    """Test 6: Vacation edge — December 31 vs January 1."""

    def test_december_31(self):
        """Filing December 31, 2025 → base starts Jan 1, 2022."""
        base = compute_vacation_base_window(date(2025, 12, 31))
        assert base == date(2022, 1, 1)

    def test_january_1(self):
        """Filing January 1, 2026 → base starts Jan 1, 2023."""
        base = compute_vacation_base_window(date(2026, 1, 1))
        assert base == date(2023, 1, 1)

    def test_one_day_one_year_difference(self):
        """One day difference in filing → one year difference in window."""
        base_dec = compute_vacation_base_window(date(2025, 12, 31))
        base_jan = compute_vacation_base_window(date(2026, 1, 1))

        assert (base_jan.year - base_dec.year) == 1


class TestFixture7OverlappingFreezes:
    """Test 7: Overlapping freeze periods (must merge)."""

    def test_overlapping_merged(self):
        """Overlapping freezes are merged before calculation."""
        filing = date(2025, 6, 1)
        base_start = compute_general_base_window(filing)

        freezes = [
            FreezePeriod("a", "A", date(2023, 8, 1), date(2024, 1, 31)),
            FreezePeriod("b", "B", date(2023, 10, 7), date(2024, 4, 6)),
        ]

        # Merged: 2023-08-01 to 2024-04-06 = 250 days
        merged = merge_freeze_periods(freezes)
        assert len(merged) == 1
        assert merged[0].days == 250

        effective, applied = compute_effective_window(filing, base_start, freezes)

        # Merged freeze: 250 days
        # Gap after freeze: 421 days
        # Remaining: 2558 - 421 = 2137 days
        # Cursor: 2023-07-31, effective = 2023-07-31 - 2136 = 2017-09-24
        assert effective == date(2017, 9, 24)


class TestFixture8FreezeAfterFiling:
    """Test 8: Freeze entirely after filing date (irrelevant)."""

    def test_freeze_after_filing_ignored(self):
        """Freeze after filing date is ignored."""
        filing = date(2023, 6, 1)
        base_start = compute_general_base_window(filing)

        freeze = FreezePeriod(
            "war", "הקפאת מלחמת התקומה",
            date(2023, 10, 7), date(2024, 4, 6)
        )

        effective, applied = compute_effective_window(filing, base_start, [freeze])

        # Freeze is entirely after filing → ignored
        assert effective == base_start
        assert effective == date(2016, 6, 1)


class TestFixture9NoFreezePeriods:
    """Test 9: No freeze periods."""

    def test_empty_freeze_list(self):
        """Empty freeze list → effective = base."""
        filing = date(2025, 1, 15)
        base_start = compute_general_base_window(filing)

        effective, applied = compute_effective_window(filing, base_start, [])

        assert effective == date(2018, 1, 15)
        assert applied == []


class TestFixture10EmploymentAfterWindow:
    """Test 10: Employment started after effective window start."""

    def test_employment_after_window(self):
        """Effective window extends before employment — no limitation cut."""
        filing = date(2025, 6, 1)
        base_start = compute_general_base_window(filing)
        employment_start = date(2020, 3, 1)

        freeze = FreezePeriod(
            "war", "הקפאת מלחמת התקומה",
            date(2023, 10, 7), date(2024, 4, 6)
        )

        effective, _ = compute_effective_window(filing, base_start, [freeze])

        # Effective: 2017-11-30 (same as Test 2)
        # Employment started 2020-03-01 — after effective
        # So limitation doesn't cut anything
        assert effective == date(2017, 11, 30)
        assert employment_start > effective


class TestFixture11MultipleLimitationTypes:
    """Test 11: Multiple limitation types in same claim."""

    def test_different_windows_per_type(self):
        """Different rights have different limitation windows."""
        filing = date(2025, 6, 1)

        freeze = FreezePeriod(
            "war", "הקפאת מלחמת התקומה",
            date(2023, 10, 7), date(2024, 4, 6)
        )

        config = LimitationConfig(filing_date=filing, freeze_periods=[freeze])

        general_window = compute_limitation_window(GENERAL_LIMITATION, config)
        vacation_window = compute_limitation_window(VACATION_LIMITATION, config)

        # General: effective 2017-11-30
        assert general_window.effective_window_start == date(2017, 11, 30)

        # Vacation: base 2022-01-01, effective 2021-07-02
        assert vacation_window.base_window_start == date(2022, 1, 1)
        assert vacation_window.effective_window_start == date(2021, 7, 2)


class TestFixture12PartialMonthFiltering:
    """Test 12: Filtering — partial month at boundary."""

    def test_partial_month(self):
        """Partial month at boundary is pro-rated."""
        # Effective window starts June 15
        # June 2018 (30 days): days 15-30 = 16 days within window
        result = filter_period_by_window(
            period_start=date(2018, 6, 1),
            period_end=date(2018, 6, 30),
            full_amount=Decimal("1000"),
            effective_window_start=date(2018, 6, 15),
            filing_date=date(2025, 6, 1),
        )

        # 16 out of 30 days
        assert result.fraction == Decimal("16") / Decimal("30")
        # 1000 * (16/30) = 533.33...
        expected = Decimal("1000") * Decimal("16") / Decimal("30")
        assert result.claimable_amount == expected
        assert result.excluded_amount == Decimal("1000") - expected

    def test_fully_inside_window(self):
        """Period fully inside window = 100%."""
        result = filter_period_by_window(
            period_start=date(2020, 6, 1),
            period_end=date(2020, 6, 30),
            full_amount=Decimal("1000"),
            effective_window_start=date(2018, 6, 1),
            filing_date=date(2025, 6, 1),
        )

        assert result.fraction == Decimal("1")
        assert result.claimable_amount == Decimal("1000")
        assert result.excluded_amount == Decimal("0")

    def test_fully_outside_window(self):
        """Period fully outside window = 0%."""
        result = filter_period_by_window(
            period_start=date(2015, 6, 1),
            period_end=date(2015, 6, 30),
            full_amount=Decimal("1000"),
            effective_window_start=date(2018, 6, 1),
            filing_date=date(2025, 6, 1),
        )

        assert result.fraction == Decimal("0")
        assert result.claimable_amount == Decimal("0")
        assert result.excluded_amount == Decimal("1000")


class TestFixture13FilingInsideFreeze:
    """Test 13: Filing date within a freeze period."""

    def test_filing_inside_freeze(self):
        """Filing date inside freeze period."""
        filing = date(2024, 1, 15)  # Inside war freeze
        base_start = compute_general_base_window(filing)

        freeze = FreezePeriod(
            "war", "הקפאת מלחמת התקומה",
            date(2023, 10, 7), date(2024, 4, 6)
        )

        effective, applied = compute_effective_window(filing, base_start, [freeze])

        # Base: 2017-01-15
        # Filing inside freeze: cursor jumps to 2023-10-06
        # Then walk back to find effective start
        # active_needed = days_between(2017-01-15, 2024-01-15)
        assert base_start == date(2017, 1, 15)

        # Per fixture: effective ≈ 2016-10-08
        # Let's verify the algorithm handles this correctly
        assert effective < base_start
        assert len(applied) == 1


class TestFilterMonthlyResults:
    """Test filtering of monthly results."""

    def test_filter_monthly(self):
        """Filter multiple months by limitation window."""
        monthly = {
            (2017, 6): Decimal("1000"),  # Before window
            (2018, 6): Decimal("1000"),  # Partial (if boundary)
            (2020, 6): Decimal("1000"),  # Inside window
        }

        total_claim, total_excl, details = filter_monthly_results(
            monthly,
            effective_window_start=date(2018, 6, 15),
            filing_date=date(2025, 6, 1),
        )

        # 2017-06: fully excluded
        # 2018-06: partially included (16/30)
        # 2020-06: fully included
        assert len(details) == 3

        # Find each month's result
        jun_2017 = next(d for d in details if d[0] == (2017, 6))
        jun_2018 = next(d for d in details if d[0] == (2018, 6))
        jun_2020 = next(d for d in details if d[0] == (2020, 6))

        assert jun_2017[1].claimable_amount == Decimal("0")
        assert jun_2018[1].fraction == Decimal("16") / Decimal("30")
        assert jun_2020[1].claimable_amount == Decimal("1000")


class TestWarFreezeDefault:
    """Test the default war freeze period."""

    def test_war_freeze_dates(self):
        """War freeze has correct dates."""
        assert DEFAULT_WAR_FREEZE.start_date == date(2023, 10, 7)
        assert DEFAULT_WAR_FREEZE.end_date == date(2024, 4, 6)
        assert DEFAULT_WAR_FREEZE.days == 183


class TestEdgeCases:
    """Additional edge cases."""

    def test_freeze_before_base_window(self):
        """Freeze entirely before base window has no effect."""
        filing = date(2025, 6, 1)
        base_start = compute_general_base_window(filing)  # 2018-06-01

        # Freeze entirely before base window
        freeze = FreezePeriod("old", "Old", date(2010, 1, 1), date(2010, 12, 31))

        effective, applied = compute_effective_window(filing, base_start, [freeze])

        # No effect — freeze is too old
        assert effective == base_start

    def test_multiple_small_freezes(self):
        """Multiple small non-overlapping freezes accumulate."""
        filing = date(2025, 6, 1)
        base_start = compute_general_base_window(filing)

        freezes = [
            FreezePeriod("a", "A", date(2024, 1, 1), date(2024, 1, 31)),  # 31 days
            FreezePeriod("b", "B", date(2023, 6, 1), date(2023, 6, 30)),  # 30 days
            FreezePeriod("c", "C", date(2022, 1, 1), date(2022, 1, 31)),  # 31 days
        ]

        effective, applied = compute_effective_window(filing, base_start, freezes)

        # Total freeze: 92 days
        # Effective should be 92 days earlier than base
        expected = base_start - timedelta(days=92)
        assert effective == expected

    def test_freeze_spans_entire_base_window(self):
        """Freeze spanning entire base window extends it fully."""
        filing = date(2025, 6, 1)
        base_start = compute_general_base_window(filing)  # 2018-06-01

        # Freeze spans most of the window
        freeze = FreezePeriod(
            "long", "Long",
            date(2018, 7, 1),
            date(2025, 5, 31)
        )

        effective, applied = compute_effective_window(filing, base_start, [freeze])

        # Window extends back significantly
        assert effective < base_start
