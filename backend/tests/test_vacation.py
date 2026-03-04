"""Tests for annual vacation (חופשה שנתית) calculation.

Test cases from docs/skills/vacation/SKILL.md
"""

import pytest
from datetime import date
from decimal import Decimal

from app.ssot import (
    EmploymentPeriod,
    WorkPattern,
    PeriodMonthRecord,
    SeniorityTotals,
    Duration,
)
from app.modules.vacation import compute_vacation


# =============================================================================
# Test fixtures
# =============================================================================

def make_employment_period(start: date, end: date) -> EmploymentPeriod:
    """Create an employment period."""
    return EmploymentPeriod(
        id="EP1",
        start=start,
        end=end,
        duration=Duration(days=(end - start).days + 1),
    )


def make_work_pattern(start: date, end: date, work_days: list[int]) -> WorkPattern:
    """Create a work pattern.

    work_days: list of weekday indices (0=Monday, 6=Sunday)
    For 5-day week: [0, 1, 2, 3, 4] (Sun-Thu)
    For 6-day week: [0, 1, 2, 3, 4, 5] (Sun-Fri)
    """
    return WorkPattern(
        id="WP1",
        start=start,
        end=end,
        work_days=work_days,
    )


def make_period_month_records(
    start: date,
    end: date,
    daily_salary: Decimal,
    work_days_per_month: int = 22,
) -> list[PeriodMonthRecord]:
    """Create period month records for each month in the range."""
    records = []
    current = date(start.year, start.month, 1)
    while current <= end:
        records.append(PeriodMonthRecord(
            month=(current.year, current.month),
            effective_period_id="EP1",
            work_days_count=work_days_per_month,
            salary_daily=daily_salary,
            salary_monthly=daily_salary * Decimal(str(work_days_per_month)),
        ))
        # Move to next month
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)
    return records


def make_seniority_totals(prior_months: int = 0) -> SeniorityTotals:
    """Create seniority totals with prior seniority."""
    return SeniorityTotals(
        prior_seniority_months=prior_months,
        at_defendant_months=0,  # Will be computed by pipeline
        total_industry_months=prior_months,
        at_defendant_years=Decimal("0"),
        total_industry_years=Decimal(str(prior_months / 12)) if prior_months else Decimal("0"),
    )


# =============================================================================
# Test Case 1: General, 5-day, 3 full years
# =============================================================================

def test_case_1_general_5day_3_full_years():
    """
    Employment: 2021-01-01 – 2023-12-31, prior=0, salary 10,000₪/month
    5-day week

    Expected:
    - Year 2021: seniority=1, base=12 days (5-day)
    - Year 2022: seniority=2, base=12 days
    - Year 2023: seniority=3, base=12 days
    """
    start = date(2021, 1, 1)
    end = date(2023, 12, 31)

    employment_periods = [make_employment_period(start, end)]
    # 5-day week: Sun-Thu (indices 0-4 in Israeli week, but using 0=Monday standard)
    # Actually, for 5-day week, we use indices 0-4 which excludes Friday (5)
    work_patterns = [make_work_pattern(start, end, [0, 1, 2, 3, 4])]

    daily_salary = Decimal("10000") / Decimal("22")  # ~454.55
    period_month_records = make_period_month_records(start, end, daily_salary)
    seniority_totals = make_seniority_totals(prior_months=0)

    result = compute_vacation(
        employment_periods=employment_periods,
        work_patterns=work_patterns,
        period_month_records=period_month_records,
        industry="general",
        seniority_totals=seniority_totals,
        birth_year=None,
        right_toggles=None,
    )

    assert result.entitled is True
    assert result.industry == "general"
    assert result.seniority_basis == "employer"
    assert len(result.years) == 3

    # Year 2021: seniority=1 → 12 days (5-day)
    assert result.years[0].year == 2021
    assert result.years[0].seniority_years == 1
    assert result.years[0].is_partial is False

    # Year 2022: seniority=2 → 12 days (5-day, 1-5 years = 12)
    assert result.years[1].year == 2022
    assert result.years[1].seniority_years == 2
    assert result.years[1].is_partial is False

    # Year 2023: seniority=3 → 12 days (5-day, 1-5 years = 12)
    assert result.years[2].year == 2023
    assert result.years[2].seniority_years == 3
    assert result.years[2].is_partial is False

    # Total should be 36 days
    assert result.grand_total_days == Decimal("36")


# =============================================================================
# Test Case 2: Cleaning, partial first/last year, industry seniority
# =============================================================================

def test_case_2_cleaning_partial_years_industry_seniority():
    """
    Employment: 2021-04-01 – 2023-09-30, prior=12m (1y), 5-day
    Cleaning uses industry seniority

    Expected:
    - Year 2021 (Apr-Dec, 9 months): seniority=floor(12/12)+1=2 → 10 days × 9/12
    - Year 2022 (full year): seniority=floor(21/12)+1=2 → 10 days
    - Year 2023 (Jan-Sep, 9 months): seniority=floor(33/12)+1=3 → 11 days × 9/12
    """
    start = date(2021, 4, 1)
    end = date(2023, 9, 30)

    employment_periods = [make_employment_period(start, end)]
    work_patterns = [make_work_pattern(start, end, [0, 1, 2, 3, 4])]  # 5-day

    daily_salary = Decimal("400")  # 40₪/h × 10 hours
    period_month_records = make_period_month_records(start, end, daily_salary)
    seniority_totals = make_seniority_totals(prior_months=12)  # 1 year prior

    result = compute_vacation(
        employment_periods=employment_periods,
        work_patterns=work_patterns,
        period_month_records=period_month_records,
        industry="cleaning",
        seniority_totals=seniority_totals,
        birth_year=None,
        right_toggles=None,
    )

    assert result.entitled is True
    assert result.industry == "cleaning"
    assert result.seniority_basis == "industry"
    assert len(result.years) == 3

    # Year 2021: partial (Apr-Dec), seniority=2 (12m prior / 12 + 1)
    assert result.years[0].year == 2021
    assert result.years[0].seniority_years == 2  # floor(12/12)+1 = 2
    assert result.years[0].is_partial is True

    # Year 2022: full year, seniority=2 (still in range)
    assert result.years[1].year == 2022
    assert result.years[1].seniority_years == 2  # floor(21/12)+1 = 2
    assert result.years[1].is_partial is False

    # Year 2023: partial (Jan-Sep), seniority=3
    assert result.years[2].year == 2023
    assert result.years[2].seniority_years == 3  # floor(33/12)+1 = 3
    assert result.years[2].is_partial is True


# =============================================================================
# Test Case 3: Construction, age 55 split
# =============================================================================

def test_case_3_construction_age_55_split():
    """
    Employment: 2015-01-01 – 2024-12-31, prior=24m (2y), birth_year=1969
    Age 55 turns on 2024-01-01 (Jan 1, 1969+55)

    Construction uses industry seniority.
    At start of 2024: seniority = prior(24m) + months at defendant 2015-2023 (108m) = 132m
    seniority_years = floor(132/12)+1 = 11+1 = 12 years

    Age 55 on Jan 1 2024 → full year at 55+ → use construction_55plus table
    """
    start = date(2015, 1, 1)
    end = date(2024, 12, 31)

    employment_periods = [make_employment_period(start, end)]
    work_patterns = [make_work_pattern(start, end, [0, 1, 2, 3, 4, 5])]  # 6-day

    daily_salary = Decimal("500")
    period_month_records = make_period_month_records(start, end, daily_salary)
    seniority_totals = make_seniority_totals(prior_months=24)  # 2 years prior

    result = compute_vacation(
        employment_periods=employment_periods,
        work_patterns=work_patterns,
        period_month_records=period_month_records,
        industry="construction",
        seniority_totals=seniority_totals,
        birth_year=1969,
        right_toggles=None,
    )

    assert result.entitled is True
    assert result.industry == "construction"
    assert result.seniority_basis == "industry"

    # Find year 2024
    year_2024 = next((y for y in result.years if y.year == 2024), None)
    assert year_2024 is not None

    # Age at year start (2024) = 2024 - 1969 = 55
    assert year_2024.age_at_year_start == 55

    # Since age 55 is exactly on Jan 1, no split needed - full year at 55+
    # Worker turned 55 on Jan 1 2024, so full year is 55+


# =============================================================================
# Anti-pattern tests
# =============================================================================

def test_anti_pattern_calendar_year_not_employment_anniversary():
    """Vacation is calculated per calendar year, not employment anniversary year."""
    # Employment starting mid-year
    start = date(2022, 7, 1)
    end = date(2023, 12, 31)

    employment_periods = [make_employment_period(start, end)]
    work_patterns = [make_work_pattern(start, end, [0, 1, 2, 3, 4])]

    daily_salary = Decimal("450")
    period_month_records = make_period_month_records(start, end, daily_salary)
    seniority_totals = make_seniority_totals(prior_months=0)

    result = compute_vacation(
        employment_periods=employment_periods,
        work_patterns=work_patterns,
        period_month_records=period_month_records,
        industry="general",
        seniority_totals=seniority_totals,
    )

    # Should have 2 calendar years (2022 partial, 2023 full)
    assert len(result.years) == 2

    # First year should be 2022, partial
    assert result.years[0].year == 2022
    assert result.years[0].is_partial is True

    # Second year should be 2023, full
    assert result.years[1].year == 2023
    assert result.years[1].is_partial is False


def test_anti_pattern_industry_seniority_for_construction():
    """Construction uses industry seniority (prior + at defendant), not employer-only."""
    start = date(2023, 1, 1)
    end = date(2023, 12, 31)

    employment_periods = [make_employment_period(start, end)]
    work_patterns = [make_work_pattern(start, end, [0, 1, 2, 3, 4, 5])]

    daily_salary = Decimal("400")
    period_month_records = make_period_month_records(start, end, daily_salary)
    # 5 years prior seniority in industry
    seniority_totals = make_seniority_totals(prior_months=60)

    result = compute_vacation(
        employment_periods=employment_periods,
        work_patterns=work_patterns,
        period_month_records=period_month_records,
        industry="construction",
        seniority_totals=seniority_totals,
    )

    # With 60 months prior, seniority = floor(60/12)+1 = 6
    assert result.years[0].seniority_years == 6
    assert result.seniority_basis == "industry"


def test_anti_pattern_employer_seniority_for_general():
    """General industry uses employer seniority only, not industry."""
    start = date(2023, 1, 1)
    end = date(2023, 12, 31)

    employment_periods = [make_employment_period(start, end)]
    work_patterns = [make_work_pattern(start, end, [0, 1, 2, 3, 4])]

    daily_salary = Decimal("450")
    period_month_records = make_period_month_records(start, end, daily_salary)
    # Prior seniority should be ignored for general
    seniority_totals = make_seniority_totals(prior_months=60)

    result = compute_vacation(
        employment_periods=employment_periods,
        work_patterns=work_patterns,
        period_month_records=period_month_records,
        industry="general",
        seniority_totals=seniority_totals,
    )

    # Prior seniority should be ignored for general - seniority should be 1
    assert result.years[0].seniority_years == 1
    assert result.seniority_basis == "employer"


def test_week_type_affects_base_days():
    """5-day vs 6-day week should give different base days."""
    start = date(2023, 1, 1)
    end = date(2023, 12, 31)

    employment_periods = [make_employment_period(start, end)]
    daily_salary = Decimal("450")
    period_month_records = make_period_month_records(start, end, daily_salary)
    seniority_totals = make_seniority_totals(prior_months=0)

    # 5-day week
    work_patterns_5 = [make_work_pattern(start, end, [0, 1, 2, 3, 4])]
    result_5 = compute_vacation(
        employment_periods=employment_periods,
        work_patterns=work_patterns_5,
        period_month_records=period_month_records,
        industry="general",
        seniority_totals=seniority_totals,
    )

    # 6-day week
    work_patterns_6 = [make_work_pattern(start, end, [0, 1, 2, 3, 4, 5])]
    result_6 = compute_vacation(
        employment_periods=employment_periods,
        work_patterns=work_patterns_6,
        period_month_records=period_month_records,
        industry="general",
        seniority_totals=seniority_totals,
    )

    # General industry, seniority 1: 5-day=12, 6-day=14
    assert result_5.years[0].weighted_base_days == Decimal("12")
    assert result_6.years[0].weighted_base_days == Decimal("14")


def test_vacation_disabled_by_toggle():
    """Vacation should not be calculated if disabled by toggle."""
    start = date(2023, 1, 1)
    end = date(2023, 12, 31)

    employment_periods = [make_employment_period(start, end)]
    work_patterns = [make_work_pattern(start, end, [0, 1, 2, 3, 4])]
    period_month_records = make_period_month_records(start, end, Decimal("450"))
    seniority_totals = make_seniority_totals(prior_months=0)

    result = compute_vacation(
        employment_periods=employment_periods,
        work_patterns=work_patterns,
        period_month_records=period_month_records,
        industry="general",
        seniority_totals=seniority_totals,
        right_toggles={"vacation": {"enabled": False}},
    )

    assert result.entitled is False
    assert len(result.years) == 0


def test_partial_year_prorated_by_work_days():
    """Partial years should be prorated by actual work days, not months."""
    # Employment for only 6 months
    start = date(2023, 1, 1)
    end = date(2023, 6, 30)

    employment_periods = [make_employment_period(start, end)]
    # Work pattern needs to cover the full year for proper partial calculation
    full_year_end = date(2023, 12, 31)
    work_patterns = [make_work_pattern(start, full_year_end, [0, 1, 2, 3, 4])]

    daily_salary = Decimal("450")
    period_month_records = make_period_month_records(start, end, daily_salary)
    seniority_totals = make_seniority_totals(prior_months=0)

    result = compute_vacation(
        employment_periods=employment_periods,
        work_patterns=work_patterns,
        period_month_records=period_month_records,
        industry="general",
        seniority_totals=seniority_totals,
    )

    assert result.entitled is True
    assert len(result.years) == 1
    assert result.years[0].is_partial is True
    # partial_fraction should be close to 0.5 (about half year)
    assert result.years[0].partial_fraction is not None
    assert Decimal("0.4") < result.years[0].partial_fraction < Decimal("0.6")


def test_no_intermediate_rounding():
    """No rounding should occur in intermediate calculations."""
    start = date(2023, 1, 1)
    end = date(2023, 12, 31)

    employment_periods = [make_employment_period(start, end)]
    work_patterns = [make_work_pattern(start, end, [0, 1, 2, 3, 4])]

    # Odd daily salary that would show rounding issues
    daily_salary = Decimal("457.33")
    period_month_records = make_period_month_records(start, end, daily_salary)
    seniority_totals = make_seniority_totals(prior_months=0)

    result = compute_vacation(
        employment_periods=employment_periods,
        work_patterns=work_patterns,
        period_month_records=period_month_records,
        industry="general",
        seniority_totals=seniority_totals,
    )

    # Calculate expected value
    # 12 days × 457.33 = 5487.96
    expected_value = Decimal("12") * daily_salary

    # Value should be exact, not rounded
    assert result.grand_total_value == expected_value
