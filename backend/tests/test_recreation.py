"""Tests for recreation pay (דמי הבראה) calculation.

Test cases from docs/skills/recreation/SKILL.md
"""

import pytest
from datetime import date
from decimal import Decimal

from app.ssot import EmploymentPeriod, MonthAggregate, Duration
from app.modules.recreation import compute_recreation


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


def make_month_aggregates(start: date, end: date, job_scope: Decimal = Decimal("1.0")) -> list[MonthAggregate]:
    """Create month aggregates for each month in the range with given job_scope."""
    aggregates = []
    current = date(start.year, start.month, 1)
    while current <= end:
        aggregates.append(MonthAggregate(
            month=(current.year, current.month),
            job_scope=job_scope,
            raw_scope=job_scope,
            full_time_hours_base=Decimal("182"),
        ))
        # Move to next month
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)
    return aggregates


def mock_get_recreation_days(industry: str, seniority_years: int) -> int:
    """Mock function for recreation days lookup.

    Tables start from 1 (seniority after completing first year).
    """
    tables = {
        "general": [
            (1, 1, 5),
            (2, 3, 6),
            (4, 10, 7),
            (11, 15, 8),
            (16, 19, 9),
            (20, 999, 10),
        ],
        "construction": [
            (1, 2, 6),
            (3, 4, 8),
            (5, 10, 9),
            (11, 15, 10),
            (16, 19, 11),
            (20, 999, 12),
        ],
        "agriculture": [
            (1, 7, 7),
            (8, 8, 8),
            (9, 9, 9),
            (10, 999, 10),
        ],
        "cleaning": [
            (1, 3, 7),
            (4, 10, 9),
            (11, 15, 10),
            (16, 19, 11),
            (20, 24, 12),
            (25, 999, 13),
        ],
    }

    table = tables.get(industry, tables["general"])
    for min_y, max_y, days in table:
        if min_y <= seniority_years <= max_y:
            return days

    # Fallback to general
    for min_y, max_y, days in tables["general"]:
        if min_y <= seniority_years <= max_y:
            return days

    raise ValueError(f"No recreation days for {industry}, {seniority_years}")


def mock_get_recreation_day_value(target_date: date, industry: str) -> tuple[Decimal, date]:
    """Mock function for recreation day value lookup."""
    # Cleaning has fixed value of 423
    if industry == "cleaning":
        return Decimal("423.00"), date(2018, 7, 1)

    # Others: 378 before 2023-07-01, 418 after
    if target_date >= date(2023, 7, 1):
        return Decimal("418.00"), date(2023, 7, 1)
    else:
        return Decimal("378.00"), date(2018, 7, 1)


# =============================================================================
# Test Case 1: 3 full years, general industry
# =============================================================================

def test_case_1_three_full_years_general():
    """
    employment: 01.01.2021 – 01.01.2024 (3 שנים מלאות)
    industry: general
    seniority at start: 0
    scope: 1.0 כל התקופה

    year 1: seniority=1 → days=5, fraction=1.0, scope=1.0 → 5 ימים
    year 2: seniority=2 → days=6, fraction=1.0, scope=1.0 → 6 ימים
    year 3: seniority=3 → days=6, fraction=1.0, scope=1.0 → 6 ימים

    grand_total_days = 17.0
    """
    start = date(2021, 1, 1)
    end = date(2024, 1, 1)  # Exactly 3 years

    employment_periods = [make_employment_period(start, end)]
    month_aggregates = make_month_aggregates(start, end, Decimal("1.0"))

    result = compute_recreation(
        employment_periods=employment_periods,
        total_seniority_years=Decimal("0"),
        month_aggregates=month_aggregates,
        industry="general",
        get_recreation_days=mock_get_recreation_days,
        get_recreation_day_value=mock_get_recreation_day_value,
    )

    assert result.entitled is True
    assert result.not_entitled_reason is None
    assert result.industry == "general"
    assert len(result.years) == 3

    # Year 1: seniority=1 → days=5
    assert result.years[0].year_number == 1
    assert result.years[0].seniority_years == 1
    assert result.years[0].base_days == 5
    assert result.years[0].is_partial is False
    assert result.years[0].entitled_days == Decimal("5")

    # Year 2: seniority=2 → days=6
    assert result.years[1].year_number == 2
    assert result.years[1].seniority_years == 2
    assert result.years[1].base_days == 6
    assert result.years[1].entitled_days == Decimal("6")

    # Year 3: seniority=3 → days=6
    assert result.years[2].year_number == 3
    assert result.years[2].seniority_years == 3
    assert result.years[2].base_days == 6
    assert result.years[2].entitled_days == Decimal("6")

    assert result.grand_total_days == Decimal("17")
    # Year 1 ends 2021-12-31 -> 378, Year 2 ends 2022-12-31 -> 378, Year 3 ends 2023-12-31 -> 418
    # So: 5*378 + 6*378 + 6*418 = 1890 + 2268 + 2508 = 6666
    expected_value = Decimal("5") * Decimal("378") + Decimal("6") * Decimal("378") + Decimal("6") * Decimal("418")
    assert result.grand_total_value == expected_value


# =============================================================================
# Test Case 2: Less than a year - not entitled
# =============================================================================

def test_case_2_less_than_year_not_entitled():
    """
    employment: 01.01.2024 – 01.06.2024 (5 חודשים)
    entitled = False
    grand_total_days  = 0
    grand_total_value = 0
    """
    start = date(2024, 1, 1)
    end = date(2024, 6, 1)  # About 5 months

    employment_periods = [make_employment_period(start, end)]
    month_aggregates = make_month_aggregates(start, end)

    result = compute_recreation(
        employment_periods=employment_periods,
        total_seniority_years=Decimal("0"),
        month_aggregates=month_aggregates,
        industry="general",
        get_recreation_days=mock_get_recreation_days,
        get_recreation_day_value=mock_get_recreation_day_value,
    )

    assert result.entitled is False
    assert result.not_entitled_reason == "תקופת העסקה פחות משנה"
    assert result.grand_total_days == Decimal("0")
    assert result.grand_total_value == Decimal("0")
    assert len(result.years) == 0


# =============================================================================
# Test Case 3: 18 months (1 year + 6 months partial)
# =============================================================================

def test_case_3_eighteen_months_partial_year():
    """
    employment: 01.01.2023 – 01.07.2024 (18 חודשים)
    industry: general
    seniority at start: 0
    scope: 1.0

    year 1: seniority=1 → days=5, fraction=1.0, scope=1.0 → 5 ימים
    year 2: seniority=2 → days=6, fraction=6/12=0.5, scope=1.0 → 3 ימים

    grand_total_days = 8.0
    """
    start = date(2023, 1, 1)
    end = date(2024, 7, 1)  # 18 months

    employment_periods = [make_employment_period(start, end)]
    month_aggregates = make_month_aggregates(start, end, Decimal("1.0"))

    result = compute_recreation(
        employment_periods=employment_periods,
        total_seniority_years=Decimal("0"),
        month_aggregates=month_aggregates,
        industry="general",
        get_recreation_days=mock_get_recreation_days,
        get_recreation_day_value=mock_get_recreation_day_value,
    )

    assert result.entitled is True
    assert len(result.years) == 2

    # Year 1: full year, seniority=1 → days=5
    assert result.years[0].year_number == 1
    assert result.years[0].seniority_years == 1
    assert result.years[0].base_days == 5
    assert result.years[0].is_partial is False
    assert result.years[0].entitled_days == Decimal("5")

    # Year 2: partial (6 months), seniority=2 → days=6, fraction=0.5
    assert result.years[1].year_number == 2
    assert result.years[1].seniority_years == 2
    assert result.years[1].base_days == 6
    assert result.years[1].is_partial is True
    assert result.years[1].partial_fraction == Decimal("0.5")
    assert result.years[1].entitled_days == Decimal("3")

    assert result.grand_total_days == Decimal("8")
    # Year 1 ends 2023-12-31 -> 418, Year 2 ends 2024-07-01 -> 418
    expected_value = Decimal("5") * Decimal("418") + Decimal("3") * Decimal("418")
    assert result.grand_total_value == expected_value


# =============================================================================
# Test Case 4: Construction industry with existing seniority
# =============================================================================

def test_case_4_construction_with_seniority():
    """
    employment: 01.01.2022 – 01.01.2024 (2 שנים)
    industry: construction
    seniority at start: 5 (5 שנות ותק ענפי לפני תחילת עסקה)
    scope: 0.5

    year 1: seniority=6 → days=9 (6 נמצא בטווח 5–10), fraction=1.0, scope=0.5 → 4.5 ימים
    year 2: seniority=7 → days=9 (7 נמצא בטווח 5–10), fraction=1.0, scope=0.5 → 4.5 ימים

    grand_total_days = 9.0
    """
    start = date(2022, 1, 1)
    end = date(2024, 1, 1)  # 2 years

    employment_periods = [make_employment_period(start, end)]
    month_aggregates = make_month_aggregates(start, end, Decimal("0.5"))

    result = compute_recreation(
        employment_periods=employment_periods,
        total_seniority_years=Decimal("5"),  # 5 years seniority at start
        month_aggregates=month_aggregates,
        industry="construction",
        get_recreation_days=mock_get_recreation_days,
        get_recreation_day_value=mock_get_recreation_day_value,
    )

    assert result.entitled is True
    assert result.industry == "construction"
    assert len(result.years) == 2

    # Year 1: seniority=6 → days=9 (construction table: 5-10 = 9)
    assert result.years[0].year_number == 1
    assert result.years[0].seniority_years == 6
    assert result.years[0].base_days == 9
    assert result.years[0].avg_scope == Decimal("0.5")
    assert result.years[0].entitled_days == Decimal("4.5")

    # Year 2: seniority=7 → days=9
    assert result.years[1].year_number == 2
    assert result.years[1].seniority_years == 7
    assert result.years[1].base_days == 9
    assert result.years[1].avg_scope == Decimal("0.5")
    assert result.years[1].entitled_days == Decimal("4.5")

    assert result.grand_total_days == Decimal("9.0")
    # Year 1 ends 2023-01-01 -> 378, Year 2 ends 2024-01-01 -> 418
    expected_value = Decimal("4.5") * Decimal("378") + Decimal("4.5") * Decimal("418")
    assert result.grand_total_value == expected_value


# =============================================================================
# Test Case 5: Exactly 1 year (boundary case)
# =============================================================================

def test_case_5_exactly_one_year_boundary():
    """
    employment: 01.01.2023 – 01.01.2024 (365 ימים מלאים — שנה אחת בדיוק)
    entitled = True  (השלים שנה, לא פחות)

    year 1: שנה מלאה → fraction = 1.0
    """
    start = date(2023, 1, 1)
    end = date(2024, 1, 1)  # Exactly 1 year (366 days including both ends)

    employment_periods = [make_employment_period(start, end)]
    month_aggregates = make_month_aggregates(start, end, Decimal("1.0"))

    result = compute_recreation(
        employment_periods=employment_periods,
        total_seniority_years=Decimal("0"),
        month_aggregates=month_aggregates,
        industry="general",
        get_recreation_days=mock_get_recreation_days,
        get_recreation_day_value=mock_get_recreation_day_value,
    )

    assert result.entitled is True
    assert len(result.years) == 1

    # Year 1: full year, seniority=1
    assert result.years[0].year_number == 1
    assert result.years[0].is_partial is False
    assert result.years[0].seniority_years == 1
    assert result.years[0].base_days == 5
    assert result.years[0].entitled_days == Decimal("5")

    assert result.grand_total_days == Decimal("5")


# =============================================================================
# Anti-pattern tests
# =============================================================================

def test_anti_pattern_seniority_floored():
    """Seniority for table lookup must be floored to integer."""
    start = date(2023, 1, 1)
    end = date(2024, 7, 1)

    employment_periods = [make_employment_period(start, end)]
    month_aggregates = make_month_aggregates(start, end)

    # 1.5 years seniority - should floor to 1
    result = compute_recreation(
        employment_periods=employment_periods,
        total_seniority_years=Decimal("1.5"),
        month_aggregates=month_aggregates,
        industry="general",
        get_recreation_days=mock_get_recreation_days,
        get_recreation_day_value=mock_get_recreation_day_value,
    )

    # Year 1: seniority = floor(1.5) + 1 = 2 → 6 days (seniority 2 is in range 2-3)
    assert result.years[0].seniority_years == 2
    assert result.years[0].base_days == 6


def test_anti_pattern_per_year_day_value():
    """Each employment year gets its own day value based on year_end."""
    start = date(2022, 1, 1)
    end = date(2024, 1, 1)

    employment_periods = [make_employment_period(start, end)]
    month_aggregates = make_month_aggregates(start, end)

    result = compute_recreation(
        employment_periods=employment_periods,
        total_seniority_years=Decimal("0"),
        month_aggregates=month_aggregates,
        industry="general",
        get_recreation_days=mock_get_recreation_days,
        get_recreation_day_value=mock_get_recreation_day_value,
    )

    # Year 1 ends 2023-01-01 (before 2023-07-01) -> 378
    assert result.years[0].day_value == Decimal("378")
    # Year 2 ends 2024-01-01 (after 2023-07-01) -> 418
    assert result.years[1].day_value == Decimal("418")


def test_industry_fallback_to_general():
    """If industry not found, fall back to general."""
    start = date(2023, 1, 1)
    end = date(2024, 1, 1)

    employment_periods = [make_employment_period(start, end)]
    month_aggregates = make_month_aggregates(start, end)

    result = compute_recreation(
        employment_periods=employment_periods,
        total_seniority_years=Decimal("0"),
        month_aggregates=month_aggregates,
        industry="unknown_industry",  # Not in table
        get_recreation_days=mock_get_recreation_days,
        get_recreation_day_value=mock_get_recreation_day_value,
    )

    assert result.entitled is True
    # Should fall back to general table
    assert result.years[0].base_days == 5  # general: seniority 1 -> 5 days


def test_no_intermediate_rounding():
    """No rounding in intermediate calculations."""
    start = date(2023, 1, 1)
    end = date(2024, 7, 1)

    employment_periods = [make_employment_period(start, end)]
    # 0.75 scope
    month_aggregates = make_month_aggregates(start, end, Decimal("0.75"))

    result = compute_recreation(
        employment_periods=employment_periods,
        total_seniority_years=Decimal("0"),
        month_aggregates=month_aggregates,
        industry="general",
        get_recreation_days=mock_get_recreation_days,
        get_recreation_day_value=mock_get_recreation_day_value,
    )

    # Year 1: seniority=1 → 5 days, 5 * 1.0 * 0.75 = 3.75
    assert result.years[0].entitled_days == Decimal("3.75")
    # Year 2: seniority=2 → 6 days, 6 * 0.5 * 0.75 = 2.25
    assert result.years[1].entitled_days == Decimal("2.25")
    # Total: 6.0 (no rounding)
    assert result.grand_total_days == Decimal("6")
