"""Recreation pay (דמי הבראה) calculation module.

Calculates recreation pay entitlement per employment year.
See docs/skills/recreation/SKILL.md for complete documentation.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Callable

from app.ssot import (
    RecreationResult,
    RecreationYearData,
    EmploymentPeriod,
    MonthAggregate,
)


@dataclass
class EmploymentYear:
    """Internal representation of an employment year."""
    year_number: int
    start: date
    end: date
    is_partial: bool
    whole_months: int  # Number of whole months (for partial year)


def _add_years(d: date, years: int) -> date:
    """Add years to a date, handling leap years."""
    try:
        return d.replace(year=d.year + years)
    except ValueError:
        # Feb 29 in a non-leap year -> Feb 28
        return d.replace(year=d.year + years, day=28)


def _count_whole_months(start: date, end: date, employment_start_day: int) -> int:
    """Count whole months from start to end.

    A month counts only if fully completed from the day-of-month of employment start.
    This matches the seniority module's month-counting logic.
    """
    if end < start:
        return 0

    months = 0
    cursor_year = start.year
    cursor_month = start.month

    while True:
        # The "completion date" for this month is the employment_start_day
        # If employment started on day 15, the month completes on day 15 of the next month

        # Move to next month
        if cursor_month == 12:
            next_year = cursor_year + 1
            next_month = 1
        else:
            next_year = cursor_year
            next_month = cursor_month + 1

        # Find the completion date in the next month
        try:
            completion_date = date(next_year, next_month, employment_start_day)
        except ValueError:
            # Day doesn't exist in this month (e.g., 31 in a 30-day month)
            # Use last day of month
            if next_month == 12:
                completion_date = date(next_year + 1, 1, 1) - timedelta(days=1)
            else:
                completion_date = date(next_year, next_month + 1, 1) - timedelta(days=1)

        # A month is complete if we reach the completion date (exclusive - need to complete the day before)
        # Actually, the month is complete when we reach or pass the completion date
        if completion_date <= end:
            months += 1
            cursor_year = next_year
            cursor_month = next_month
        else:
            break

        # Safety check to avoid infinite loop
        if cursor_year > end.year + 1:
            break

    return months


def _compute_employment_years(
    employment_start: date,
    employment_end: date,
) -> list[EmploymentYear]:
    """Compute employment years from start to end date.

    Employment years are defined from the employment start date:
    - Year 1: [start, start + 1 year)
    - Year 2: [start + 1 year, start + 2 years)
    - ...
    - Year N: [start + (N−1) years, min(end, start + N years))

    Note: A partial year with 0 whole months is not included.
    """
    years = []
    year_number = 1
    current_start = employment_start

    while current_start <= employment_end:
        # Calculate the ideal end of this employment year
        year_end_ideal = _add_years(current_start, 1) - timedelta(days=1)

        # Actual end is the minimum of ideal end and employment end
        year_end_actual = min(year_end_ideal, employment_end)

        # Check if this is a partial year
        is_partial = year_end_actual < year_end_ideal

        # Count whole months for partial year
        whole_months = 12  # Full year
        if is_partial:
            whole_months = _count_whole_months(
                current_start,
                year_end_actual,
                employment_start.day
            )
            # Skip years with 0 whole months (e.g., employment ends on anniversary)
            if whole_months == 0:
                break

        years.append(EmploymentYear(
            year_number=year_number,
            start=current_start,
            end=year_end_actual,
            is_partial=is_partial,
            whole_months=whole_months,
        ))

        # Move to next year
        year_number += 1
        current_start = _add_years(current_start, 1)

    return years


def _compute_avg_scope_for_year(
    year_start: date,
    year_end: date,
    month_aggregates: list[MonthAggregate],
) -> Decimal:
    """Compute weighted average job scope for an employment year.

    Uses month_aggregates to get job_scope per month, weighted by the
    fraction of each month that falls within the employment year.
    """
    if not month_aggregates:
        return Decimal("1")  # Default to full scope if no data

    total_weight = Decimal("0")
    weighted_sum = Decimal("0")

    for ma in month_aggregates:
        year, month = ma.month

        # Calculate month boundaries
        month_start = date(year, month, 1)
        if month == 12:
            month_end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(year, month + 1, 1) - timedelta(days=1)

        # Calculate overlap with employment year
        overlap_start = max(month_start, year_start)
        overlap_end = min(month_end, year_end)

        if overlap_start <= overlap_end:
            # Calculate weight (days of overlap / days in month)
            overlap_days = (overlap_end - overlap_start).days + 1
            month_days = (month_end - month_start).days + 1
            weight = Decimal(overlap_days) / Decimal(month_days)

            total_weight += weight
            weighted_sum += weight * ma.job_scope

    if total_weight == 0:
        return Decimal("1")  # Default to full scope if no overlap

    return weighted_sum / total_weight


def compute_recreation(
    employment_periods: list[EmploymentPeriod],
    total_seniority_years: Decimal,
    month_aggregates: list[MonthAggregate],
    industry: str,
    get_recreation_days: Callable[[str, int], int],
    get_recreation_day_value: Callable[[date, str], tuple[Decimal, date]],
) -> RecreationResult:
    """Compute recreation pay entitlement.

    Args:
        employment_periods: List of employment periods
        total_seniority_years: Total industry seniority at employment start (decimal)
        month_aggregates: Monthly aggregates with job_scope
        industry: Industry identifier
        get_recreation_days: Function to look up recreation days by industry + seniority
        get_recreation_day_value: Function to look up day value by date + industry

    Returns:
        RecreationResult with all calculation details
    """
    result = RecreationResult(industry=industry)

    if not employment_periods:
        result.entitled = False
        result.not_entitled_reason = "אין תקופות העסקה"
        return result

    # Get employment boundaries
    employment_start = min(ep.start for ep in employment_periods)
    employment_end = max(ep.end for ep in employment_periods)

    # Step 1: Check waiting period (1 full year)
    total_days = (employment_end - employment_start).days + 1
    if total_days < 365:
        result.entitled = False
        result.not_entitled_reason = "תקופת העסקה פחות משנה"
        return result

    result.entitled = True

    # Step 2: Define employment years
    employment_years = _compute_employment_years(employment_start, employment_end)

    # Step 3-8: Calculate for each employment year
    grand_total_days = Decimal("0")
    grand_total_value = Decimal("0")

    # Seniority at employment start (floored to integer)
    seniority_at_start = int(total_seniority_years)

    # Track if we fell back to general industry
    industry_fallback_used = False

    for emp_year in employment_years:
        # Step 3: Seniority for this year
        # Worker completing year Y has seniority Y (not Y-1)
        seniority_for_year = seniority_at_start + emp_year.year_number

        # Step 4: Table lookup for recreation days
        try:
            base_days = get_recreation_days(industry, seniority_for_year)
        except ValueError:
            # Fall back to general
            base_days = get_recreation_days("general", seniority_for_year)
            industry_fallback_used = True

        # Step 5: Calculate average scope for this year
        avg_scope = _compute_avg_scope_for_year(
            emp_year.start,
            emp_year.end,
            month_aggregates,
        )

        # Step 6: Get day value for end of this year
        day_value, day_value_effective_date = get_recreation_day_value(emp_year.end, industry)

        # Step 7: Calculate entitled days and value
        if emp_year.is_partial:
            partial_fraction = Decimal(emp_year.whole_months) / Decimal("12")
        else:
            partial_fraction = Decimal("1")

        entitled_days = Decimal(base_days) * partial_fraction * avg_scope
        entitled_value = entitled_days * day_value

        # Add to totals
        grand_total_days += entitled_days
        grand_total_value += entitled_value

        # Create year data
        year_data = RecreationYearData(
            year_number=emp_year.year_number,
            year_start=emp_year.start,
            year_end=emp_year.end,
            is_partial=emp_year.is_partial,
            partial_fraction=partial_fraction if emp_year.is_partial else None,
            seniority_years=seniority_for_year,
            base_days=base_days,
            avg_scope=avg_scope,
            day_value=day_value,
            day_value_effective_date=day_value_effective_date,
            entitled_days=entitled_days,
            entitled_value=entitled_value,
        )
        result.years.append(year_data)

    result.industry_fallback_used = industry_fallback_used
    result.grand_total_days = grand_total_days
    result.grand_total_value = grand_total_value

    return result
