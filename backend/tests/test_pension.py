"""Tests for pension module.

See docs/skills/pension/SKILL.md for test cases.
"""

import pytest
from datetime import date
from decimal import Decimal

from app.modules.pension import compute_pension, _get_pension_rate, PENSION_RATES
from app.ssot import PeriodMonthRecord, MonthAggregate


class TestGetPensionRate:
    """Tests for _get_pension_rate function."""

    def test_general_rate(self):
        """General industry always uses 6.5%."""
        assert _get_pension_rate("general", 2020, 1) == Decimal("0.065")
        assert _get_pension_rate("general", 2024, 12) == Decimal("0.065")

    def test_agriculture_rate(self):
        """Agriculture industry always uses 6.5%."""
        assert _get_pension_rate("agriculture", 2020, 1) == Decimal("0.065")

    def test_cleaning_rate(self):
        """Cleaning industry always uses 7.5%."""
        assert _get_pension_rate("cleaning", 2020, 1) == Decimal("0.075")
        assert _get_pension_rate("cleaning", 2024, 12) == Decimal("0.075")

    def test_construction_rate_before_july_2018(self):
        """Construction before July 2018 uses 6.0%."""
        assert _get_pension_rate("construction", 2018, 6) == Decimal("0.060")
        assert _get_pension_rate("construction", 2017, 12) == Decimal("0.060")
        assert _get_pension_rate("construction", 2015, 1) == Decimal("0.060")

    def test_construction_rate_from_july_2018(self):
        """Construction from July 2018 uses 7.1%."""
        assert _get_pension_rate("construction", 2018, 7) == Decimal("0.071")
        assert _get_pension_rate("construction", 2024, 12) == Decimal("0.071")

    def test_unknown_industry_falls_back_to_general(self):
        """Unknown industry falls back to general rate."""
        assert _get_pension_rate("unknown", 2020, 1) == Decimal("0.065")


class TestComputePension:
    """Tests for compute_pension function."""

    def test_case1_general_3_years_full_time(self):
        """Case 1: general, 3 years, 10,000₪/month, full time.

        Expected: 36 months × 10,000 × 0.065 × 1.0 = 23,400₪
        """
        # Create 36 months of PMRs
        pmrs = []
        mas = []
        for year in range(2021, 2024):
            for month in range(1, 13):
                pmrs.append(PeriodMonthRecord(
                    effective_period_id="ep1",
                    month=(year, month),
                    salary_monthly=Decimal("10000"),
                ))
                mas.append(MonthAggregate(
                    month=(year, month),
                    job_scope=Decimal("1.0"),
                ))

        result = compute_pension(
            period_month_records=pmrs,
            month_aggregates=mas,
            industry="general",
            right_toggles={},
        )

        assert result.entitled is True
        assert result.industry == "general"
        assert len(result.months) == 36
        assert result.grand_total_value == Decimal("23400")

    def test_case3_toggle_disabled(self):
        """Case 3: toggle disabled → entitled=False."""
        pmrs = [PeriodMonthRecord(
            effective_period_id="ep1",
            month=(2021, 1),
            salary_monthly=Decimal("10000"),
        )]
        mas = [MonthAggregate(month=(2021, 1), job_scope=Decimal("1.0"))]

        result = compute_pension(
            period_month_records=pmrs,
            month_aggregates=mas,
            industry="general",
            right_toggles={"pension": {"enabled": False}},
        )

        assert result.entitled is False
        assert result.grand_total_value == Decimal("0")

    def test_case4_cleaning_partial_scope(self):
        """Case 4: cleaning, job_scope=0.5, salary_monthly=6,000₪.

        Expected: 6,000 × 0.075 × 0.5 = 225₪
        """
        pmrs = [PeriodMonthRecord(
            effective_period_id="ep1",
            month=(2021, 1),
            salary_monthly=Decimal("6000"),
        )]
        mas = [MonthAggregate(month=(2021, 1), job_scope=Decimal("0.5"))]

        result = compute_pension(
            period_month_records=pmrs,
            month_aggregates=mas,
            industry="cleaning",
            right_toggles={},
        )

        assert result.entitled is True
        assert len(result.months) == 1
        assert result.months[0].month_value == Decimal("225")
        assert result.grand_total_value == Decimal("225")

    def test_construction_rate_change_mid_employment(self):
        """Construction rate changes from 6% to 7.1% in July 2018."""
        pmrs = []
        mas = []

        # Add months from Jan 2018 to Dec 2018
        for month in range(1, 13):
            pmrs.append(PeriodMonthRecord(
                effective_period_id="ep1",
                month=(2018, month),
                salary_monthly=Decimal("10000"),
            ))
            mas.append(MonthAggregate(
                month=(2018, month),
                job_scope=Decimal("1.0"),
            ))

        result = compute_pension(
            period_month_records=pmrs,
            month_aggregates=mas,
            industry="construction",
            right_toggles={},
        )

        assert result.entitled is True
        assert len(result.months) == 12

        # First 6 months: 6%
        for i in range(6):
            assert result.months[i].pension_rate == Decimal("0.060")
            assert result.months[i].month_value == Decimal("600")

        # Last 6 months: 7.1%
        for i in range(6, 12):
            assert result.months[i].pension_rate == Decimal("0.071")
            assert result.months[i].month_value == Decimal("710")

        # Total: 6 × 600 + 6 × 710 = 3600 + 4260 = 7860
        assert result.grand_total_value == Decimal("7860")

    def test_multiple_effective_periods_same_month(self):
        """When multiple EPs overlap a month, sum their salary_monthly."""
        pmrs = [
            PeriodMonthRecord(
                effective_period_id="ep1",
                month=(2021, 1),
                salary_monthly=Decimal("5000"),
            ),
            PeriodMonthRecord(
                effective_period_id="ep2",
                month=(2021, 1),
                salary_monthly=Decimal("3000"),
            ),
        ]
        mas = [MonthAggregate(month=(2021, 1), job_scope=Decimal("1.0"))]

        result = compute_pension(
            period_month_records=pmrs,
            month_aggregates=mas,
            industry="general",
            right_toggles={},
        )

        assert len(result.months) == 1
        # Combined salary: 5000 + 3000 = 8000
        # Pension: 8000 × 0.065 × 1.0 = 520
        assert result.months[0].salary_monthly == Decimal("8000")
        assert result.months[0].month_value == Decimal("520")

    def test_no_month_aggregates_defaults_to_full_scope(self):
        """When no matching month_aggregate, default job_scope to 1.0."""
        pmrs = [PeriodMonthRecord(
            effective_period_id="ep1",
            month=(2021, 1),
            salary_monthly=Decimal("10000"),
        )]
        mas = []  # No month aggregates

        result = compute_pension(
            period_month_records=pmrs,
            month_aggregates=mas,
            industry="general",
            right_toggles={},
        )

        assert result.months[0].job_scope == Decimal("1")
        assert result.months[0].month_value == Decimal("650")
