"""Meal allowance (אש"ל) module.

Calculates meal allowance for construction workers who sleep on site.
See docs/skills/meal-allowance/SKILL.md for complete documentation.

Key rules:
- Construction industry only
- Unit is per night, not per day
- Rates are time-varying (lookup from CSV)
"""

from calendar import monthrange
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Callable

from app.ssot import (
    LodgingInput,
    LodgingPeriod,
    EmploymentPeriod,
    MealAllowanceData,
    MealAllowanceMonthlyBreakdown,
    DailyRecord,
    total_nights,
)


def count_work_weeks(start: date, end: date) -> Decimal:
    """Count calendar weeks (as a decimal) that fall within the date range.

    A week is counted proportionally based on how many days fall in the range.
    Uses Mon-Sun week boundaries.

    Args:
        start: Start date (inclusive)
        end: End date (inclusive)

    Returns:
        Decimal number of calendar weeks
    """
    if start > end:
        return Decimal("0")

    # Count total days
    total_days = (end - start).days + 1

    # Simple approximation: each week has 7 days
    # A more accurate method would count actual Mon-Sun boundaries
    weeks = Decimal(total_days) / Decimal("7")

    return weeks


def count_actual_work_weeks(
    start: date,
    end: date,
    daily_records: list[DailyRecord],
) -> Decimal:
    """Count work weeks that have at least one work day in the date range.

    For cyclic patterns, weeks without work days should not count for lodging.

    Args:
        start: Start date (inclusive)
        end: End date (inclusive)
        daily_records: List of daily records with is_work_day flag

    Returns:
        Decimal number of work weeks (weeks with at least one work day)
    """
    if start > end:
        return Decimal("0")

    # Group daily_records by week (Sun-Sat, using ISO week adjusted for Sun start)
    # Week key = (year, week_number) where week starts on Sunday
    def get_week_key(d: date) -> tuple[int, int]:
        # Sunday = 0, so we use (date - days_since_sunday) as week start
        days_since_sunday = (d.weekday() + 1) % 7
        week_start = d - timedelta(days=days_since_sunday)
        return (week_start.year, week_start.month, week_start.day)

    # Find all weeks in the range
    weeks_with_work: set[tuple[int, int, int]] = set()
    all_weeks_in_range: set[tuple[int, int, int]] = set()

    current = start
    while current <= end:
        week_key = get_week_key(current)
        all_weeks_in_range.add(week_key)
        current += timedelta(days=1)

    # Check which weeks have work days
    for record in daily_records:
        if record.date < start or record.date > end:
            continue
        if record.is_work_day:
            week_key = get_week_key(record.date)
            weeks_with_work.add(week_key)

    # For weeks that span the boundaries, we need to pro-rate
    # For simplicity, count full weeks with work
    # A more accurate method would count partial weeks proportionally

    # Count full work weeks
    work_week_count = len(weeks_with_work)

    # Handle partial weeks at boundaries
    # For start boundary: count fraction of first week in range
    # For end boundary: count fraction of last week in range
    first_week_key = get_week_key(start)
    last_week_key = get_week_key(end)

    # If the range spans multiple weeks, handle boundary fractions
    if first_week_key != last_week_key:
        # First week: what fraction is in range?
        days_since_sunday_start = (start.weekday() + 1) % 7
        days_in_first_week = 7 - days_since_sunday_start
        first_week_fraction = Decimal(days_in_first_week) / Decimal(7)

        # Last week: what fraction is in range?
        days_since_sunday_end = (end.weekday() + 1) % 7
        days_in_last_week = days_since_sunday_end + 1
        last_week_fraction = Decimal(days_in_last_week) / Decimal(7)

        # Adjust count: subtract 2 full weeks, add back partial fractions
        if first_week_key in weeks_with_work and last_week_key in weeks_with_work:
            # Both boundary weeks have work
            total_weeks = Decimal(work_week_count - 2) + first_week_fraction + last_week_fraction
        elif first_week_key in weeks_with_work:
            # Only first boundary week has work
            total_weeks = Decimal(work_week_count - 1) + first_week_fraction
        elif last_week_key in weeks_with_work:
            # Only last boundary week has work
            total_weeks = Decimal(work_week_count - 1) + last_week_fraction
        else:
            # Neither boundary week has work (both were subtracted from count already)
            total_weeks = Decimal(work_week_count)
    else:
        # Single week range
        days_in_range = (end - start).days + 1
        if first_week_key in weeks_with_work:
            total_weeks = Decimal(days_in_range) / Decimal(7)
        else:
            total_weeks = Decimal(0)

    return total_weeks


def get_months_in_range(start: date, end: date) -> list[tuple[int, int]]:
    """Get all (year, month) tuples that overlap with the date range.

    Args:
        start: Start date
        end: End date

    Returns:
        List of (year, month) tuples in chronological order
    """
    months = []
    current = date(start.year, start.month, 1)

    while current <= end:
        months.append((current.year, current.month))
        # Move to next month
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)

    return months


def clip_period_to_month(
    period_start: date,
    period_end: date,
    year: int,
    month: int,
) -> tuple[date, date, int]:
    """Clip a period to a specific month.

    Args:
        period_start: Original period start
        period_end: Original period end
        year: Target year
        month: Target month

    Returns:
        Tuple of (clipped_start, clipped_end, days_in_clip)
    """
    _, days_in_month = monthrange(year, month)
    month_start = date(year, month, 1)
    month_end = date(year, month, days_in_month)

    clipped_start = max(period_start, month_start)
    clipped_end = min(period_end, month_end)

    if clipped_start > clipped_end:
        return clipped_start, clipped_end, 0

    days_in_clip = (clipped_end - clipped_start).days + 1
    return clipped_start, clipped_end, days_in_clip


def compute_meal_allowance(
    industry: str,
    lodging_input: LodgingInput | None,
    employment_periods: list[EmploymentPeriod],
    daily_records: list[DailyRecord],
    get_rate: Callable[[date], Decimal],
    right_enabled: bool,
) -> MealAllowanceData:
    """Compute meal allowance (אש"ל).

    Args:
        industry: Industry identifier
        lodging_input: Lodging input with periods
        employment_periods: List of employment periods
        daily_records: List of daily records (for checking work days in weekly patterns)
        get_rate: Function to look up nightly rate by date
        right_enabled: Whether meal allowance right is enabled

    Returns:
        MealAllowanceData with all calculation results
    """
    # Initialize result
    result = MealAllowanceData(industry=industry)

    # Check if right is enabled
    if not right_enabled:
        result.entitled = False
        result.not_entitled_reason = "disabled"
        return result

    # Only construction workers are entitled
    if industry != "construction":
        result.entitled = False
        result.not_entitled_reason = "not_construction"
        return result

    # Check lodging input
    if lodging_input is None or not lodging_input.periods:
        result.entitled = False
        result.not_entitled_reason = "no_lodging_input"
        return result

    # Filter to active periods (pattern_type != "none")
    active_periods = [p for p in lodging_input.periods if p.pattern_type != "none"]
    if not active_periods:
        result.entitled = False
        result.not_entitled_reason = "no_lodging_input"
        return result

    # Get employment date range for clipping
    if not employment_periods:
        result.entitled = False
        result.not_entitled_reason = "no_lodging_input"
        return result

    emp_start = min(ep.start for ep in employment_periods if ep.start)
    emp_end = max(ep.end for ep in employment_periods if ep.end)

    # Monthly aggregation
    monthly_nights: dict[tuple[int, int], Decimal] = defaultdict(Decimal)
    monthly_rates: dict[tuple[int, int], Decimal] = {}

    for period in active_periods:
        if period.start is None or period.end is None:
            continue

        # Clip period to employment range
        period_start = max(period.start, emp_start) if emp_start else period.start
        period_end = min(period.end, emp_end) if emp_end else period.end

        if period_start > period_end:
            continue

        # Get all months that overlap with this period
        months = get_months_in_range(period_start, period_end)

        for year, month in months:
            clipped_start, clipped_end, days_in_clip = clip_period_to_month(
                period_start, period_end, year, month
            )

            if days_in_clip <= 0:
                continue

            _, days_in_full_month = monthrange(year, month)
            month_key = (year, month)

            # Compute nights for this month based on pattern type
            # Use total_nights() to sum all visit groups
            nights_per_unit = total_nights(period)

            if period.pattern_type == "monthly":
                # Pro-rate the monthly nights to the clipped portion
                nights_this_month = Decimal(nights_per_unit) * (
                    Decimal(days_in_clip) / Decimal(days_in_full_month)
                )
            elif period.pattern_type == "weekly":
                # Count actual work weeks (weeks with at least one work day)
                # This handles cyclic patterns where some weeks have no work
                weeks_in_clip = count_actual_work_weeks(clipped_start, clipped_end, daily_records)
                nights_this_month = Decimal(nights_per_unit) * weeks_in_clip
            else:
                nights_this_month = Decimal("0")

            monthly_nights[month_key] += nights_this_month

            # Get rate for this month (use first day of lodging in this month)
            if month_key not in monthly_rates:
                try:
                    monthly_rates[month_key] = get_rate(clipped_start)
                except ValueError:
                    # No rate found, use 0
                    monthly_rates[month_key] = Decimal("0")

    # Build monthly breakdown
    monthly_breakdown: list[MealAllowanceMonthlyBreakdown] = []
    grand_total_nights = Decimal("0")
    grand_total_value = Decimal("0")

    for month_key in sorted(monthly_nights.keys()):
        nights = monthly_nights[month_key]
        rate = monthly_rates.get(month_key, Decimal("0"))
        claim_amount = nights * rate

        monthly_breakdown.append(MealAllowanceMonthlyBreakdown(
            month=month_key,
            nights=nights,
            nightly_rate=rate,
            claim_amount=claim_amount,
        ))

        grand_total_nights += nights
        grand_total_value += claim_amount

    result.entitled = True
    result.not_entitled_reason = None
    result.monthly_breakdown = monthly_breakdown
    result.grand_total_nights = grand_total_nights
    result.grand_total_value = grand_total_value
    result.claim_before_deductions = grand_total_value

    return result
