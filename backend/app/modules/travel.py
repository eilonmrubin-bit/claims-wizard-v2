"""Travel allowance (דמי נסיעות) module.

Calculates travel allowance based on work days, lodging patterns, and industry rates.
See docs/skills/travel/SKILL.md for complete documentation.

Updated to use new period-based LodgingInput structure.
Formula: travel_days = max(2 * visits, work_days + visits - nights)
Floor is 2 × visits because every visit has departure + return.
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
    total_nights,
    total_visits,
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
    """Compute travel days for a week using the corrected formula.

    Formula: travel_days = max(2 * visits, work_days + visits - nights)

    The floor is 2 × visits (not 0) because every visit has departure + return.

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
        nights = total_nights(active_period)
        visits = total_visits(active_period)
        # Floor is 2 × visits: every visit has departure + return = 2 travel days minimum
        return max(2 * visits, work_days + visits - nights)

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

    # For monthly lodging patterns: count work days by calendar date, NOT by week attribution
    # Build a mapping of month -> set of distinct work days (for monthly pattern only)
    monthly_work_days_by_calendar: dict[tuple[int, int], set[date]] = defaultdict(set)
    for week, _ in work_weeks:
        if week.start_date is None:
            continue
        week_shifts = [s for s in shifts if s.assigned_week == week.id]
        for shift in week_shifts:
            if shift.assigned_day is not None:
                day = shift.assigned_day
                month_key = (day.year, day.month)
                monthly_work_days_by_calendar[month_key].add(day)

    # Pre-populate monthly_lodging_periods for all months with calendar work days
    # This handles cross-month weeks (e.g., week starting Jan 30 with shifts in Feb)
    if has_lodging and lodging_input is not None:
        from calendar import monthrange
        for month_key in monthly_work_days_by_calendar.keys():
            month_start = date(month_key[0], month_key[1], 1)
            _, last_day = monthrange(month_key[0], month_key[1])
            month_end = date(month_key[0], month_key[1], last_day)
            active_period = find_active_lodging_period(month_start, month_end, lodging_input)
            if active_period is not None and active_period.pattern_type == "monthly":
                monthly_lodging_periods[month_key] = active_period
                # Initialize monthly aggregates for this month
                if month_key not in monthly_aggregates:
                    monthly_aggregates[month_key]["travel_days"] = 0
                    monthly_aggregates[month_key]["value"] = Decimal("0")
                    monthly_aggregates[month_key]["work_days"] = 0

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

        # Track lodging period for this month (for monthly pattern)
        if active_period is not None and active_period.pattern_type == "monthly":
            # For monthly pattern, use week.start_date month for tracking
            month_key = (week.start_date.year, week.start_date.month)
            monthly_aggregates[month_key]["work_days"] += work_days
            monthly_lodging_periods[month_key] = active_period
        else:
            # For weekly pattern: split week proportionally across months
            # Group this week's shifts by calendar month
            week_shifts_by_month: dict[tuple[int, int], int] = defaultdict(int)
            for shift in week_shifts:
                if shift.assigned_day is not None:
                    shift_month = (shift.assigned_day.year, shift.assigned_day.month)
                    week_shifts_by_month[shift_month] += 1

            # Distribute travel_days and value proportionally
            for month_key, shifts_in_month in week_shifts_by_month.items():
                if work_days > 0:
                    fraction = Decimal(shifts_in_month) / Decimal(work_days)
                    monthly_aggregates[month_key]["work_days"] += shifts_in_month
                    monthly_aggregates[month_key]["travel_days"] += Decimal(travel_days) * fraction
                    monthly_aggregates[month_key]["value"] += week_travel_value * fraction

    # Now handle monthly pattern adjustments
    for month_key, period in monthly_lodging_periods.items():
        if period is None:
            continue
        # CRITICAL: Use calendar-based work days, NOT week-attributed work days
        # A day belongs to month M if its calendar date falls within M, regardless of week attribution
        month_work_days = len(monthly_work_days_by_calendar.get(month_key, set()))

        # Apply monthly formula: travel_days = max(2 * visits, work_days + visits - nights)
        # Floor is 2 × visits: every visit has departure + return = 2 travel days minimum
        nights = total_nights(period)
        visits = total_visits(period)
        travel_days_month = max(2 * visits, month_work_days + visits - nights)

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
    # Note: travel_days may be Decimal (from proportional split) - round to int for storage
    monthly_breakdown = []
    for month_key in sorted(monthly_aggregates.keys()):
        agg = monthly_aggregates[month_key]
        travel_days_rounded = int(round(agg["travel_days"])) if isinstance(agg["travel_days"], Decimal) else agg["travel_days"]
        if travel_days_rounded > 0 or agg["value"] > 0:
            monthly_breakdown.append(TravelMonthlyBreakdown(
                month=month_key,
                travel_days=travel_days_rounded,
                claim_amount=agg["value"],
            ))

    # Compute totals from monthly aggregates
    # Sum the actual (possibly fractional) values, then round at the end
    grand_total_travel_days_raw = sum(agg["travel_days"] for agg in monthly_aggregates.values())
    grand_total_travel_days = int(round(grand_total_travel_days_raw)) if isinstance(grand_total_travel_days_raw, Decimal) else grand_total_travel_days_raw
    grand_total_value = sum(agg["value"] for agg in monthly_aggregates.values())

    result.weekly_detail = weekly_details
    result.monthly_breakdown = monthly_breakdown
    result.grand_total_travel_days = grand_total_travel_days
    result.grand_total_value = grand_total_value
    result.claim_before_deductions = grand_total_value

    return result
