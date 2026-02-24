"""Tests for job scope module.

Test fixtures from docs/skills/job-scope/JOB_SCOPE_TEST_FIXTURES.md
"""

import pytest
from decimal import Decimal

from app.modules.job_scope import (
    calculate_job_scope,
    process_month_aggregate,
    run_job_scope,
    DEFAULT_FULL_TIME_HOURS_BASE,
)
from app.ssot import MonthAggregate


class TestJobScopeCalculation:
    """Test job scope calculation from TEST_FIXTURES."""

    def test_1_full_time(self):
        """Test 1: Full-time - 182 hours = 100%."""
        raw, effective = calculate_job_scope(Decimal("182"))

        assert raw == Decimal("1")
        assert effective == Decimal("1")

    def test_2_part_time(self):
        """Test 2: Part-time - 91 hours = 50%."""
        raw, effective = calculate_job_scope(Decimal("91"))

        assert raw == Decimal("0.5")
        assert effective == Decimal("0.5")

    def test_3_over_182_capped(self):
        """Test 3: Over 182 hours - capped at 100%."""
        raw, effective = calculate_job_scope(Decimal("200"))

        # raw = 200 / 182 = 1.0989...
        assert raw == Decimal("200") / Decimal("182")
        assert raw > Decimal("1")
        # effective capped at 1.0
        assert effective == Decimal("1")

    def test_4_zero_hours(self):
        """Test 4: Zero hours = 0%."""
        raw, effective = calculate_job_scope(Decimal("0"))

        assert raw == Decimal("0")
        assert effective == Decimal("0")

    def test_5_partial_month(self):
        """Test 5: Partial month - started mid-month, 80 hours."""
        raw, effective = calculate_job_scope(Decimal("80"))

        # 80 / 182 = 0.4395604...
        expected = Decimal("80") / Decimal("182")
        assert raw == expected
        assert effective == expected

    def test_6_varying_scope_across_months(self):
        """Test 6: Varying scope across months."""
        # January: 160 hours
        raw_jan, eff_jan = calculate_job_scope(Decimal("160"))
        assert raw_jan == Decimal("160") / Decimal("182")
        assert eff_jan == Decimal("160") / Decimal("182")

        # February: 182 hours (full)
        raw_feb, eff_feb = calculate_job_scope(Decimal("182"))
        assert raw_feb == Decimal("1")
        assert eff_feb == Decimal("1")

        # March: 100 hours
        raw_mar, eff_mar = calculate_job_scope(Decimal("100"))
        assert raw_mar == Decimal("100") / Decimal("182")
        assert eff_mar == Decimal("100") / Decimal("182")


class TestMonthAggregateProcessing:
    """Test processing of MonthAggregate records."""

    def test_process_single_aggregate(self):
        """Process a single month aggregate."""
        ma = MonthAggregate(
            month=(2024, 6),
            total_regular_hours=Decimal("160"),
            total_ot_hours=Decimal("20"),
            total_work_days=20,
            total_shifts=20,
        )

        result = process_month_aggregate(ma)

        assert result.full_time_hours_base == Decimal("182")
        assert result.raw_scope == Decimal("160") / Decimal("182")
        assert result.job_scope == Decimal("160") / Decimal("182")

    def test_process_aggregate_capped(self):
        """Process aggregate with hours > 182 - scope capped."""
        ma = MonthAggregate(
            month=(2024, 6),
            total_regular_hours=Decimal("200"),
            total_ot_hours=Decimal("0"),
            total_work_days=25,
            total_shifts=25,
        )

        result = process_month_aggregate(ma)

        assert result.raw_scope > Decimal("1")
        assert result.job_scope == Decimal("1")  # Capped


class TestRunJobScope:
    """Test run_job_scope on multiple months."""

    def test_run_multiple_months(self):
        """Process multiple month aggregates."""
        aggregates = [
            MonthAggregate(
                month=(2024, 1),
                total_regular_hours=Decimal("160"),
                total_ot_hours=Decimal("10"),
                total_work_days=20,
                total_shifts=20,
            ),
            MonthAggregate(
                month=(2024, 2),
                total_regular_hours=Decimal("182"),
                total_ot_hours=Decimal("15"),
                total_work_days=22,
                total_shifts=22,
            ),
            MonthAggregate(
                month=(2024, 3),
                total_regular_hours=Decimal("100"),
                total_ot_hours=Decimal("5"),
                total_work_days=12,
                total_shifts=12,
            ),
        ]

        results = run_job_scope(aggregates)

        assert len(results) == 3

        # January: 160/182
        assert results[0].job_scope == Decimal("160") / Decimal("182")

        # February: 182/182 = 1.0
        assert results[1].job_scope == Decimal("1")

        # March: 100/182
        assert results[2].job_scope == Decimal("100") / Decimal("182")

    def test_empty_list(self):
        """Empty list returns empty list."""
        results = run_job_scope([])
        assert results == []


class TestCustomFullTimeBase:
    """Test with custom full-time hours base."""

    def test_custom_base(self):
        """Use custom full-time hours base."""
        # If legislation changes to 186 hours
        raw, effective = calculate_job_scope(
            Decimal("186"),
            full_time_hours_base=Decimal("186"),
        )

        assert raw == Decimal("1")
        assert effective == Decimal("1")

    def test_custom_base_partial(self):
        """Custom base with partial hours."""
        raw, effective = calculate_job_scope(
            Decimal("93"),
            full_time_hours_base=Decimal("186"),
        )

        assert raw == Decimal("0.5")
        assert effective == Decimal("0.5")


class TestAntiPatterns:
    """Test anti-patterns from skill doc."""

    def test_no_hardcoded_182(self):
        """DO NOT hardcode 182 - use configurable base."""
        # Verify default is from constant, not hardcoded
        assert DEFAULT_FULL_TIME_HOURS_BASE == Decimal("182")

        # Can be overridden
        raw, _ = calculate_job_scope(
            Decimal("200"),
            full_time_hours_base=Decimal("200"),
        )
        assert raw == Decimal("1")

    def test_never_exceeds_100_percent(self):
        """DO NOT return scope > 1.0."""
        # Even with very high hours
        _, effective = calculate_job_scope(Decimal("500"))
        assert effective == Decimal("1")

        _, effective = calculate_job_scope(Decimal("1000"))
        assert effective == Decimal("1")

    def test_reads_regular_hours_not_recalculates(self):
        """DO NOT recalculate regular hours - use from SSOT."""
        # The module takes regular_hours as input (from SSOT)
        # It doesn't calculate them itself
        ma = MonthAggregate(
            month=(2024, 6),
            total_regular_hours=Decimal("150"),  # Pre-calculated
            total_ot_hours=Decimal("30"),
            total_work_days=22,
            total_shifts=22,
        )

        result = process_month_aggregate(ma)

        # Uses the provided regular hours, not total hours
        assert result.raw_scope == Decimal("150") / Decimal("182")
        # OT hours are not included in scope calculation
        assert result.raw_scope != Decimal("180") / Decimal("182")


class TestEdgeCases:
    """Test edge cases from skill doc."""

    def test_zero_full_time_base(self):
        """Handle zero full-time base (edge case)."""
        raw, effective = calculate_job_scope(
            Decimal("100"),
            full_time_hours_base=Decimal("0"),
        )

        # Avoid division by zero
        assert raw == Decimal("0")
        assert effective == Decimal("0")

    def test_fractional_hours(self):
        """Handle fractional regular hours."""
        raw, effective = calculate_job_scope(Decimal("91.5"))

        expected = Decimal("91.5") / Decimal("182")
        assert raw == expected
        assert effective == expected

    def test_scope_just_at_100_percent(self):
        """Exactly 182 hours = exactly 100%."""
        raw, effective = calculate_job_scope(Decimal("182"))

        assert raw == Decimal("1")
        assert effective == Decimal("1")
        # Not 1.0000001 or 0.9999999
