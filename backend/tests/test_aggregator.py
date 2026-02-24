"""Tests for aggregator module.

Test cases from docs/skills/aggregator/SKILL.md edge cases section.
"""

import pytest
from datetime import date
from decimal import Decimal

from app.modules.aggregator import run_aggregator, AggregatorResult
from app.ssot import Shift


def create_shift(
    shift_id: str,
    effective_period_id: str,
    assigned_day: date,
    regular_hours: Decimal,
    ot_tier1_hours: Decimal = Decimal("0"),
    ot_tier2_hours: Decimal = Decimal("0"),
) -> Shift:
    """Helper to create a shift with required fields."""
    return Shift(
        id=shift_id,
        date=assigned_day,
        effective_period_id=effective_period_id,
        assigned_day=assigned_day,
        regular_hours=regular_hours,
        ot_tier1_hours=ot_tier1_hours,
        ot_tier2_hours=ot_tier2_hours,
    )


class TestBasicAggregation:
    """Basic aggregation tests."""

    def test_single_period_single_month(self):
        """Simple case: one period, one month, multiple shifts."""
        shifts = [
            create_shift("s1", "ep1", date(2024, 3, 1), Decimal("8")),
            create_shift("s2", "ep1", date(2024, 3, 2), Decimal("8")),
            create_shift("s3", "ep1", date(2024, 3, 3), Decimal("8")),
        ]

        result = run_aggregator(shifts)

        assert len(result.period_month_records) == 1
        pmr = result.period_month_records[0]
        assert pmr.effective_period_id == "ep1"
        assert pmr.month == (2024, 3)
        assert pmr.work_days_count == 3
        assert pmr.shifts_count == 3
        assert pmr.total_regular_hours == Decimal("24")
        assert pmr.total_ot_hours == Decimal("0")
        assert pmr.avg_regular_hours_per_day == Decimal("8")
        assert pmr.avg_regular_hours_per_shift == Decimal("8")

        assert len(result.month_aggregates) == 1
        ma = result.month_aggregates[0]
        assert ma.month == (2024, 3)
        assert ma.total_regular_hours == Decimal("24")
        assert ma.total_work_days == 3

    def test_with_overtime_hours(self):
        """Test aggregation of overtime hours."""
        shifts = [
            create_shift(
                "s1", "ep1", date(2024, 3, 1),
                regular_hours=Decimal("8"),
                ot_tier1_hours=Decimal("2"),
                ot_tier2_hours=Decimal("1"),
            ),
            create_shift(
                "s2", "ep1", date(2024, 3, 2),
                regular_hours=Decimal("8"),
                ot_tier1_hours=Decimal("1"),
                ot_tier2_hours=Decimal("0"),
            ),
        ]

        result = run_aggregator(shifts)

        pmr = result.period_month_records[0]
        assert pmr.total_regular_hours == Decimal("16")
        assert pmr.total_ot_hours == Decimal("4")  # 2+1 + 1+0


class TestEdgeCases:
    """Edge cases from skill documentation."""

    def test_1_month_split_between_two_periods(self):
        """Case 1: Month split between two atomic periods.

        Period A: 01.03 - 15.03
        Period B: 16.03 - 31.03

        Should create two separate period_month_records for March,
        and one combined month_aggregate.
        """
        shifts = []

        # Period A: 11 work days, 8 hours each
        for day in range(1, 12):  # 1-11 March
            shifts.append(create_shift(
                f"sa{day}", "period_a", date(2024, 3, day), Decimal("8")
            ))

        # Period B: 11 work days, 8 hours each
        for day in range(16, 27):  # 16-26 March
            shifts.append(create_shift(
                f"sb{day}", "period_b", date(2024, 3, day), Decimal("8")
            ))

        result = run_aggregator(shifts)

        # Two period_month_records for March
        assert len(result.period_month_records) == 2

        pmr_a = next(p for p in result.period_month_records if p.effective_period_id == "period_a")
        pmr_b = next(p for p in result.period_month_records if p.effective_period_id == "period_b")

        assert pmr_a.month == (2024, 3)
        assert pmr_a.work_days_count == 11
        assert pmr_a.total_regular_hours == Decimal("88")
        assert pmr_a.avg_regular_hours_per_day == Decimal("8")

        assert pmr_b.month == (2024, 3)
        assert pmr_b.work_days_count == 11
        assert pmr_b.total_regular_hours == Decimal("88")
        assert pmr_b.avg_regular_hours_per_day == Decimal("8")

        # One month_aggregate combining both
        assert len(result.month_aggregates) == 1
        ma = result.month_aggregates[0]
        assert ma.month == (2024, 3)
        assert ma.total_work_days == 22
        assert ma.total_regular_hours == Decimal("176")

    def test_2_period_starts_mid_month(self):
        """Case 2: Period starts mid-month.

        Employment starts on 20th - only 8 work days in first month.
        Averages should be computed from actual data, not normalized.
        """
        shifts = []

        # 8 work days from 20th onwards
        for day in range(20, 28):
            shifts.append(create_shift(
                f"s{day}", "ep1", date(2024, 3, day), Decimal("8")
            ))

        result = run_aggregator(shifts)

        pmr = result.period_month_records[0]
        assert pmr.work_days_count == 8
        assert pmr.total_regular_hours == Decimal("64")
        assert pmr.avg_regular_hours_per_day == Decimal("8")

    def test_3_multiple_shifts_same_day(self):
        """Case 3: Multiple shifts on the same day.

        Day with two shifts: morning and evening.
        work_days_count = 1, shifts_count = 2.
        """
        shifts = [
            # Morning shift: 6 hours
            create_shift("s1", "ep1", date(2024, 3, 5), Decimal("6")),
            # Evening shift: 5 hours
            create_shift("s2", "ep1", date(2024, 3, 5), Decimal("5")),
        ]

        result = run_aggregator(shifts)

        pmr = result.period_month_records[0]
        assert pmr.work_days_count == 1  # One day
        assert pmr.shifts_count == 2  # Two shifts
        assert pmr.total_regular_hours == Decimal("11")
        assert pmr.avg_regular_hours_per_day == Decimal("11")  # 11 / 1
        assert pmr.avg_regular_hours_per_shift == Decimal("5.5")  # 11 / 2

    def test_4_month_with_no_shifts(self):
        """Case 4: Month without shifts.

        No shifts in April - should have no record for April.
        """
        shifts = [
            create_shift("s1", "ep1", date(2024, 3, 15), Decimal("8")),
            create_shift("s2", "ep1", date(2024, 5, 1), Decimal("8")),
        ]

        result = run_aggregator(shifts)

        # Should only have March and May
        months = [pmr.month for pmr in result.period_month_records]
        assert (2024, 3) in months
        assert (2024, 5) in months
        assert (2024, 4) not in months

        ma_months = [ma.month for ma in result.month_aggregates]
        assert (2024, 4) not in ma_months

    def test_5_shift_assigned_to_different_month(self):
        """Case 5: Shift assigned to different month by majority rule.

        Night shift starting 31.03 assigned to 01.04 by OT pipeline.
        Should count in April, not March.
        """
        # Shift that started March 31 but assigned to April 1
        shift = create_shift("s1", "ep1", date(2024, 4, 1), Decimal("8"))
        # Override date to simulate original start date
        shift.date = date(2024, 3, 31)

        result = run_aggregator([shift])

        pmr = result.period_month_records[0]
        assert pmr.month == (2024, 4)  # April, not March


class TestMultipleMonths:
    """Tests spanning multiple months."""

    def test_multiple_months_same_period(self):
        """Multiple months in the same period."""
        shifts = [
            create_shift("s1", "ep1", date(2024, 1, 15), Decimal("8")),
            create_shift("s2", "ep1", date(2024, 2, 15), Decimal("8")),
            create_shift("s3", "ep1", date(2024, 3, 15), Decimal("8")),
        ]

        result = run_aggregator(shifts)

        assert len(result.period_month_records) == 3
        assert len(result.month_aggregates) == 3

        # All belong to same period
        for pmr in result.period_month_records:
            assert pmr.effective_period_id == "ep1"

    def test_cross_period_same_month(self):
        """Same month, different periods - month_aggregate sums them."""
        shifts = [
            create_shift("s1", "ep1", date(2024, 3, 5), Decimal("8")),
            create_shift("s2", "ep2", date(2024, 3, 20), Decimal("9")),
        ]

        result = run_aggregator(shifts)

        # Two period_month_records
        assert len(result.period_month_records) == 2

        # One month_aggregate with combined totals
        assert len(result.month_aggregates) == 1
        ma = result.month_aggregates[0]
        assert ma.total_regular_hours == Decimal("17")
        assert ma.total_work_days == 2
        assert ma.total_shifts == 2


class TestAntiPatterns:
    """Tests for anti-patterns from skill doc."""

    def test_no_mixing_periods_in_averages(self):
        """Anti-pattern 1: Do not mix periods when computing averages.

        Each period gets its own avg_regular_hours_per_day.
        """
        shifts = [
            # Period A: 1 day, 10 hours
            create_shift("s1", "period_a", date(2024, 3, 5), Decimal("10")),
            # Period B: 1 day, 6 hours
            create_shift("s2", "period_b", date(2024, 3, 20), Decimal("6")),
        ]

        result = run_aggregator(shifts)

        pmr_a = next(p for p in result.period_month_records if p.effective_period_id == "period_a")
        pmr_b = next(p for p in result.period_month_records if p.effective_period_id == "period_b")

        # Each has its own average, not mixed
        assert pmr_a.avg_regular_hours_per_day == Decimal("10")
        assert pmr_b.avg_regular_hours_per_day == Decimal("6")

        # Anti-pattern would be (10+6)/2 = 8 for both

    def test_work_days_from_shifts_not_daily_records(self):
        """Anti-pattern 2: Count work days from shifts, not daily_records.

        Even if a day is marked as work day in pattern, if no shift exists,
        it should not be counted.
        """
        # Only 2 shifts, even if pattern says 5 work days
        shifts = [
            create_shift("s1", "ep1", date(2024, 3, 4), Decimal("8")),
            create_shift("s2", "ep1", date(2024, 3, 6), Decimal("8")),
        ]

        result = run_aggregator(shifts)

        pmr = result.period_month_records[0]
        assert pmr.work_days_count == 2  # Not 5 from pattern

    def test_no_records_for_empty_months(self):
        """Anti-pattern 3: Do not create records for empty months."""
        shifts = [
            create_shift("s1", "ep1", date(2024, 1, 15), Decimal("8")),
            # Gap: February has no shifts
            create_shift("s2", "ep1", date(2024, 3, 15), Decimal("8")),
        ]

        result = run_aggregator(shifts)

        # Should not have February
        months = {pmr.month for pmr in result.period_month_records}
        assert (2024, 2) not in months

    def test_no_rounding(self):
        """Anti-pattern 4: No rounding - all values decimal."""
        shifts = [
            create_shift("s1", "ep1", date(2024, 3, 1), Decimal("7")),
            create_shift("s2", "ep1", date(2024, 3, 2), Decimal("8")),
            create_shift("s3", "ep1", date(2024, 3, 3), Decimal("9")),
        ]

        result = run_aggregator(shifts)

        pmr = result.period_month_records[0]
        # 24 / 3 = 8 exactly
        assert pmr.avg_regular_hours_per_day == Decimal("8")

        # Test with non-round division
        shifts2 = [
            create_shift("s1", "ep2", date(2024, 4, 1), Decimal("7")),
            create_shift("s2", "ep2", date(2024, 4, 2), Decimal("8")),
        ]

        result2 = run_aggregator(shifts2)
        pmr2 = result2.period_month_records[0]
        # 15 / 2 = 7.5 exactly, not rounded
        assert pmr2.avg_regular_hours_per_day == Decimal("7.5")

    def test_uses_assigned_day_not_date(self):
        """Anti-pattern 5: Use assigned_day, not shift.date."""
        shift = Shift(
            id="s1",
            date=date(2024, 3, 31),  # Original date
            effective_period_id="ep1",
            assigned_day=date(2024, 4, 1),  # Assigned to April
            regular_hours=Decimal("8"),
            ot_tier1_hours=Decimal("0"),
            ot_tier2_hours=Decimal("0"),
        )

        result = run_aggregator([shift])

        pmr = result.period_month_records[0]
        # Should be April (assigned_day), not March (date)
        assert pmr.month == (2024, 4)


class TestEmptyInput:
    """Test with empty input."""

    def test_empty_shifts_list(self):
        """Empty shifts list returns empty results."""
        result = run_aggregator([])

        assert result.period_month_records == []
        assert result.month_aggregates == []

    def test_shifts_without_assigned_day(self):
        """Shifts without assigned_day are skipped."""
        shift = Shift(
            id="s1",
            date=date(2024, 3, 15),
            effective_period_id="ep1",
            assigned_day=None,  # Not assigned
            regular_hours=Decimal("8"),
            ot_tier1_hours=Decimal("0"),
            ot_tier2_hours=Decimal("0"),
        )

        result = run_aggregator([shift])

        assert result.period_month_records == []
        assert result.month_aggregates == []
