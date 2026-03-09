"""Travel allowance (דמי נסיעות) module.

Calculates travel allowance based on work days, lodging patterns, and industry rates.
See docs/skills/travel/SKILL.md for complete documentation.

Updated to use new period-based LodgingInput structure.
New formula: travel_days = work_days + visits - nights
"""

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Callable

from app.ssot import (
    Week,
    Shift,
    LodgingInput,
    LodgingPeriod,
    TravelData,
    TravelWeekDetail,
    TravelMonthlyBreakdown,
)


def find_active_lodging_period(
    period_start: date,
    period_end: date,
    lodging_input: LodgingInput | None,
) -> LodgingPeriod | None:
    """Find the lodging period that covers the given date range.

    Args:
        period_start: Start date of the period to check
        period_end: End date of the period to check
        lodging_input: The lodging input with periods

    Returns:
        The active LodgingPeriod or None if no matching period
    """
    if lodging_input is None or not lodging_input.periods:
        return None

    for period in lodging_input.periods:
        if period.start is None or period.end is None:
            continue
        # Check if the period overlaps with the date range
        if period.start <= period_end and period.end >= period_start:
            return period

    return None


def compute_weekly_travel_days(work_days: int, active_period: LodgingPeriod | None) -> int:
    """Compute travel days for a week using the new formula.

    Formula: travel_days = work_days + visits - nights

    Args:
        work_days: Number of distinct work days in the week
        active_period: Active lodging period (or None for no lodging)

    Returns:
        Number of travel days
    """
    if work_days == 0:
        return 0

    if active_period is None or active_period.pattern_type == "none":
        return work_days

    if active_period.pattern_type == "weekly":
        nights_rounded = round(active_period.nights_per_unit)
        visits_rounded = max(1, round(active_period.visits_per_unit)) if nights_rounded > 0 else 0
        travel_days = work_days + visits_rounded - nights_rounded
        return max(0, travel_days)

    # For monthly pattern, we compute at month level, so return work_days here
    # The monthly computation will handle the adjustment
    return work_days


def get_work_days_in_week(week: Week, shifts: list[Shift]) -> int:
    """Count distinct work days in a week.

    Args:
        week: Week object
        shifts: All shifts in the system

    Returns:
        Number of distinct calendar days with at least one shift in this week
    """
    week_shifts = [s for s in shifts if s.assigned_week == week.id]
    distinct_days = set(s.assigned_day for s in week_shifts if s.assigned_day is not None)
    return len(distinct_days)


def compute_travel(
    industry: str,
    travel_distance_km: Decimal | None,
    lodging_input: LodgingInput | None,
    weeks: list[Week],
    shifts: list[Shift],
    get_travel_rate: Callable[[str, Decimal | None, date], Decimal],
    right_enabled: bool,
) -> TravelData:
    """Compute travel allowance.

    Args:
        industry: Industry identifier
        travel_distance_km: Distance in km (construction only)
        lodging_input: Lodging pattern input (construction only)
        weeks: List of Week objects from OT pipeline
        shifts: List of Shift objects from OT pipeline
        get_travel_rate: Function to look up travel rate
        right_enabled: Whether travel right is enabled

    Returns:
        TravelData with all calculation results
    """
    # Initialize result
    result = TravelData(industry=industry)

    # If right is disabled, return empty result
    if not right_enabled:
        return result

    # Determine distance tier (construction only)
    if industry == "construction":
        result.distance_km = travel_distance_km
        if travel_distance_km is not None and travel_distance_km >= 40:
            result.distance_tier = "far"
        else:
            result.distance_tier = "standard"
    else:
        result.distance_tier = None

    # Handle lodging input
    # Lodging only applies to construction workers
    has_lodging = False
    lodging_periods_count = 0

    if industry == "construction" and lodging_input is not None and lodging_input.periods:
        # Count periods with pattern_type != "none"
        active_periods = [p for p in lodging_input.periods if p.pattern_type != "none"]
        lodging_periods_count = len(active_periods)
        has_lodging = lodging_periods_count > 0

    result.has_lodging = has_lodging
    result.lodging_periods_count = lodging_periods_count

    # Filter to weeks with actual work
    work_weeks = []
    for week in weeks:
        work_days = get_work_days_in_week(week, shifts)
        if work_days > 0:
            work_weeks.append((week, work_days))

    weekly_details: list[TravelWeekDetail] = []
    monthly_aggregates: dict[tuple[int, int], dict] = defaultdict(
        lambda: {"travel_days": 0, "value": Decimal("0"), "work_days": 0}
    )

    # Get first rate to use as the "effective rate" for display
    if work_weeks:
        first_week = work_weeks[0][0]
        if first_week.start_date:
            result.daily_rate = get_travel_rate(industry, travel_distance_km, first_week.start_date)

    # Track monthly lodging periods for monthly pattern handling
    monthly_lodging_periods: dict[tuple[int, int], LodgingPeriod | None] = {}

    for week, work_days in work_weeks:
        if week.start_date is None:
            continue

        # Find active lodging period for this week
        active_period = None
        if has_lodging and lodging_input is not None:
            active_period = find_active_lodging_period(
                week.start_date,
                week.end_date or week.start_date,
                lodging_input
            )

        # Determine week pattern string for display
        if active_period is None or active_period.pattern_type == "none":
            week_pattern = "no_lodging"
        elif active_period.pattern_type == "weekly":
            week_pattern = "weekly_lodging"
        elif active_period.pattern_type == "monthly":
            week_pattern = "monthly_lodging"
        else:
            week_pattern = "no_lodging"

        # Compute travel days for weekly pattern
        if active_period is not None and active_period.pattern_type == "monthly":
            # For monthly pattern, accumulate work_days and compute at month level
            travel_days = work_days  # Temporary, will be adjusted at month level
        else:
            travel_days = compute_weekly_travel_days(work_days, active_period)

        # Get rate for this week
        daily_rate = get_travel_rate(industry, travel_distance_km, week.start_date)

        # Compute value (for weekly pattern)
        if active_period is not None and active_period.pattern_type == "monthly":
            # Will be computed at month level
            week_travel_value = Decimal(travel_days) * daily_rate
        else:
            week_travel_value = Decimal(travel_days) * daily_rate

        # Get effective period from first shift of this week
        week_shifts = [s for s in shifts if s.assigned_week == week.id]
        effective_period_id = week_shifts[0].effective_period_id if week_shifts else ""

        # Create weekly detail
        detail = TravelWeekDetail(
            week_start=week.start_date,
            week_end=week.end_date,
            effective_period_id=effective_period_id,
            work_days=work_days,
            cycle_position=None,  # No longer using cycle
            week_pattern=week_pattern,
            travel_days=travel_days,
            daily_rate=daily_rate,
            week_travel_value=week_travel_value,
        )
        weekly_details.append(detail)

        # Aggregate by month (week belongs to month of start_date)
        month_key = (week.start_date.year, week.start_date.month)
        monthly_aggregates[month_key]["work_days"] += work_days

        # Track lodging period for this month (for monthly pattern)
        if active_period is not None and active_period.pattern_type == "monthly":
            monthly_lodging_periods[month_key] = active_period
            # Store work_days for later adjustment
        else:
            monthly_aggregates[month_key]["travel_days"] += travel_days
            monthly_aggregates[month_key]["value"] += week_travel_value

    # Now handle monthly pattern adjustments
    for month_key, period in monthly_lodging_periods.items():
        if period is None:
            continue
        month_work_days = monthly_aggregates[month_key]["work_days"]

        # Apply monthly formula: travel_days = work_days + visits - nights
        nights = period.nights_per_unit
        visits = period.visits_per_unit
        travel_days_month = max(0, month_work_days + visits - nights)

        # Get rate for this month (use first day of month)
        month_date = date(month_key[0], month_key[1], 1)
        daily_rate = get_travel_rate(industry, travel_distance_km, month_date)

        monthly_aggregates[month_key]["travel_days"] = travel_days_month
        monthly_aggregates[month_key]["value"] = Decimal(travel_days_month) * daily_rate

        # Update weekly details for this month to reflect adjusted values
        for detail in weekly_details:
            if detail.week_start and (detail.week_start.year, detail.week_start.month) == month_key:
                if detail.week_pattern == "monthly_lodging":
                    # Pro-rate the travel days based on work day proportion
                    if month_work_days > 0:
                        proportion = Decimal(detail.work_days) / Decimal(month_work_days)
                        detail.travel_days = int(round(travel_days_month * proportion))
                        detail.week_travel_value = Decimal(detail.travel_days) * detail.daily_rate

    # Build monthly breakdown
    monthly_breakdown = []
    for month_key in sorted(monthly_aggregates.keys()):
        agg = monthly_aggregates[month_key]
        if agg["travel_days"] > 0 or agg["value"] > 0:
            monthly_breakdown.append(TravelMonthlyBreakdown(
                month=month_key,
                travel_days=agg["travel_days"],
                claim_amount=agg["value"],
            ))

    # Compute totals from monthly aggregates
    grand_total_travel_days = sum(agg["travel_days"] for agg in monthly_aggregates.values())
    grand_total_value = sum(agg["value"] for agg in monthly_aggregates.values())

    result.weekly_detail = weekly_details
    result.monthly_breakdown = monthly_breakdown
    result.grand_total_travel_days = grand_total_travel_days
    result.grand_total_value = grand_total_value
    result.claim_before_deductions = grand_total_value

    return result
