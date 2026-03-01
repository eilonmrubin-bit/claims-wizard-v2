"""Tests for severance pay module.

Test fixtures from docs/skills/severance/SKILL.md
"""

import pytest
from datetime import date
from decimal import Decimal

from app.ssot import (
    TerminationReason,
    SeverancePath,
    Section14Status,
    SeveranceLimitationType,
    LastSalaryMethod,
    PeriodMonthRecord,
    MonthAggregate,
    EffectivePeriod,
    SalaryType,
    NetOrGross,
    Duration,
)
from app.modules.severance import (
    compute_severance,
    load_industry_config,
    IndustryConfig,
)


def make_pmr(
    month: tuple[int, int],
    effective_period_id: str = "ep1",
    salary_monthly: Decimal = Decimal("10000"),
) -> PeriodMonthRecord:
    """Create a PeriodMonthRecord for testing."""
    return PeriodMonthRecord(
        effective_period_id=effective_period_id,
        month=month,
        salary_monthly=salary_monthly,
        salary_daily=salary_monthly / Decimal("22"),
        salary_hourly=salary_monthly / Decimal("182"),
        work_days_count=22,
        shifts_count=22,
    )


def make_month_aggregate(
    month: tuple[int, int],
    job_scope: Decimal = Decimal("1.0"),
) -> MonthAggregate:
    """Create a MonthAggregate for testing."""
    return MonthAggregate(
        month=month,
        job_scope=job_scope,
        raw_scope=job_scope,
    )


def make_effective_period(
    ep_id: str,
    start: date,
    end: date,
) -> EffectivePeriod:
    """Create an EffectivePeriod for testing."""
    return EffectivePeriod(
        id=ep_id,
        start=start,
        end=end,
        employment_period_id="emp1",
        work_pattern_id="wp1",
        salary_tier_id="st1",
        salary_amount=Decimal("10000"),
        salary_type=SalaryType.MONTHLY,
        salary_net_or_gross=NetOrGross.GROSS,
    )


def generate_monthly_data(
    start_date: date,
    end_date: date,
    salary: Decimal = Decimal("10000"),
    job_scope: Decimal = Decimal("1.0"),
    ep_id: str = "ep1",
) -> tuple[list[PeriodMonthRecord], list[MonthAggregate], list[EffectivePeriod]]:
    """Generate PMRs, MAs, and EPs for a date range."""
    pmrs = []
    mas = []

    # Generate months
    current_year = start_date.year
    current_month = start_date.month

    while (current_year, current_month) <= (end_date.year, end_date.month):
        month = (current_year, current_month)
        pmrs.append(make_pmr(month, ep_id, salary))
        mas.append(make_month_aggregate(month, job_scope))

        current_month += 1
        if current_month > 12:
            current_month = 1
            current_year += 1

    eps = [make_effective_period(ep_id, start_date, end_date)]

    return pmrs, mas, eps


class TestFixture1GeneralFiredSection14Holds:
    """Fixture 1: General, fired, Section 14 holds."""

    def test_section_14_holds(self):
        """Test PATH A: Section 14 holds."""
        start = date(2022, 1, 1)
        end = date(2023, 12, 31)
        pmrs, mas, eps = generate_monthly_data(start, end, Decimal("10000"))

        result = compute_severance(
            termination_reason=TerminationReason.FIRED,
            industry="general",
            period_month_records=pmrs,
            month_aggregates=mas,
            effective_periods=eps,
            total_employment_months=Decimal("24"),
            actual_deposits=Decimal("15000"),
        )

        assert result.eligible is True
        assert result.path == SeverancePath.SECTION_14_HOLDS
        assert result.section_14_status == Section14Status.HOLDS
        assert result.limitation_type == SeveranceLimitationType.NONE
        assert result.deduction_override == Decimal("0")

        # full_severance = 10,000 × 0.08333 × 24 = 19,999.20
        expected_full = Decimal("10000") * Decimal("0.08333") * 24
        assert abs(result.full_severance.grand_total - expected_full) < Decimal("1")

        # required_contributions = 10,000 × 0.06 × 24 = 14,400.00
        expected_req = Decimal("10000") * Decimal("0.06") * 24
        assert abs(result.required_contributions.grand_total - expected_req) < Decimal("1")

        # claim = full - required = 19,999.20 - 14,400.00 = 5,599.20
        expected_claim = expected_full - expected_req
        assert abs(result.total_claim - expected_claim) < Decimal("1")


class TestFixture2GeneralFiredSection14Falls:
    """Fixture 2: General, fired, Section 14 falls."""

    def test_section_14_falls(self):
        """Test PATH B: Section 14 falls."""
        start = date(2022, 1, 1)
        end = date(2023, 12, 31)
        pmrs, mas, eps = generate_monthly_data(start, end, Decimal("10000"))

        result = compute_severance(
            termination_reason=TerminationReason.FIRED,
            industry="general",
            period_month_records=pmrs,
            month_aggregates=mas,
            effective_periods=eps,
            total_employment_months=Decimal("24"),
            actual_deposits=Decimal("8000"),
        )

        assert result.eligible is True
        assert result.path == SeverancePath.SECTION_14_FALLS
        assert result.section_14_status == Section14Status.FALLS
        assert result.limitation_type == SeveranceLimitationType.NONE
        assert result.deduction_override is None

        # full_severance = 19,999.20
        expected_full = Decimal("10000") * Decimal("0.08333") * 24
        assert abs(result.full_severance.grand_total - expected_full) < Decimal("1")

        # claim = full_severance = 19,999.20
        assert abs(result.total_claim - expected_full) < Decimal("1")


class TestFixture3GeneralResigned:
    """Fixture 3: General, resigned."""

    def test_resigned_path_c(self):
        """Test PATH C: Resigned."""
        start = date(2022, 1, 1)
        end = date(2023, 12, 31)
        pmrs, mas, eps = generate_monthly_data(start, end, Decimal("10000"))

        result = compute_severance(
            termination_reason=TerminationReason.RESIGNED,
            industry="general",
            period_month_records=pmrs,
            month_aggregates=mas,
            effective_periods=eps,
            total_employment_months=Decimal("24"),
            actual_deposits=Decimal("8000"),
        )

        assert result.eligible is True
        assert result.path == SeverancePath.CONTRIBUTIONS
        assert result.section_14_status is None
        assert result.limitation_type == SeveranceLimitationType.GENERAL
        assert result.deduction_override is None

        # required_contributions = 10,000 × 0.06 × 24 = 14,400.00
        expected_req = Decimal("10000") * Decimal("0.06") * 24
        assert abs(result.required_contributions.grand_total - expected_req) < Decimal("1")

        # claim = required_contributions = 14,400.00
        assert abs(result.total_claim - expected_req) < Decimal("1")


class TestFixture4ConstructionFiredSection14Holds:
    """Fixture 4: Construction, fired, Section 14 holds."""

    def test_construction_zero_claim(self):
        """Test construction where full = required, so claim = 0."""
        start = date(2022, 1, 1)
        end = date(2023, 12, 31)
        pmrs, mas, eps = generate_monthly_data(start, end, Decimal("10000"))

        result = compute_severance(
            termination_reason=TerminationReason.FIRED,
            industry="construction",
            period_month_records=pmrs,
            month_aggregates=mas,
            effective_periods=eps,
            total_employment_months=Decimal("24"),
            actual_deposits=Decimal("20000"),
        )

        assert result.eligible is True
        assert result.path == SeverancePath.SECTION_14_HOLDS
        assert result.section_14_status == Section14Status.HOLDS

        # full_severance = 10,000 × 0.08333 × 24 = 19,999.20
        # required_contributions = 10,000 × 0.08333 × 24 = 19,999.20
        # claim = 19,999.20 - 19,999.20 = 0
        assert abs(result.total_claim) < Decimal("1")


class TestFixture5CleaningFiredWithOT:
    """Fixture 5: Cleaning, fired, with OT, Section 14 falls."""

    def test_cleaning_with_ot(self):
        """Test cleaning industry with OT addition."""
        start = date(2023, 1, 1)
        end = date(2023, 12, 31)
        pmrs, mas, eps = generate_monthly_data(start, end, Decimal("6000"))

        # Note: We don't have shift data in this test, so OT will be 0
        # This tests the structure, not the OT calculation
        result = compute_severance(
            termination_reason=TerminationReason.FIRED,
            industry="cleaning",
            period_month_records=pmrs,
            month_aggregates=mas,
            effective_periods=eps,
            total_employment_months=Decimal("12"),
            actual_deposits=Decimal("5000"),
            shifts=None,  # No shifts, so OT = 0
        )

        assert result.eligible is True
        assert result.path == SeverancePath.SECTION_14_FALLS
        assert result.section_14_status == Section14Status.FALLS
        assert result.ot_addition_rate == Decimal("0.06")
        assert result.recreation_addition_rate == Decimal("0.08333")

        # full_base = 6,000 × 0.08333 × 12 = 5,999.76
        expected_base = Decimal("6000") * Decimal("0.08333") * 12
        assert abs(result.full_severance.base_total - expected_base) < Decimal("1")


class TestFixture6SalaryChangedInLastYear:
    """Fixture 6: Salary changed in last year."""

    def test_salary_changed_uses_average(self):
        """Test that salary change in last 12 months uses average."""
        start = date(2022, 1, 1)
        end = date(2024, 6, 30)

        # For salary to change in last 12 months (Jul 2023 - Jun 2024):
        # Months 1-24 (Jan 2022 - Dec 2023): 8,000
        # Months 25-30 (Jan 2024 - Jun 2024): 10,000
        pmrs = []
        mas = []

        # Jan 2022 - Dec 2023: salary 8,000 (24 months)
        for year in [2022, 2023]:
            for month in range(1, 13):
                m = (year, month)
                pmrs.append(make_pmr(m, "ep1", Decimal("8000")))
                mas.append(make_month_aggregate(m))

        # Jan 2024 - Jun 2024: salary 10,000 (6 months)
        for month in range(1, 7):
            m = (2024, month)
            pmrs.append(make_pmr(m, "ep1", Decimal("10000")))
            mas.append(make_month_aggregate(m))

        eps = [make_effective_period("ep1", start, end)]

        result = compute_severance(
            termination_reason=TerminationReason.FIRED,
            industry="general",
            period_month_records=pmrs,
            month_aggregates=mas,
            effective_periods=eps,
            total_employment_months=Decimal("30"),
            actual_deposits=Decimal("20000"),
        )

        assert result.eligible is True
        assert result.last_salary_info.salary_changed_in_last_year is True
        assert result.last_salary_info.method == LastSalaryMethod.AVG_12_MONTHS

        # last_salary should be avg of last 12 months (Jul 2023 - Jun 2024)
        # 6 months at 8,000 + 6 months at 10,000 = avg 9,000
        assert abs(result.last_salary_info.last_salary - Decimal("9000")) < Decimal("1")


class TestFixture7Ineligible:
    """Fixture 7: Ineligible (less than minimum months)."""

    def test_ineligible_general(self):
        """Test ineligibility due to insufficient employment."""
        start = date(2024, 1, 1)
        end = date(2024, 10, 31)
        pmrs, mas, eps = generate_monthly_data(start, end, Decimal("10000"))

        result = compute_severance(
            termination_reason=TerminationReason.FIRED,
            industry="general",
            period_month_records=pmrs,
            month_aggregates=mas,
            effective_periods=eps,
            total_employment_months=Decimal("10"),  # < 12 months for general
            actual_deposits=Decimal("5000"),
        )

        assert result.eligible is False
        assert result.ineligible_reason == "לא השלים את תקופת העבודה המינימלית"


class TestFixture8ConstructionShortEmployment:
    """Fixture 8: Construction, short employment, still eligible."""

    def test_construction_eligible_from_day_one(self):
        """Test construction eligibility from day one (min_months = 0)."""
        start = date(2024, 1, 1)
        end = date(2024, 3, 31)
        pmrs, mas, eps = generate_monthly_data(start, end, Decimal("10000"))

        result = compute_severance(
            termination_reason=TerminationReason.FIRED,
            industry="construction",
            period_month_records=pmrs,
            month_aggregates=mas,
            effective_periods=eps,
            total_employment_months=Decimal("3"),
            actual_deposits=Decimal("2500"),
        )

        assert result.eligible is True
        assert result.path == SeverancePath.SECTION_14_HOLDS

        # full_severance = 10,000 × 0.08333 × 3 = 2,499.90
        # required_contributions = 10,000 × 0.08333 × 3 = 2,499.90
        # claim = 0
        assert abs(result.total_claim) < Decimal("1")


class TestLoadIndustryConfig:
    """Test industry config loading."""

    def test_load_config(self):
        """Test that industry configs load correctly."""
        configs = load_industry_config()

        assert "general" in configs
        assert "construction" in configs
        assert "cleaning" in configs
        assert "agriculture" in configs

        assert configs["general"].severance_rate == Decimal("0.08333")
        assert configs["general"].contribution_rate == Decimal("0.06")
        assert configs["general"].min_months == 12

        assert configs["construction"].contribution_rate == Decimal("0.08333")
        assert configs["construction"].min_months == 0

        assert configs["cleaning"].ot_addition is True
        assert configs["cleaning"].ot_addition_rate == Decimal("0.06")


class TestResignedAsFired:
    """Test resigned_as_fired behaves like fired."""

    def test_resigned_as_fired_path_a(self):
        """Test that resigned_as_fired follows PATH A when deposits >= required."""
        start = date(2022, 1, 1)
        end = date(2023, 12, 31)
        pmrs, mas, eps = generate_monthly_data(start, end, Decimal("10000"))

        result = compute_severance(
            termination_reason=TerminationReason.RESIGNED_AS_FIRED,
            industry="general",
            period_month_records=pmrs,
            month_aggregates=mas,
            effective_periods=eps,
            total_employment_months=Decimal("24"),
            actual_deposits=Decimal("15000"),
        )

        assert result.eligible is True
        assert result.path == SeverancePath.SECTION_14_HOLDS
        assert result.section_14_status == Section14Status.HOLDS


class TestMonthlyBreakdown:
    """Test monthly breakdown generation."""

    def test_monthly_breakdown_path_a(self):
        """Test that monthly breakdown is generated for PATH A."""
        start = date(2023, 1, 1)
        end = date(2023, 12, 31)
        pmrs, mas, eps = generate_monthly_data(start, end, Decimal("10000"))

        result = compute_severance(
            termination_reason=TerminationReason.FIRED,
            industry="general",
            period_month_records=pmrs,
            month_aggregates=mas,
            effective_periods=eps,
            total_employment_months=Decimal("12"),
            actual_deposits=Decimal("8000"),
        )

        assert len(result.monthly_breakdown) == 12
        # Each month should have a claim_amount
        for mb in result.monthly_breakdown:
            assert mb.month is not None
            assert mb.claim_amount is not None


class TestDeductionOverride:
    """Test deduction_override behavior."""

    def test_path_a_deduction_override_zero(self):
        """Test that PATH A sets deduction_override to 0."""
        start = date(2022, 1, 1)
        end = date(2023, 12, 31)
        pmrs, mas, eps = generate_monthly_data(start, end, Decimal("10000"))

        result = compute_severance(
            termination_reason=TerminationReason.FIRED,
            industry="general",
            period_month_records=pmrs,
            month_aggregates=mas,
            effective_periods=eps,
            total_employment_months=Decimal("24"),
            actual_deposits=Decimal("15000"),
        )

        assert result.path == SeverancePath.SECTION_14_HOLDS
        assert result.deduction_override == Decimal("0")

    def test_path_b_no_deduction_override(self):
        """Test that PATH B has no deduction_override (None)."""
        start = date(2022, 1, 1)
        end = date(2023, 12, 31)
        pmrs, mas, eps = generate_monthly_data(start, end, Decimal("10000"))

        result = compute_severance(
            termination_reason=TerminationReason.FIRED,
            industry="general",
            period_month_records=pmrs,
            month_aggregates=mas,
            effective_periods=eps,
            total_employment_months=Decimal("24"),
            actual_deposits=Decimal("8000"),
        )

        assert result.path == SeverancePath.SECTION_14_FALLS
        assert result.deduction_override is None

    def test_path_c_no_deduction_override(self):
        """Test that PATH C has no deduction_override (None)."""
        start = date(2022, 1, 1)
        end = date(2023, 12, 31)
        pmrs, mas, eps = generate_monthly_data(start, end, Decimal("10000"))

        result = compute_severance(
            termination_reason=TerminationReason.RESIGNED,
            industry="general",
            period_month_records=pmrs,
            month_aggregates=mas,
            effective_periods=eps,
            total_employment_months=Decimal("24"),
            actual_deposits=Decimal("8000"),
        )

        assert result.path == SeverancePath.CONTRIBUTIONS
        assert result.deduction_override is None
