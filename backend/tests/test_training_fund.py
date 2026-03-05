"""Tests for training fund (קרן השתלמות) module.

See docs/skills/training-fund/SKILL.md for test cases.
"""

import pytest
from datetime import date
from decimal import Decimal

from app.modules.training_fund import compute_training_fund, load_training_fund_config
from app.ssot import PeriodMonthRecord, MonthAggregate, SeniorityMonthly, TrainingFundTier


class TestLoadConfig:
    """Tests for configuration loading."""

    def test_loads_construction_tiers(self):
        """Configuration should include construction tiers by seniority."""
        config = load_training_fund_config()
        assert "construction" in config
        assert config["construction"].tiers_by_seniority is not None
        assert len(config["construction"].tiers_by_seniority) == 4

    def test_loads_cleaning_rates(self):
        """Configuration should include cleaning flat rates."""
        config = load_training_fund_config()
        assert "cleaning" in config
        assert config["cleaning"].employer_rate == Decimal("0.075")
        assert config["cleaning"].employee_rate == Decimal("0.025")

    def test_general_has_null_rates(self):
        """General industry should have null rates (requires custom tiers)."""
        config = load_training_fund_config()
        assert "general" in config
        assert config["general"].employer_rate is None
        assert config["general"].employee_rate is None


class TestFixture1ConstructionWorker3To6YearSeniority:
    """Fixture 1: Construction worker, 3-6 year seniority tier.

    Input:
        industry: "construction"
        is_construction_foreman: false
        employment: 2020-01-01 to 2023-06-30
        industry_seniority at start: 2.5 years (crosses 3yr threshold in Jul 2020)
        salary_monthly: 10,000
        job_scope: 1.0
        actual_deposits: 0

    Expected:
        Months Jan-Jun 2020: seniority < 3yr -> eligible_this_month = false, amount = 0
        Months Jul 2020-Jun 2023: seniority >= 3yr, < 6yr -> employer_rate = 2.5%
        Eligible months: 36
        required_total = 10,000 x 0.025 x 36 = 9,000
        claim_before_deductions = 9,000
    """

    def test_construction_worker_3_to_6_year_tier(self):
        # Create PMRs for 42 months (Jan 2020 - Jun 2023)
        pmrs = []
        mas = []
        seniority = []

        # Starting seniority: 2.5 years = 30 months
        cumulative_months = 30

        for year in range(2020, 2024):
            for month in range(1, 13):
                if year == 2023 and month > 6:
                    break  # End at Jun 2023

                pmrs.append(PeriodMonthRecord(
                    effective_period_id="ep1",
                    month=(year, month),
                    salary_monthly=Decimal("10000"),
                ))
                mas.append(MonthAggregate(
                    month=(year, month),
                    job_scope=Decimal("1.0"),
                ))
                seniority.append(SeniorityMonthly(
                    month=(year, month),
                    worked=True,
                    total_industry_cumulative=cumulative_months,
                    total_industry_years_cumulative=Decimal(cumulative_months) / Decimal("12"),
                ))
                cumulative_months += 1

        result = compute_training_fund(
            period_month_records=pmrs,
            month_aggregates=mas,
            seniority_monthly=seniority,
            industry="construction",
            is_construction_foreman=False,
            training_fund_tiers=[],
            actual_deposits=Decimal("0"),
        )

        assert result.eligible is True
        assert result.industry == "construction"
        assert result.is_construction_foreman is False

        # First 6 months (Jan-Jun 2020): seniority < 3yr, not eligible
        ineligible_months = [d for d in result.monthly_detail if not d.eligible_this_month]
        assert len(ineligible_months) == 6

        # Remaining 36 months (Jul 2020 - Jun 2023): eligible
        eligible_months = [d for d in result.monthly_detail if d.eligible_this_month]
        assert len(eligible_months) == 36

        # All eligible months should have segments with 2.5% rate
        for m in eligible_months:
            assert len(m.segments) >= 1
            # At least one segment should have 2.5%
            assert any(seg.employer_rate == Decimal("0.025") for seg in m.segments)

        # Total: 36 x 10,000 x 0.025 = 9,000
        assert result.required_total == Decimal("9000")
        assert result.claim_before_deductions == Decimal("9000")


class TestFixture2ConstructionForeman:
    """Fixture 2: Construction foreman.

    Input:
        industry: "construction"
        is_construction_foreman: true
        employment: 2022-01-01 to 2023-12-31 (24 months)
        salary_monthly: 12,000
        job_scope: 1.0
        actual_deposits: 10,000

    Expected:
        employer_rate = 7.5% (from day 1)
        required_total = 12,000 x 0.075 x 24 = 21,600
        claim_before_deductions = 21,600
        // actual_deposits = 10,000 -> handled by deductions module -> net = 11,600
    """

    def test_construction_foreman_full_eligibility(self):
        pmrs = []
        mas = []
        seniority = []

        cumulative_months = 0  # No prior seniority
        for year in range(2022, 2024):
            for month in range(1, 13):
                pmrs.append(PeriodMonthRecord(
                    effective_period_id="ep1",
                    month=(year, month),
                    salary_monthly=Decimal("12000"),
                ))
                mas.append(MonthAggregate(
                    month=(year, month),
                    job_scope=Decimal("1.0"),
                ))
                seniority.append(SeniorityMonthly(
                    month=(year, month),
                    worked=True,
                    total_industry_cumulative=cumulative_months,
                    total_industry_years_cumulative=Decimal(cumulative_months) / Decimal("12"),
                ))
                cumulative_months += 1

        result = compute_training_fund(
            period_month_records=pmrs,
            month_aggregates=mas,
            seniority_monthly=seniority,
            industry="construction",
            is_construction_foreman=True,
            training_fund_tiers=[],
            actual_deposits=Decimal("10000"),
        )

        assert result.eligible is True
        assert result.is_construction_foreman is True

        # All 24 months should be eligible (foreman gets 7.5% from day 1)
        assert len(result.monthly_detail) == 24
        for m in result.monthly_detail:
            assert m.eligible_this_month is True
            assert len(m.segments) == 1
            assert m.segments[0].employer_rate == Decimal("0.075")
            assert m.month_required == Decimal("900")  # 12,000 x 0.075

        assert result.required_total == Decimal("21600")
        assert result.claim_before_deductions == Decimal("21600")
        assert result.actual_deposits == Decimal("10000")


class TestFixture3Cleaning:
    """Fixture 3: Cleaning.

    Input:
        industry: "cleaning"
        employment: 2022-01-01 to 2023-12-31 (24 months)
        salary_monthly: 6,000
        job_scope: 1.0
        actual_deposits: 5,000
        recreation_pending: true

    Expected:
        salary_base = 6,000 (recreation pending)
        required_total = 6,000 x 0.075 x 24 = 10,800
        claim_before_deductions = 10,800
        recreation_pending = true
    """

    def test_cleaning_with_recreation_pending(self):
        pmrs = []
        mas = []

        for year in range(2022, 2024):
            for month in range(1, 13):
                pmrs.append(PeriodMonthRecord(
                    effective_period_id="ep1",
                    month=(year, month),
                    salary_monthly=Decimal("6000"),
                ))
                mas.append(MonthAggregate(
                    month=(year, month),
                    job_scope=Decimal("1.0"),
                ))

        result = compute_training_fund(
            period_month_records=pmrs,
            month_aggregates=mas,
            seniority_monthly=[],
            industry="cleaning",
            is_construction_foreman=False,
            training_fund_tiers=[],
            actual_deposits=Decimal("5000"),
        )

        assert result.eligible is True
        assert result.industry == "cleaning"
        assert result.recreation_pending is True

        # All 24 months should be eligible with 7.5% rate
        assert len(result.monthly_detail) == 24
        for m in result.monthly_detail:
            assert m.eligible_this_month is True
            assert len(m.segments) == 1
            assert m.segments[0].employer_rate == Decimal("0.075")
            assert m.salary_base == Decimal("6000")
            assert m.recreation_component == Decimal("0")  # Pending
            assert m.month_required == Decimal("450")  # 6,000 x 0.075

        assert result.required_total == Decimal("10800")
        assert result.claim_before_deductions == Decimal("10800")
        assert result.actual_deposits == Decimal("5000")


class TestFixture4CustomTiersOverride:
    """Fixture 4: Custom tiers override.

    Input:
        industry: "construction"
        is_construction_foreman: false
        employment: 2021-01-01 to 2023-12-31 (36 months)
        salary_monthly: 10,000
        job_scope: 1.0
        actual_deposits: 0
        training_fund_tiers: [
            { start_date: 2021-01-01, end_date: 2023-12-31,
              employer_rate: 0.075, employee_rate: 0.025 }
        ]

    Expected:
        Custom tier covers all months -> employer_rate = 7.5% for all months
        required_total = 10,000 x 0.075 x 36 = 27,000
        claim_before_deductions = 27,000
    """

    def test_custom_tiers_override_industry_defaults(self):
        pmrs = []
        mas = []
        seniority = []

        cumulative_months = 0
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
                seniority.append(SeniorityMonthly(
                    month=(year, month),
                    worked=True,
                    total_industry_cumulative=cumulative_months,
                    total_industry_years_cumulative=Decimal(cumulative_months) / Decimal("12"),
                ))
                cumulative_months += 1

        custom_tiers = [
            TrainingFundTier(
                start_date=date(2021, 1, 1),
                end_date=date(2023, 12, 31),
                employer_rate=Decimal("0.075"),
                employee_rate=Decimal("0.025"),
            )
        ]

        result = compute_training_fund(
            period_month_records=pmrs,
            month_aggregates=mas,
            seniority_monthly=seniority,
            industry="construction",
            is_construction_foreman=False,
            training_fund_tiers=custom_tiers,
            actual_deposits=Decimal("0"),
        )

        assert result.eligible is True
        assert result.used_custom_tiers is True

        # All 36 months should use custom tier rate
        assert len(result.monthly_detail) == 36
        for m in result.monthly_detail:
            assert len(m.segments) == 1
            assert m.segments[0].tier_source == "custom"
            assert m.segments[0].employer_rate == Decimal("0.075")
            assert m.segments[0].eligible is True
            assert m.month_required == Decimal("750")  # 10,000 x 0.075

        assert result.required_total == Decimal("27000")
        assert result.claim_before_deductions == Decimal("27000")


class TestFixture5AgricultureIneligible:
    """Fixture 5: Agriculture - ineligible.

    Input:
        industry: "agriculture"

    Expected:
        eligible: false
        ineligible_reason: "ענף חקלאות — אין זכות אישית לעובד רגיל"
        No calculation.
    """

    def test_agriculture_returns_ineligible(self):
        pmrs = [PeriodMonthRecord(
            effective_period_id="ep1",
            month=(2021, 1),
            salary_monthly=Decimal("10000"),
        )]
        mas = [MonthAggregate(month=(2021, 1), job_scope=Decimal("1.0"))]

        result = compute_training_fund(
            period_month_records=pmrs,
            month_aggregates=mas,
            seniority_monthly=[],
            industry="agriculture",
            is_construction_foreman=False,
            training_fund_tiers=[],
            actual_deposits=Decimal("0"),
        )

        assert result.eligible is False
        assert result.ineligible_reason == "ענף חקלאות — אין זכות אישית לעובד רגיל"
        assert len(result.monthly_detail) == 0
        assert result.required_total == Decimal("0")


class TestFixture6GeneralWithoutCustomTiersIneligible:
    """Fixture 6: General without custom tiers - ineligible.

    Input:
        industry: "general"
        training_fund_tiers: null

    Expected:
        eligible: false
        ineligible_reason: "לא הוזנו מדרגות קרן השתלמות"
    """

    def test_general_without_custom_tiers_returns_ineligible(self):
        pmrs = [PeriodMonthRecord(
            effective_period_id="ep1",
            month=(2021, 1),
            salary_monthly=Decimal("10000"),
        )]
        mas = [MonthAggregate(month=(2021, 1), job_scope=Decimal("1.0"))]

        result = compute_training_fund(
            period_month_records=pmrs,
            month_aggregates=mas,
            seniority_monthly=[],
            industry="general",
            is_construction_foreman=False,
            training_fund_tiers=[],  # No custom tiers
            actual_deposits=Decimal("0"),
        )

        assert result.eligible is False
        assert result.ineligible_reason == "לא הוזנו מדרגות קרן השתלמות"


class TestFixture7ConstructionSplitMonthSeniorityThreshold:
    """Fixture 7: Construction worker — split month at 3-year threshold.

    Input:
        industry: "construction"
        is_construction_foreman: false
        employment: 2020-03-15 to 2023-06-30
        industry_seniority at 2020-03-15: 2 years 11 months
        → 3-year threshold reached on: 2020-04-15
        salary_monthly: 10,000
        job_scope: 1.0
        actual_deposits: 0

    Expected for April 2020:
        is_split_month: true
        segments:
            { days: 14, days_total: 30, employer_rate: 0.0, eligible: false }
            { days: 16, days_total: 30, employer_rate: 0.025, eligible: true }
        month_required: ~133.33
    """

    def test_split_month_at_3_year_seniority_threshold(self):
        # Create PMRs for Mar 2020 - Jun 2020 (4 months to test the split)
        pmrs = []
        mas = []
        seniority = []

        # Starting seniority: 2 years 11 months = 35 months
        # At start of March 2020: 35 months = 2.9167 years
        # At start of April 2020: 36 months = 3.0 years (crosses threshold during April)
        # Actually, we need seniority to cross mid-April

        # Let's set it up so that:
        # - At start of April 2020: seniority = 2 years 11.5 months = 35.5 months = 2.9583 years
        # - By end of April 2020 (start of May): seniority = 36.5 months = 3.0417 years
        # - Threshold of 3.0 years (36 months) is crossed on April 15

        months_data = [
            ((2020, 3), Decimal("35")),  # March: 35 months = 2.917 years
            ((2020, 4), Decimal("35.5")),  # April start: 35.5 months = 2.9583 years
            ((2020, 5), Decimal("36.5")),  # May start: 36.5 months = 3.0417 years
            ((2020, 6), Decimal("37.5")),  # June start: 37.5 months
        ]

        for (year, month), cumulative in months_data:
            pmrs.append(PeriodMonthRecord(
                effective_period_id="ep1",
                month=(year, month),
                salary_monthly=Decimal("10000"),
            ))
            mas.append(MonthAggregate(
                month=(year, month),
                job_scope=Decimal("1.0"),
            ))
            seniority.append(SeniorityMonthly(
                month=(year, month),
                worked=True,
                total_industry_cumulative=int(cumulative),
                total_industry_years_cumulative=cumulative / Decimal("12"),
            ))

        result = compute_training_fund(
            period_month_records=pmrs,
            month_aggregates=mas,
            seniority_monthly=seniority,
            industry="construction",
            is_construction_foreman=False,
            training_fund_tiers=[],
            actual_deposits=Decimal("0"),
        )

        assert result.eligible is True

        # Find April 2020
        april = next(d for d in result.monthly_detail if d.month == (2020, 4))

        # April should be a split month
        assert april.is_split_month is True
        assert len(april.segments) == 2

        # First segment: before threshold (ineligible)
        seg1 = april.segments[0]
        assert seg1.eligible is False
        assert seg1.employer_rate == Decimal("0")

        # Second segment: after threshold (eligible at 2.5%)
        seg2 = april.segments[1]
        assert seg2.eligible is True
        assert seg2.employer_rate == Decimal("0.025")

        # Month is partially eligible
        assert april.eligible_this_month is True

        # Total days should be 30
        assert seg1.days + seg2.days == 30
        assert seg1.days_total == 30
        assert seg2.days_total == 30

        # Check the total is approximately correct
        # ~133.33 = 10,000 x (16/30) x 0.025
        expected_approx = Decimal("10000") * (Decimal(seg2.days) / Decimal("30")) * Decimal("0.025")
        assert abs(april.month_required - expected_approx) < Decimal("1")


class TestFixture8CustomTierSplitMonth:
    """Fixture 8: Custom tier — split month at tier boundary.

    Input:
        industry: "general"
        employment: 2022-01-01 to 2022-12-31 (12 months)
        salary_monthly: 8,000
        job_scope: 1.0
        actual_deposits: 0
        training_fund_tiers: [
            { start_date: 2022-03-16, end_date: 2022-12-31,
              employer_rate: 0.075, employee_rate: 0.025 }
        ]

    Expected:
        Jan-Feb 2022: ineligible (no tier)
        March 2022: split month
            Segment A: days 1-15 (15 days) -> ineligible
            Segment B: days 16-31 (16 days) -> 7.5%
            month_required = 8,000 × (16/31) × 0.075 = 309.68
        Apr-Dec 2022: full tier coverage, 9 × 8,000 × 0.075 = 5,400
        required_total: 0 + 0 + 309.68 + 5,400 = 5,709.68
    """

    def test_custom_tier_split_month_at_boundary(self):
        pmrs = []
        mas = []

        for month in range(1, 13):
            pmrs.append(PeriodMonthRecord(
                effective_period_id="ep1",
                month=(2022, month),
                salary_monthly=Decimal("8000"),
            ))
            mas.append(MonthAggregate(
                month=(2022, month),
                job_scope=Decimal("1.0"),
            ))

        custom_tiers = [
            TrainingFundTier(
                start_date=date(2022, 3, 16),
                end_date=date(2022, 12, 31),
                employer_rate=Decimal("0.075"),
                employee_rate=Decimal("0.025"),
            )
        ]

        result = compute_training_fund(
            period_month_records=pmrs,
            month_aggregates=mas,
            seniority_monthly=[],
            industry="general",
            is_construction_foreman=False,
            training_fund_tiers=custom_tiers,
            actual_deposits=Decimal("0"),
        )

        assert result.eligible is True
        assert result.used_custom_tiers is True

        # Jan-Feb should be ineligible (no tier covers them)
        jan = next(d for d in result.monthly_detail if d.month == (2022, 1))
        feb = next(d for d in result.monthly_detail if d.month == (2022, 2))
        assert jan.eligible_this_month is False
        assert jan.month_required == Decimal("0")
        assert feb.eligible_this_month is False
        assert feb.month_required == Decimal("0")

        # March should be a split month
        march = next(d for d in result.monthly_detail if d.month == (2022, 3))
        assert march.is_split_month is True
        assert len(march.segments) == 2
        assert march.eligible_this_month is True

        # Segment 1: days 1-15 (15 days), ineligible
        seg1 = march.segments[0]
        assert seg1.days == 15
        assert seg1.eligible is False
        assert seg1.employer_rate == Decimal("0")

        # Segment 2: days 16-31 (16 days), 7.5%
        seg2 = march.segments[1]
        assert seg2.days == 16
        assert seg2.eligible is True
        assert seg2.employer_rate == Decimal("0.075")
        assert seg2.tier_source == "custom"

        # March amount: 8,000 × (16/31) × 0.075 ≈ 309.68
        expected_march = Decimal("8000") * (Decimal("16") / Decimal("31")) * Decimal("0.075")
        assert abs(march.month_required - expected_march) < Decimal("0.01")

        # Apr-Dec: 9 months at full rate
        apr_dec_total = Decimal("0")
        for month in range(4, 13):
            m = next(d for d in result.monthly_detail if d.month == (2022, month))
            assert m.eligible_this_month is True
            assert m.is_split_month is False
            assert m.month_required == Decimal("600")  # 8,000 × 0.075
            apr_dec_total += m.month_required

        assert apr_dec_total == Decimal("5400")  # 9 × 600

        # Total: 0 + 0 + ~309.68 + 5400 ≈ 5709.68
        expected_total = expected_march + Decimal("5400")
        assert abs(result.required_total - expected_total) < Decimal("0.01")


class TestConstructionSeniorityThresholds:
    """Tests for construction seniority threshold transitions."""

    def test_crossing_6_year_threshold(self):
        """Worker crossing 6-year threshold mid-employment gets higher rate."""
        pmrs = []
        mas = []
        seniority = []

        # Start with 5.5 years = 66 months seniority
        cumulative_months = 66

        for year in range(2022, 2024):
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
                seniority.append(SeniorityMonthly(
                    month=(year, month),
                    worked=True,
                    total_industry_cumulative=cumulative_months,
                    total_industry_years_cumulative=Decimal(cumulative_months) / Decimal("12"),
                ))
                cumulative_months += 1

        result = compute_training_fund(
            period_month_records=pmrs,
            month_aggregates=mas,
            seniority_monthly=seniority,
            industry="construction",
            is_construction_foreman=False,
            training_fund_tiers=[],
            actual_deposits=Decimal("0"),
        )

        # First 6 months (Jan-Jun 2022): seniority 5.5-6yr -> 2.5%
        for i in range(6):
            m = result.monthly_detail[i]
            # Should have single segment or be eligible at 2.5%
            assert any(seg.employer_rate == Decimal("0.025") for seg in m.segments)

        # After Jul 2022: seniority >= 6yr -> 5%
        for i in range(6, 24):
            m = result.monthly_detail[i]
            # Should have segment(s) at 5%
            assert any(seg.employer_rate == Decimal("0.05") for seg in m.segments)


class TestPartialJobScope:
    """Tests for partial job scope handling."""

    def test_partial_job_scope_reduces_amount(self):
        """Job scope < 1.0 should reduce month_required proportionally."""
        pmrs = [PeriodMonthRecord(
            effective_period_id="ep1",
            month=(2022, 1),
            salary_monthly=Decimal("10000"),
        )]
        mas = [MonthAggregate(month=(2022, 1), job_scope=Decimal("0.5"))]

        result = compute_training_fund(
            period_month_records=pmrs,
            month_aggregates=mas,
            seniority_monthly=[],
            industry="cleaning",
            is_construction_foreman=False,
            training_fund_tiers=[],
            actual_deposits=Decimal("0"),
        )

        assert result.eligible is True
        # 10,000 x 0.075 x 0.5 = 375
        assert result.monthly_detail[0].month_required == Decimal("375")
        assert result.required_total == Decimal("375")


class TestMonthlyBreakdown:
    """Tests for monthly_breakdown generation."""

    def test_monthly_breakdown_matches_monthly_detail(self):
        """monthly_breakdown should contain same amounts as monthly_detail."""
        pmrs = []
        mas = []

        for month in range(1, 4):
            pmrs.append(PeriodMonthRecord(
                effective_period_id="ep1",
                month=(2022, month),
                salary_monthly=Decimal("10000"),
            ))
            mas.append(MonthAggregate(
                month=(2022, month),
                job_scope=Decimal("1.0"),
            ))

        result = compute_training_fund(
            period_month_records=pmrs,
            month_aggregates=mas,
            seniority_monthly=[],
            industry="cleaning",
            is_construction_foreman=False,
            training_fund_tiers=[],
            actual_deposits=Decimal("0"),
        )

        assert len(result.monthly_breakdown) == 3
        for detail, breakdown in zip(result.monthly_detail, result.monthly_breakdown):
            assert detail.month == breakdown.month
            assert detail.month_required == breakdown.claim_amount


class TestSegmentStructure:
    """Tests for segment structure in monthly detail."""

    def test_non_split_month_has_single_segment(self):
        """Non-split months should have exactly one segment."""
        pmrs = [PeriodMonthRecord(
            effective_period_id="ep1",
            month=(2022, 1),
            salary_monthly=Decimal("10000"),
        )]
        mas = [MonthAggregate(month=(2022, 1), job_scope=Decimal("1.0"))]

        result = compute_training_fund(
            period_month_records=pmrs,
            month_aggregates=mas,
            seniority_monthly=[],
            industry="cleaning",
            is_construction_foreman=False,
            training_fund_tiers=[],
            actual_deposits=Decimal("0"),
        )

        assert len(result.monthly_detail) == 1
        m = result.monthly_detail[0]
        assert m.is_split_month is False
        assert len(m.segments) == 1
        assert m.segments[0].days == 31  # January has 31 days
        assert m.segments[0].days_total == 31
