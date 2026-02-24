"""Tests for overtime stage 8: pricing.

Test cases from docs/skills/overtime-calculation/SKILL.md.
"""

import pytest
from datetime import date
from decimal import Decimal

from app.modules.overtime.stage8_pricing import (
    price_shift,
    run_pricing,
    calculate_monthly_totals,
    calculate_grand_total,
    RATE_MULTIPLIERS,
    CLAIM_MULTIPLIERS_FULL,
    CLAIM_MULTIPLIERS_NO_REST,
)
from app.ssot import Shift, PeriodMonthRecord


def create_shift(
    shift_id: str,
    effective_period_id: str,
    assigned_day: date,
    # Regular hours (not in rest window)
    non_rest_regular: Decimal = Decimal("0"),
    non_rest_tier1: Decimal = Decimal("0"),
    non_rest_tier2: Decimal = Decimal("0"),
    # Rest window hours
    rest_regular: Decimal = Decimal("0"),
    rest_tier1: Decimal = Decimal("0"),
    rest_tier2: Decimal = Decimal("0"),
) -> Shift:
    """Create a shift with rest window breakdown."""
    return Shift(
        id=shift_id,
        date=assigned_day,
        effective_period_id=effective_period_id,
        assigned_day=assigned_day,
        # Stage 7 outputs
        non_rest_regular_hours=non_rest_regular,
        non_rest_ot_tier1_hours=non_rest_tier1,
        non_rest_ot_tier2_hours=non_rest_tier2,
        rest_window_regular_hours=rest_regular,
        rest_window_ot_tier1_hours=rest_tier1,
        rest_window_ot_tier2_hours=rest_tier2,
        # Also set the totals for consistency
        regular_hours=non_rest_regular + rest_regular,
        ot_tier1_hours=non_rest_tier1 + rest_tier1,
        ot_tier2_hours=non_rest_tier2 + rest_tier2,
    )


class TestRateMultipliers:
    """Test that rate multipliers are correct per the skill doc."""

    def test_regular_day_rates(self):
        """Regular day rates: 100%, 125%, 150%."""
        assert RATE_MULTIPLIERS[(0, False)] == Decimal("1.00")
        assert RATE_MULTIPLIERS[(1, False)] == Decimal("1.25")
        assert RATE_MULTIPLIERS[(2, False)] == Decimal("1.50")

    def test_rest_day_rates(self):
        """Rest day rates: 150%, 175%, 200%."""
        assert RATE_MULTIPLIERS[(0, True)] == Decimal("1.50")
        assert RATE_MULTIPLIERS[(1, True)] == Decimal("1.75")
        assert RATE_MULTIPLIERS[(2, True)] == Decimal("2.00")


class TestClaimMultipliers:
    """Test that claim multipliers are correct per the skill doc."""

    def test_regular_day_claim_full(self):
        """Regular day claims: 0%, 25%, 50%."""
        assert CLAIM_MULTIPLIERS_FULL[(0, False)] == Decimal("0.00")
        assert CLAIM_MULTIPLIERS_FULL[(1, False)] == Decimal("0.25")
        assert CLAIM_MULTIPLIERS_FULL[(2, False)] == Decimal("0.50")

    def test_rest_day_claim_full(self):
        """Rest day claims (full): 50%, 75%, 100%."""
        assert CLAIM_MULTIPLIERS_FULL[(0, True)] == Decimal("0.50")
        assert CLAIM_MULTIPLIERS_FULL[(1, True)] == Decimal("0.75")
        assert CLAIM_MULTIPLIERS_FULL[(2, True)] == Decimal("1.00")

    def test_rest_day_claim_no_rest_premium(self):
        """Rest day claims when employer paid rest premium: 0%, 25%, 50%."""
        assert CLAIM_MULTIPLIERS_NO_REST[(0, True)] == Decimal("0.00")
        assert CLAIM_MULTIPLIERS_NO_REST[(1, True)] == Decimal("0.25")
        assert CLAIM_MULTIPLIERS_NO_REST[(2, True)] == Decimal("0.50")


class TestPriceShift:
    """Test pricing of individual shifts."""

    def test_regular_hours_no_claim(self):
        """Regular hours on regular day = no claim (base pay only)."""
        shift = create_shift(
            "s1", "ep1", date(2024, 6, 3),
            non_rest_regular=Decimal("8"),
        )

        result = price_shift(shift, hourly_wage=Decimal("50"))

        assert result.claim_amount == Decimal("0")
        assert len(result.breakdown) == 1
        assert result.breakdown[0].tier == 0
        assert result.breakdown[0].in_rest is False
        assert result.breakdown[0].claim_multiplier == Decimal("0")

    def test_tier1_overtime_regular_day(self):
        """Tier 1 overtime on regular day = 25% claim."""
        shift = create_shift(
            "s1", "ep1", date(2024, 6, 3),
            non_rest_regular=Decimal("8"),
            non_rest_tier1=Decimal("2"),
        )

        result = price_shift(shift, hourly_wage=Decimal("50"))

        # Only tier1 generates claim: 2h × 50 × 0.25 = 25
        assert result.claim_amount == Decimal("25")

    def test_tier2_overtime_regular_day(self):
        """Tier 2 overtime on regular day = 50% claim."""
        shift = create_shift(
            "s1", "ep1", date(2024, 6, 3),
            non_rest_regular=Decimal("8"),
            non_rest_tier1=Decimal("2"),
            non_rest_tier2=Decimal("1"),
        )

        result = price_shift(shift, hourly_wage=Decimal("50"))

        # Tier1: 2 × 50 × 0.25 = 25
        # Tier2: 1 × 50 × 0.50 = 25
        # Total: 50
        assert result.claim_amount == Decimal("50")

    def test_regular_hours_rest_day(self):
        """Regular hours in rest window = 50% claim."""
        shift = create_shift(
            "s1", "ep1", date(2024, 6, 1),
            rest_regular=Decimal("8"),
        )

        result = price_shift(shift, hourly_wage=Decimal("50"))

        # 8h × 50 × 0.50 = 200
        assert result.claim_amount == Decimal("200")

    def test_tier1_overtime_rest_day(self):
        """Tier 1 overtime in rest window = 75% claim."""
        shift = create_shift(
            "s1", "ep1", date(2024, 6, 1),
            rest_regular=Decimal("7"),
            rest_tier1=Decimal("2"),
        )

        result = price_shift(shift, hourly_wage=Decimal("50"))

        # Regular: 7 × 50 × 0.50 = 175
        # Tier1: 2 × 50 × 0.75 = 75
        # Total: 250
        assert result.claim_amount == Decimal("250")

    def test_tier2_overtime_rest_day(self):
        """Tier 2 overtime in rest window = 100% claim."""
        shift = create_shift(
            "s1", "ep1", date(2024, 6, 1),
            rest_regular=Decimal("7"),
            rest_tier1=Decimal("2"),
            rest_tier2=Decimal("1"),
        )

        result = price_shift(shift, hourly_wage=Decimal("50"))

        # Regular: 7 × 50 × 0.50 = 175
        # Tier1: 2 × 50 × 0.75 = 75
        # Tier2: 1 × 50 × 1.00 = 50
        # Total: 300
        assert result.claim_amount == Decimal("300")

    def test_mixed_rest_and_regular(self):
        """Shift crossing rest window boundary - mixed rates."""
        shift = create_shift(
            "s1", "ep1", date(2024, 5, 31),
            # 4 hours outside rest window
            non_rest_regular=Decimal("4"),
            non_rest_tier1=Decimal("1"),
            # 4 hours inside rest window
            rest_regular=Decimal("3"),
            rest_tier1=Decimal("1"),
        )

        result = price_shift(shift, hourly_wage=Decimal("40"))

        # Non-rest regular: 4 × 40 × 0.00 = 0
        # Non-rest tier1: 1 × 40 × 0.25 = 10
        # Rest regular: 3 × 40 × 0.50 = 60
        # Rest tier1: 1 × 40 × 0.75 = 30
        # Total: 100
        assert result.claim_amount == Decimal("100")

    def test_employer_paid_rest_premium(self):
        """When employer paid rest premium, rest window = 0% for regular."""
        shift = create_shift(
            "s1", "ep1", date(2024, 6, 1),
            rest_regular=Decimal("7"),
            rest_tier1=Decimal("2"),
        )

        result = price_shift(
            shift,
            hourly_wage=Decimal("50"),
            employer_paid_rest_premium=True,
        )

        # Regular: 7 × 50 × 0.00 = 0 (not 0.50)
        # Tier1: 2 × 50 × 0.25 = 25 (not 0.75)
        # Total: 25
        assert result.claim_amount == Decimal("25")

    def test_breakdown_contains_all_segments(self):
        """Breakdown includes all non-zero hour segments."""
        shift = create_shift(
            "s1", "ep1", date(2024, 5, 31),
            non_rest_regular=Decimal("4"),
            non_rest_tier1=Decimal("1"),
            non_rest_tier2=Decimal("0.5"),
            rest_regular=Decimal("2"),
            rest_tier1=Decimal("0.5"),
        )

        result = price_shift(shift, hourly_wage=Decimal("40"))

        # Should have 5 segments (all non-zero)
        assert len(result.breakdown) == 5

        # Verify each segment has correct metadata
        for segment in result.breakdown:
            assert segment.hourly_wage == Decimal("40")
            assert segment.hours > 0
            assert segment.tier in [0, 1, 2]


class TestRunPricing:
    """Test pricing of multiple shifts."""

    def test_run_pricing_multiple_shifts(self):
        """Run pricing on multiple shifts."""
        shifts = [
            create_shift(
                "s1", "ep1", date(2024, 6, 3),
                non_rest_regular=Decimal("8"),
                non_rest_tier1=Decimal("2"),
            ),
            create_shift(
                "s2", "ep1", date(2024, 6, 4),
                non_rest_regular=Decimal("8"),
                non_rest_tier1=Decimal("1"),
            ),
        ]

        pmr = {
            ("ep1", (2024, 6)): PeriodMonthRecord(
                effective_period_id="ep1",
                month=(2024, 6),
                salary_hourly=Decimal("50"),
            ),
        }

        result = run_pricing(shifts, pmr)

        # Shift 1: 2h × 50 × 0.25 = 25
        assert result[0].claim_amount == Decimal("25")
        # Shift 2: 1h × 50 × 0.25 = 12.5
        assert result[1].claim_amount == Decimal("12.5")

    def test_different_periods_different_wages(self):
        """Different periods have different hourly wages."""
        shifts = [
            create_shift(
                "s1", "ep1", date(2024, 6, 3),
                non_rest_tier1=Decimal("2"),
            ),
            create_shift(
                "s2", "ep2", date(2024, 6, 4),
                non_rest_tier1=Decimal("2"),
            ),
        ]

        pmr = {
            ("ep1", (2024, 6)): PeriodMonthRecord(
                effective_period_id="ep1",
                month=(2024, 6),
                salary_hourly=Decimal("40"),
            ),
            ("ep2", (2024, 6)): PeriodMonthRecord(
                effective_period_id="ep2",
                month=(2024, 6),
                salary_hourly=Decimal("60"),
            ),
        }

        result = run_pricing(shifts, pmr)

        # Shift 1: 2h × 40 × 0.25 = 20
        assert result[0].claim_amount == Decimal("20")
        # Shift 2: 2h × 60 × 0.25 = 30
        assert result[1].claim_amount == Decimal("30")


class TestMonthlyTotals:
    """Test monthly total calculation."""

    def test_calculate_monthly_totals(self):
        """Calculate totals per month."""
        shifts = [
            create_shift("s1", "ep1", date(2024, 5, 15)),
            create_shift("s2", "ep1", date(2024, 5, 16)),
            create_shift("s3", "ep1", date(2024, 6, 1)),
        ]
        shifts[0].claim_amount = Decimal("100")
        shifts[1].claim_amount = Decimal("150")
        shifts[2].claim_amount = Decimal("200")

        totals = calculate_monthly_totals(shifts)

        assert totals[(2024, 5)] == Decimal("250")
        assert totals[(2024, 6)] == Decimal("200")

    def test_grand_total(self):
        """Calculate grand total across all shifts."""
        shifts = [
            create_shift("s1", "ep1", date(2024, 5, 15)),
            create_shift("s2", "ep1", date(2024, 6, 1)),
        ]
        shifts[0].claim_amount = Decimal("100")
        shifts[1].claim_amount = Decimal("200")

        total = calculate_grand_total(shifts)

        assert total == Decimal("300")


class TestEdgeCases:
    """Test edge cases."""

    def test_zero_hours(self):
        """Shift with zero hours = zero claim."""
        shift = create_shift("s1", "ep1", date(2024, 6, 3))

        result = price_shift(shift, hourly_wage=Decimal("50"))

        assert result.claim_amount == Decimal("0")
        assert len(result.breakdown) == 0

    def test_missing_period_month_record(self):
        """Missing period_month_record = zero hourly wage."""
        shift = create_shift(
            "s1", "ep1", date(2024, 6, 3),
            non_rest_tier1=Decimal("2"),
        )

        # Empty period_month_records
        result = run_pricing([shift], {})

        # No wage = no claim
        assert result[0].claim_amount == Decimal("0")

    def test_fractional_hours(self):
        """Fractional hours are priced correctly."""
        shift = create_shift(
            "s1", "ep1", date(2024, 6, 3),
            non_rest_tier1=Decimal("1.5"),
        )

        result = price_shift(shift, hourly_wage=Decimal("40"))

        # 1.5h × 40 × 0.25 = 15
        assert result.claim_amount == Decimal("15")

    def test_very_small_hours(self):
        """Very small hour fractions are handled."""
        shift = create_shift(
            "s1", "ep1", date(2024, 6, 3),
            non_rest_tier2=Decimal("0.1"),
        )

        result = price_shift(shift, hourly_wage=Decimal("50"))

        # 0.1h × 50 × 0.50 = 2.5
        assert result.claim_amount == Decimal("2.5")


class TestIntegrationScenarios:
    """Integration test scenarios from skill doc."""

    def test_case_7_rest_window_cross_boundary(self):
        """Case 7: Shift crossing rest window boundary.

        Shift 14:00-22:00, rest window starts at 16:30.
        2.5h regular-day rates, 5.5h rest-day rates.
        """
        # Threshold 7.0 (eve of rest), so 7h regular, 1h tier1
        # Split: 2.5h before rest window, 5.5h in rest window
        # Regular hours: 2.5h non-rest + 4.5h rest = 7h
        # Tier1: 0h non-rest + 1h rest
        shift = create_shift(
            "s1", "ep1", date(2024, 5, 31),
            non_rest_regular=Decimal("2.5"),
            rest_regular=Decimal("4.5"),
            rest_tier1=Decimal("1"),
        )

        result = price_shift(shift, hourly_wage=Decimal("40"))

        # Non-rest regular: 2.5 × 40 × 0.00 = 0
        # Rest regular: 4.5 × 40 × 0.50 = 90
        # Rest tier1: 1 × 40 × 0.75 = 30
        # Total: 120
        assert result.claim_amount == Decimal("120")

    def test_full_rest_day_shift_with_ot(self):
        """Full shift inside rest window with overtime."""
        # 10 hour shift, threshold 7.0
        # 7h regular, 2h tier1, 1h tier2
        shift = create_shift(
            "s1", "ep1", date(2024, 6, 1),
            rest_regular=Decimal("7"),
            rest_tier1=Decimal("2"),
            rest_tier2=Decimal("1"),
        )

        result = price_shift(shift, hourly_wage=Decimal("45"))

        # Regular: 7 × 45 × 0.50 = 157.5
        # Tier1: 2 × 45 × 0.75 = 67.5
        # Tier2: 1 × 45 × 1.00 = 45
        # Total: 270
        assert result.claim_amount == Decimal("270")


class TestNoRounding:
    """Test that no rounding occurs - per skill requirement."""

    def test_no_rounding_in_claim(self):
        """Claim amounts are not rounded."""
        shift = create_shift(
            "s1", "ep1", date(2024, 6, 3),
            non_rest_tier1=Decimal("1.333"),
        )

        result = price_shift(shift, hourly_wage=Decimal("47"))

        # 1.333 × 47 × 0.25 = 15.66275
        expected = Decimal("1.333") * Decimal("47") * Decimal("0.25")
        assert result.claim_amount == expected

    def test_breakdown_preserves_precision(self):
        """Breakdown preserves full decimal precision."""
        shift = create_shift(
            "s1", "ep1", date(2024, 6, 3),
            non_rest_tier1=Decimal("1.777"),
        )

        result = price_shift(shift, hourly_wage=Decimal("33.33"))

        # Verify hours preserved exactly
        assert result.breakdown[0].hours == Decimal("1.777")
        assert result.breakdown[0].hourly_wage == Decimal("33.33")
