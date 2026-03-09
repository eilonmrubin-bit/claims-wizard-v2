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
                seniority_type="industry",
                from_months=0,
                to_months=None,  # Open-ended - applies from day 1 indefinitely
                employer_rate=Decimal("0.075"),
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
        assert result.ineligible_reason == "אין זכאות לקרן השתלמות"


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
    """Fixture 8: Custom tier — split month at seniority boundary.

    Input:
        industry: "general"
        employment: 2022-01-01 to 2022-12-31 (12 months)
        salary_monthly: 8,000
        job_scope: 1.0
        actual_deposits: 0
        seniority: starts at 2.5 months (prior experience), each month adds 1 month
        training_fund_tiers: [
            { seniority_type: "industry", from_months: 3, to_months: None,
              employer_rate: 0.075 }
        ]

    Expected:
        January 2022: split month (seniority 2.5→3.5 months, crosses 3)
            Segment A: before 3 months threshold -> ineligible
            Segment B: after threshold -> 7.5%
        Feb-Dec 2022: full tier coverage (11 months)
    """

    def test_custom_tier_split_month_at_boundary(self):
        pmrs = []
        mas = []
        seniority = []

        # Start with 2.5 months prior seniority, each month adds 1 month
        prior_months = Decimal("2.5")
        for month in range(1, 13):
            cumulative_months = prior_months + (month - 1)
            pmrs.append(PeriodMonthRecord(
                effective_period_id="ep1",
                month=(2022, month),
                salary_monthly=Decimal("8000"),
            ))
            mas.append(MonthAggregate(
                month=(2022, month),
                job_scope=Decimal("1.0"),
            ))
            seniority.append(SeniorityMonthly(
                month=(2022, month),
                worked=True,
                total_industry_cumulative=int(cumulative_months),
                total_industry_years_cumulative=cumulative_months / Decimal("12"),
            ))

        # Tier starts at 3 months seniority
        custom_tiers = [
            TrainingFundTier(
                seniority_type="industry",
                from_months=3,
                to_months=None,
                employer_rate=Decimal("0.075"),
            )
        ]

        result = compute_training_fund(
            period_month_records=pmrs,
            month_aggregates=mas,
            seniority_monthly=seniority,
            industry="general",
            is_construction_foreman=False,
            training_fund_tiers=custom_tiers,
            actual_deposits=Decimal("0"),
        )

        assert result.eligible is True
        assert result.used_custom_tiers is True

        # January should be a split month (seniority 2.5→3.5 months, crosses 3)
        jan = next(d for d in result.monthly_detail if d.month == (2022, 1))
        assert jan.is_split_month is True
        assert len(jan.segments) == 2
        assert jan.eligible_this_month is True

        # Segment 1: before threshold, ineligible
        seg1 = jan.segments[0]
        assert seg1.eligible is False
        assert seg1.employer_rate == Decimal("0")

        # Segment 2: after threshold, 7.5%
        seg2 = jan.segments[1]
        assert seg2.eligible is True
        assert seg2.employer_rate == Decimal("0.075")
        assert seg2.tier_source == "custom"

        # January amount should be partial (roughly half the month)
        assert jan.month_required > Decimal("0")
        assert jan.month_required < Decimal("600")  # Less than full month

        # Feb-Dec: 11 months at full rate
        for month in range(2, 13):
            m = next(d for d in result.monthly_detail if d.month == (2022, month))
            assert m.eligible_this_month is True
            assert m.is_split_month is False
            assert m.month_required == Decimal("600")  # 8,000 × 0.075


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


class TestFixture9MultiplePMRsSameMonth:
    """Fixture 9: Two PMRs in same month — hours_weight prevents double-counting.

    Input:
        industry: "cleaning"
        Month January 2022 has two effective periods (salary change mid-month):
        - PMR A: salary 6,000, hours 78
        - PMR B: salary 7,000, hours 91
        - MonthAggregate total_regular_hours: 169

    Expected:
        hours_weight_A = 78 / 169 ≈ 0.4615
        hours_weight_B = 91 / 169 ≈ 0.5385
        PMR A required = 6,000 × 0.075 × 0.4615 ≈ 207.69
        PMR B required = 7,000 × 0.075 × 0.5385 ≈ 282.71
        Total: ≈ 490.40

    Wrong calculation (using job_scope per PMR):
        If job_scope = 0.9266 (169/182.4) applied to each:
        PMR A = 6,000 × 0.075 × 0.9266 = 416.97
        PMR B = 7,000 × 0.075 × 0.9266 = 486.47
        Total = 903.44 → WRONG (double-count)
    """

    def test_multiple_pmrs_same_month_uses_hours_weight(self):
        # Two PMRs for the same month with different salaries and hours
        pmrs = [
            PeriodMonthRecord(
                effective_period_id="ep1",
                month=(2022, 1),
                salary_monthly=Decimal("6000"),
                total_regular_hours=Decimal("78"),
            ),
            PeriodMonthRecord(
                effective_period_id="ep2",
                month=(2022, 1),
                salary_monthly=Decimal("7000"),
                total_regular_hours=Decimal("91"),
            ),
        ]

        # Month aggregate with total hours for the month
        mas = [MonthAggregate(
            month=(2022, 1),
            total_regular_hours=Decimal("169"),  # 78 + 91
            job_scope=Decimal("0.9266"),  # 169/182.4 - should NOT be used
        )]

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
        assert len(result.monthly_detail) == 2

        # Find PMR A and B results
        pmr_a = next(d for d in result.monthly_detail if d.salary_base == Decimal("6000"))
        pmr_b = next(d for d in result.monthly_detail if d.salary_base == Decimal("7000"))

        # Check hours_weight is calculated correctly
        assert pmr_a.total_regular_hours == Decimal("78")
        assert pmr_a.month_total_regular_hours == Decimal("169")
        expected_weight_a = Decimal("78") / Decimal("169")
        assert abs(pmr_a.hours_weight - expected_weight_a) < Decimal("0.0001")

        assert pmr_b.total_regular_hours == Decimal("91")
        assert pmr_b.month_total_regular_hours == Decimal("169")
        expected_weight_b = Decimal("91") / Decimal("169")
        assert abs(pmr_b.hours_weight - expected_weight_b) < Decimal("0.0001")

        # PMR A required: 6,000 × 0.075 × (78/169) ≈ 207.69
        expected_a = Decimal("6000") * Decimal("0.075") * (Decimal("78") / Decimal("169"))
        assert abs(pmr_a.month_required - expected_a) < Decimal("0.01")

        # PMR B required: 7,000 × 0.075 × (91/169) ≈ 282.71
        expected_b = Decimal("7000") * Decimal("0.075") * (Decimal("91") / Decimal("169"))
        assert abs(pmr_b.month_required - expected_b) < Decimal("0.01")

        # Total should be approximately 490.40 (NOT 903.44 from double-count)
        expected_total = expected_a + expected_b
        assert abs(result.required_total - expected_total) < Decimal("0.01")

        # Verify it's NOT using job_scope (which would give ~903.44)
        wrong_total = (Decimal("6000") + Decimal("7000")) * Decimal("0.075") * Decimal("0.9266")
        assert result.required_total < wrong_total  # Sanity check


class TestPartialHoursWeight:
    """Tests for partial hours_weight handling (replaces job_scope tests)."""

    def test_partial_hours_weight_reduces_amount(self):
        """Hours weight < 1.0 should reduce month_required proportionally."""
        pmrs = [PeriodMonthRecord(
            effective_period_id="ep1",
            month=(2022, 1),
            salary_monthly=Decimal("10000"),
            total_regular_hours=Decimal("91"),  # Half of 182
        )]
        mas = [MonthAggregate(
            month=(2022, 1),
            total_regular_hours=Decimal("182"),  # Full month hours
            job_scope=Decimal("0.5"),  # Not used anymore
        )]

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
        # hours_weight = 91/182 = 0.5
        # 10,000 x 0.075 x 0.5 = 375
        assert result.monthly_detail[0].hours_weight == Decimal("91") / Decimal("182")
        assert result.monthly_detail[0].month_required == Decimal("10000") * Decimal("0.075") * (Decimal("91") / Decimal("182"))
        assert result.required_total == result.monthly_detail[0].month_required


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


class TestRightToggles:
    """Tests for right_toggles support."""

    def test_disabled_toggle_returns_ineligible(self):
        """When training_fund.enabled is False, should return ineligible."""
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
            right_toggles={"training_fund": {"enabled": False}},
        )

        assert result.eligible is False
        assert len(result.monthly_detail) == 0
        assert result.required_total == Decimal("0")

    def test_enabled_toggle_calculates_normally(self):
        """When training_fund.enabled is True, should calculate normally."""
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
            right_toggles={"training_fund": {"enabled": True}},
        )

        assert result.eligible is True
        assert result.required_total == Decimal("750")  # 10,000 × 0.075

    def test_no_toggles_calculates_normally(self):
        """When right_toggles is None, should calculate normally."""
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
            right_toggles=None,
        )

        assert result.eligible is True
        assert result.required_total == Decimal("750")


class TestSplitMonthWithMultiplePMRs:
    """Test combined scenario: split month at seniority threshold + two PMRs."""

    def test_split_month_with_two_pmrs_construction(self):
        """Split month + two PMRs: each PMR gets same segments but weighted by hours.

        Input:
            industry: "construction"
            is_construction_foreman: false
            Month: April 2023 (30 days)
            Two PMRs:
                PMR A: salary_monthly=10,000 | total_regular_hours=60
                PMR B: salary_monthly=12,000 | total_regular_hours=90
            month_total_regular_hours: 150
            Seniority at start of April: 2.9 years
            Seniority at end of April: 3.0 years → threshold crossed mid-April

        Expected:
            hours_weight_A = 60/150 = 0.4
            hours_weight_B = 90/150 = 0.6
            Both PMRs get is_split_month=True with same segments
            Segment before threshold: rate=0%, amount=0
            Segment after threshold: rate=2.5%
            PMR A month_required = 10,000 × 0.4 × (days_after/30) × 0.025
            PMR B month_required = 12,000 × 0.6 × (days_after/30) × 0.025
            required_total = sum of both (no double-count)
        """
        pmrs = [
            PeriodMonthRecord(
                effective_period_id="ep1",
                month=(2023, 4),
                salary_monthly=Decimal("10000"),
                total_regular_hours=Decimal("60"),
            ),
            PeriodMonthRecord(
                effective_period_id="ep2",
                month=(2023, 4),
                salary_monthly=Decimal("12000"),
                total_regular_hours=Decimal("90"),
            ),
        ]

        mas = [MonthAggregate(
            month=(2023, 4),
            total_regular_hours=Decimal("150"),
            job_scope=Decimal("1.0"),
        )]

        # Seniority crosses 3-year threshold during April
        # At start of April: 2.85 years (34.2 months)
        # At start of May: 3.1 years (37.2 months)
        # Threshold of 3.0 years crosses at approximately day 18 (60% through month)
        seniority = [
            SeniorityMonthly(
                month=(2023, 4),
                worked=True,
                total_industry_cumulative=34,
                total_industry_years_cumulative=Decimal("2.85"),
            ),
            SeniorityMonthly(
                month=(2023, 5),
                worked=True,
                total_industry_cumulative=37,
                total_industry_years_cumulative=Decimal("3.1"),
            ),
        ]

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
        assert len(result.monthly_detail) == 2

        # Find PMR A and PMR B
        pmr_a = next(d for d in result.monthly_detail if d.salary_base == Decimal("10000"))
        pmr_b = next(d for d in result.monthly_detail if d.salary_base == Decimal("12000"))

        # Both should be split months
        assert pmr_a.is_split_month is True
        assert pmr_b.is_split_month is True

        # Both should have 2 segments
        assert len(pmr_a.segments) == 2
        assert len(pmr_b.segments) == 2

        # Verify hours_weight
        assert pmr_a.hours_weight == Decimal("60") / Decimal("150")  # 0.4
        assert pmr_b.hours_weight == Decimal("90") / Decimal("150")  # 0.6

        # Both PMRs should have same segment structure
        # Segment 1: before threshold (ineligible)
        assert pmr_a.segments[0].eligible is False
        assert pmr_a.segments[0].employer_rate == Decimal("0")
        assert pmr_b.segments[0].eligible is False
        assert pmr_b.segments[0].employer_rate == Decimal("0")

        # Segment 2: after threshold (2.5%)
        assert pmr_a.segments[1].eligible is True
        assert pmr_a.segments[1].employer_rate == Decimal("0.025")
        assert pmr_b.segments[1].eligible is True
        assert pmr_b.segments[1].employer_rate == Decimal("0.025")

        # Days should be the same for both PMRs
        assert pmr_a.segments[0].days == pmr_b.segments[0].days
        assert pmr_a.segments[1].days == pmr_b.segments[1].days
        assert pmr_a.segments[0].days + pmr_a.segments[1].days == 30

        # Calculate expected amounts
        days_after = pmr_a.segments[1].days
        expected_a = Decimal("10000") * Decimal("0.4") * (Decimal(days_after) / Decimal("30")) * Decimal("0.025")
        expected_b = Decimal("12000") * Decimal("0.6") * (Decimal(days_after) / Decimal("30")) * Decimal("0.025")

        assert abs(pmr_a.month_required - expected_a) < Decimal("0.01")
        assert abs(pmr_b.month_required - expected_b) < Decimal("0.01")

        # Total should be sum of both
        expected_total = expected_a + expected_b
        assert abs(result.required_total - expected_total) < Decimal("0.01")

        # Verify no double-counting: total should be significantly less than
        # what we'd get if we applied full job_scope to each PMR
        wrong_total = (Decimal("10000") + Decimal("12000")) * (Decimal(days_after) / Decimal("30")) * Decimal("0.025")
        assert result.required_total < wrong_total


class TestOpenEndedTier:
    """Test open-ended tier (to_months=None) applies from threshold indefinitely."""

    def test_open_ended_tier_applies_from_threshold(self):
        """Open-ended tier (to_months=None) applies from from_months onwards.

        Input:
            industry: "general"
            employment: 2022-01-01 to 2024-12-31 (36 months)
            salary_monthly: 10,000
            seniority: starts at 0, each month adds 1 month
            training_fund_tiers: [
                { seniority_type: "industry", from_months: 48 (4 years),
                  to_months: None, employer_rate: 0.075 }
            ]

        Expected:
            Months 1-47: ineligible (seniority < 48 months)
            Month 48+: eligible at 7.5% (open-ended tier kicks in)
        """
        pmrs = []
        mas = []
        seniority = []

        # 60 months of employment (5 years)
        cumulative_months = 0
        for year in range(2020, 2025):
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

        # Tier starts at 48 months (4 years) with no upper limit
        custom_tiers = [
            TrainingFundTier(
                seniority_type="industry",
                from_months=48,
                to_months=None,  # Open-ended
                employer_rate=Decimal("0.075"),
            )
        ]

        result = compute_training_fund(
            period_month_records=pmrs,
            month_aggregates=mas,
            seniority_monthly=seniority,
            industry="general",
            is_construction_foreman=False,
            training_fund_tiers=custom_tiers,
            actual_deposits=Decimal("0"),
        )

        assert result.eligible is True
        assert result.used_custom_tiers is True

        # Count eligible vs ineligible months
        eligible_months = [d for d in result.monthly_detail if d.eligible_this_month]
        ineligible_months = [d for d in result.monthly_detail if not d.eligible_this_month]

        # First 48 months (0-47) should be ineligible
        # Month 48 crosses the threshold, then months 49-59 are fully eligible
        # That's 12 eligible months (month 48 is split, counts as eligible)
        assert len(eligible_months) == 12  # Months 48-59
        assert len(ineligible_months) == 48  # Months 0-47

        # Verify tier applies from month 49 onwards at full rate
        for d in result.monthly_detail:
            year, month = d.month
            month_index = (year - 2020) * 12 + month - 1  # 0-indexed
            if month_index >= 49:  # After threshold fully crossed
                assert d.eligible_this_month is True
                assert d.month_required == Decimal("750")  # 10,000 × 0.075
