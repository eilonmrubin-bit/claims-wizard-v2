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
    Shift,
    PricingBreakdown,
)
from app.modules.severance import (
    compute_severance,
    load_industry_config,
    IndustryConfig,
)
from datetime import datetime


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


def make_shift_with_ot(
    shift_date: date,
    tier1_hours: Decimal,
    tier2_hours: Decimal,
    hourly_wage: Decimal,
) -> Shift:
    """Create a shift with OT pricing breakdown for testing."""
    pricing = []
    if tier1_hours > 0:
        pricing.append(PricingBreakdown(
            hours=tier1_hours,
            tier=1,
            rate_multiplier=Decimal("1.25"),
            hourly_wage=hourly_wage,
            claim_amount=tier1_hours * Decimal("0.25") * hourly_wage,
        ))
    if tier2_hours > 0:
        pricing.append(PricingBreakdown(
            hours=tier2_hours,
            tier=2,
            rate_multiplier=Decimal("1.50"),
            hourly_wage=hourly_wage,
            claim_amount=tier2_hours * Decimal("0.50") * hourly_wage,
        ))

    return Shift(
        id=f"shift_{shift_date.isoformat()}",
        date=shift_date,
        assigned_day=shift_date,
        pricing_breakdown=pricing,
    )


class TestFixture5CleaningFiredWithOT:
    """Fixture 5: Cleaning, fired, with OT, Section 14 falls."""

    def test_cleaning_with_ot(self):
        """Test cleaning industry with OT addition - full calculation."""
        start = date(2023, 1, 1)
        end = date(2023, 12, 31)
        pmrs, mas, eps = generate_monthly_data(start, end, Decimal("6000"))

        # Create shifts with OT for each month
        # Per fixture: 20 hours tier1 at 1.25 × 35/hr + 5 hours tier2 at 1.50 × 35/hr
        # full_ot_monthly_pay = (20 × 1.25 × 35) + (5 × 1.50 × 35) = 875 + 262.50 = 1,137.50
        shifts = []
        hourly_wage = Decimal("35")
        for month in range(1, 13):
            # Create one shift per month with the specified OT
            shift_date = date(2023, month, 15)
            shifts.append(make_shift_with_ot(
                shift_date=shift_date,
                tier1_hours=Decimal("20"),
                tier2_hours=Decimal("5"),
                hourly_wage=hourly_wage,
            ))

        result = compute_severance(
            termination_reason=TerminationReason.FIRED,
            industry="cleaning",
            period_month_records=pmrs,
            month_aggregates=mas,
            effective_periods=eps,
            total_employment_months=Decimal("12"),
            actual_deposits=Decimal("5000"),
            shifts=shifts,
        )

        assert result.eligible is True
        assert result.path == SeverancePath.SECTION_14_FALLS
        assert result.section_14_status == Section14Status.FALLS
        assert result.ot_addition_rate == Decimal("0.06")
        assert result.recreation_addition_rate == Decimal("0.08333")

        # full_base = 6,000 × 0.08333 × 12 = 5,999.76
        expected_base = Decimal("6000") * Decimal("0.08333") * 12
        assert abs(result.full_severance.base_total - expected_base) < Decimal("1")

        # OT addition: 1,137.50 × 0.06 × 12 = 819.00
        # full_ot_monthly = (20 × 1.25 × 35) + (5 × 1.50 × 35) = 1137.50
        expected_full_ot_monthly = (Decimal("20") * Decimal("1.25") * hourly_wage +
                                    Decimal("5") * Decimal("1.50") * hourly_wage)
        assert abs(expected_full_ot_monthly - Decimal("1137.50")) < Decimal("0.01")

        expected_ot_total = expected_full_ot_monthly * Decimal("0.06") * 12
        assert abs(result.ot_addition.total - expected_ot_total) < Decimal("1")
        assert abs(result.full_severance.ot_total - expected_ot_total) < Decimal("1")

        # total_claim = base 5,999.76 + OT 819.00 = 6,818.76
        expected_total = expected_base + expected_ot_total
        assert abs(result.total_claim - expected_total) < Decimal("1")

    def test_cleaning_structure_without_shifts(self):
        """Test cleaning industry structure without shift data."""
        start = date(2023, 1, 1)
        end = date(2023, 12, 31)
        pmrs, mas, eps = generate_monthly_data(start, end, Decimal("6000"))

        result = compute_severance(
            termination_reason=TerminationReason.FIRED,
            industry="cleaning",
            period_month_records=pmrs,
            month_aggregates=mas,
            effective_periods=eps,
            total_employment_months=Decimal("12"),
            actual_deposits=Decimal("5000"),
            shifts=None,
        )

        assert result.eligible is True
        assert result.ot_addition_rate == Decimal("0.06")
        assert result.recreation_addition_rate == Decimal("0.08333")
        # No shifts means OT total is 0
        assert result.full_severance.ot_total == Decimal("0")


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


class TestPartialMonths:
    """Test 4a: Partial months are correctly calculated."""

    def test_partial_months_calculation(self):
        """Worker started Jan 15 and ended Mar 10 — partial fractions."""
        start = date(2024, 1, 15)
        end = date(2024, 3, 10)

        # January: 15-31 = 17 days out of 31 → 17/31
        # February: full month = 29 days (2024 is leap year) → 29/29 = 1.0
        # March: 1-10 = 10 days out of 31 → 10/31

        pmrs = [
            make_pmr((2024, 1), "ep1", Decimal("10000")),
            make_pmr((2024, 2), "ep1", Decimal("10000")),
            make_pmr((2024, 3), "ep1", Decimal("10000")),
        ]
        mas = [
            make_month_aggregate((2024, 1)),
            make_month_aggregate((2024, 2)),
            make_month_aggregate((2024, 3)),
        ]
        eps = [make_effective_period("ep1", start, end)]

        result = compute_severance(
            termination_reason=TerminationReason.FIRED,
            industry="construction",  # min_months = 0
            period_month_records=pmrs,
            month_aggregates=mas,
            effective_periods=eps,
            total_employment_months=Decimal("2"),
            actual_deposits=Decimal("2000"),
        )

        assert result.eligible is True

        # Check monthly details have correct partial_fractions
        jan_detail = next(d for d in result.full_severance.base_monthly_detail if d.month == (2024, 1))
        feb_detail = next(d for d in result.full_severance.base_monthly_detail if d.month == (2024, 2))
        mar_detail = next(d for d in result.full_severance.base_monthly_detail if d.month == (2024, 3))

        assert jan_detail.calendar_days_employed == 17
        assert jan_detail.total_calendar_days == 31
        assert abs(jan_detail.partial_fraction - Decimal("17") / Decimal("31")) < Decimal("0.001")

        assert feb_detail.calendar_days_employed == 29
        assert feb_detail.total_calendar_days == 29
        assert abs(feb_detail.partial_fraction - Decimal("1")) < Decimal("0.001")

        assert mar_detail.calendar_days_employed == 10
        assert mar_detail.total_calendar_days == 31
        assert abs(mar_detail.partial_fraction - Decimal("10") / Decimal("31")) < Decimal("0.001")

        # Period summary months_count should be count of calendar months
        summary = result.full_severance.period_summaries[0]
        assert summary.months_count == 3


class TestVaryingJobScope:
    """Test 4b: Varying job scope is calculated per month."""

    def test_varying_job_scope(self):
        """Job scope 0.5 for first 6 months, 1.0 for last 6 months."""
        start = date(2023, 1, 1)
        end = date(2023, 12, 31)

        pmrs = []
        mas = []

        # First 6 months: job_scope = 0.5
        for month in range(1, 7):
            pmrs.append(make_pmr((2023, month), "ep1", Decimal("10000")))
            mas.append(make_month_aggregate((2023, month), Decimal("0.5")))

        # Last 6 months: job_scope = 1.0
        for month in range(7, 13):
            pmrs.append(make_pmr((2023, month), "ep1", Decimal("10000")))
            mas.append(make_month_aggregate((2023, month), Decimal("1.0")))

        eps = [make_effective_period("ep1", start, end)]

        result = compute_severance(
            termination_reason=TerminationReason.FIRED,
            industry="general",
            period_month_records=pmrs,
            month_aggregates=mas,
            effective_periods=eps,
            total_employment_months=Decimal("12"),
            actual_deposits=Decimal("10000"),
        )

        assert result.eligible is True

        # Check that each month used correct job_scope
        for detail in result.full_severance.base_monthly_detail:
            month_num = detail.month[1]
            if month_num <= 6:
                assert detail.job_scope == Decimal("0.5")
            else:
                assert detail.job_scope == Decimal("1.0")

        # Full severance should be:
        # 6 months × 10,000 × 0.08333 × 0.5 + 6 months × 10,000 × 0.08333 × 1.0
        # = 6 × 833.30 × 0.5 + 6 × 833.30 × 1.0
        # = 2,499.90 + 4,999.80 = 7,499.70
        expected = Decimal("10000") * Decimal("0.08333") * 6 * Decimal("0.5") + \
                   Decimal("10000") * Decimal("0.08333") * 6 * Decimal("1.0")
        assert abs(result.full_severance.base_total - expected) < Decimal("1")


class TestTwoEffectivePeriodsWithDifferentSalaries:
    """Test 4c: Two effective periods with different salaries."""

    def test_two_eps_different_salaries(self):
        """EP1: 12 months at 8,000. EP2: 12 months at 10,000."""
        ep1_start = date(2022, 1, 1)
        ep1_end = date(2022, 12, 31)
        ep2_start = date(2023, 1, 1)
        ep2_end = date(2023, 12, 31)

        pmrs = []
        mas = []

        # EP1: 2022, salary 8,000
        for month in range(1, 13):
            pmrs.append(make_pmr((2022, month), "ep1", Decimal("8000")))
            mas.append(make_month_aggregate((2022, month)))

        # EP2: 2023, salary 10,000
        for month in range(1, 13):
            pmrs.append(make_pmr((2023, month), "ep2", Decimal("10000")))
            mas.append(make_month_aggregate((2023, month)))

        eps = [
            make_effective_period("ep1", ep1_start, ep1_end),
            make_effective_period("ep2", ep2_start, ep2_end),
        ]

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

        # Last salary should be 10,000 (no change in last 12 months)
        assert result.last_salary_info.last_salary == Decimal("10000")
        assert result.last_salary_info.salary_changed_in_last_year is False

        # Full severance uses last_salary for ALL months
        for detail in result.full_severance.base_monthly_detail:
            assert detail.salary_used == Decimal("10000")

        # Required contributions uses actual salary_monthly of each month
        for detail in result.required_contributions.base_monthly_detail:
            year = detail.month[0]
            if year == 2022:
                assert detail.salary_used == Decimal("8000")
            else:
                assert detail.salary_used == Decimal("10000")

        # Period summaries should be split correctly
        assert len(result.full_severance.period_summaries) == 2
        assert len(result.required_contributions.period_summaries) == 2

        ep1_full_summary = next(s for s in result.full_severance.period_summaries if s.effective_period_id == "ep1")
        ep2_full_summary = next(s for s in result.full_severance.period_summaries if s.effective_period_id == "ep2")

        assert ep1_full_summary.months_count == 12
        assert ep2_full_summary.months_count == 12


class TestPathCWithSalaryChange:
    """Test 4d: PATH C (resigned) with salary change."""

    def test_resigned_uses_actual_salary_per_month(self):
        """Resigned: required_contributions uses salary_monthly per month, not last_salary."""
        start = date(2022, 1, 1)
        end = date(2023, 12, 31)

        pmrs = []
        mas = []

        # First 12 months: salary 8,000
        for month in range(1, 13):
            pmrs.append(make_pmr((2022, month), "ep1", Decimal("8000")))
            mas.append(make_month_aggregate((2022, month)))

        # Last 12 months: salary 10,000
        for month in range(1, 13):
            pmrs.append(make_pmr((2023, month), "ep1", Decimal("10000")))
            mas.append(make_month_aggregate((2023, month)))

        eps = [make_effective_period("ep1", start, end)]

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

        # Required contributions should use actual salary per month
        # 12 months × 8,000 × 0.06 + 12 months × 10,000 × 0.06
        # = 5,760 + 7,200 = 12,960
        expected_req = Decimal("8000") * Decimal("0.06") * 12 + Decimal("10000") * Decimal("0.06") * 12
        assert abs(result.required_contributions.base_total - expected_req) < Decimal("1")

        # Claim = required_contributions
        assert abs(result.total_claim - expected_req) < Decimal("1")

        # Verify each month uses correct salary
        for detail in result.required_contributions.base_monthly_detail:
            year = detail.month[0]
            if year == 2022:
                assert detail.salary_used == Decimal("8000")
            else:
                assert detail.salary_used == Decimal("10000")


class TestFixture10PartialMonthsExcludedFromLastSalary:
    """Fixture 10: Partial first and last months excluded from last salary average."""

    def test_partial_months_excluded(self):
        """Test that partial first/last months are excluded from last salary determination."""
        # Employment: 2023-06-15 to 2024-06-14
        # 2023-06: partial (starts 15 Jun) → excluded
        # 2024-06: partial (ends 14 Jun) → excluded
        # 2023-07 to 2024-05: 11 full months, salary 8,000
        start = date(2023, 6, 15)
        end = date(2024, 6, 14)

        pmrs = []
        mas = []

        # All months from Jun 2023 to Jun 2024 with salary 8,000
        year = 2023
        month = 6
        while (year, month) <= (2024, 6):
            pmrs.append(make_pmr((year, month), "ep1", Decimal("8000")))
            mas.append(make_month_aggregate((year, month)))
            month += 1
            if month > 12:
                month = 1
                year += 1

        eps = [make_effective_period("ep1", start, end)]

        result = compute_severance(
            termination_reason=TerminationReason.FIRED,
            industry="general",
            period_month_records=pmrs,
            month_aggregates=mas,
            effective_periods=eps,
            total_employment_months=Decimal("12"),
            actual_deposits=Decimal("5000"),
        )

        assert result.eligible is True
        # Last salary should be 8,000 from last full month (2024-05)
        assert result.last_salary_info.last_salary == Decimal("8000")
        assert result.last_salary_info.method == LastSalaryMethod.LAST_FULL_PMR
        assert result.last_salary_info.salary_changed_in_last_year is False


class TestFixture11AllMonthsPartialFallback:
    """Fixture 11: All months partial — fallback to all months."""

    def test_all_months_partial_fallback(self):
        """Test fallback when all months in the last 12 are partial."""
        # Employment: 2024-01-15 to 2024-02-14
        # 2024-01: partial (starts 15 Jan)
        # 2024-02: partial (ends 14 Feb)
        # No full months → fallback to all
        start = date(2024, 1, 15)
        end = date(2024, 2, 14)

        pmrs = [
            make_pmr((2024, 1), "ep1", Decimal("10000")),
            make_pmr((2024, 2), "ep1", Decimal("10000")),
        ]
        mas = [
            make_month_aggregate((2024, 1)),
            make_month_aggregate((2024, 2)),
        ]
        eps = [make_effective_period("ep1", start, end)]

        result = compute_severance(
            termination_reason=TerminationReason.FIRED,
            industry="construction",  # min_months = 0
            period_month_records=pmrs,
            month_aggregates=mas,
            effective_periods=eps,
            total_employment_months=Decimal("1"),
            actual_deposits=Decimal("1500"),
        )

        assert result.eligible is True
        # Fallback to all months, salary 10,000 (no change)
        assert result.last_salary_info.last_salary == Decimal("10000")
        assert result.last_salary_info.method == LastSalaryMethod.LAST_FULL_PMR
        assert result.last_salary_info.salary_changed_in_last_year is False
