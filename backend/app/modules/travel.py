"""Travel allowance (דמי נסיעות) module.

Calculates travel allowance based on work days, lodging patterns, and industry rates.
See docs/skills/travel/SKILL.md for complete documentation.
"""

from collections import defaultdict
from dataclasses import field
from datetime import date
from decimal import Decimal
from typing import Callable

from app.ssot import (
    Week,
    Shift,
    LodgingInput,
    LodgingWeek,
    TravelData,
    TravelWeekDetail,
    TravelMonthlyBreakdown,
)


def compute_week_travel(work_days: int, week_pattern: str) -> int:
    """Compute travel days for a week based on work days and lodging pattern.

    Args:
        work_days: Number of distinct work days in the week
        week_pattern: "full_lodging" | "daily_return" | "no_lodging"

    Returns:
        Number of travel days
    """
    if week_pattern == "daily_return" or week_pattern == "no_lodging":
        return work_days

    if week_pattern == "full_lodging":
        if work_days == 0:
            return 0
        if work_days == 1:
            # Only one day worked — departure or return, not both
            return 1
        # Standard lodging week: 2 travel days (departure + return)
        return 2

    # Unknown pattern — treat as no lodging
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
    cycle_weeks = 1
    cycle: list[LodgingWeek] = []

    if industry == "construction" and lodging_input is not None and lodging_input.has_lodging:
        has_lodging = True
        cycle_weeks = lodging_input.cycle_weeks
        cycle = lodging_input.cycle if lodging_input.cycle else []

    result.has_lodging = has_lodging
    result.lodging_cycle_weeks = cycle_weeks if has_lodging else None
    result.lodging_cycle = cycle if has_lodging else None

    # Build a lookup for cycle patterns
    cycle_lookup: dict[int, str] = {}
    if has_lodging and cycle:
        for lw in cycle:
            cycle_lookup[lw.week_in_cycle] = lw.pattern

    # Filter to weeks with actual work
    work_weeks = []
    for week in weeks:
        work_days = get_work_days_in_week(week, shifts)
        if work_days > 0:
            work_weeks.append((week, work_days))

    # Track cycle position - resets at employment gaps
    # For simplicity, we track consecutive weeks. A gap in weeks = reset.
    # We'll identify gaps by checking if weeks are consecutive.
    cycle_position = 0
    prev_week_end: date | None = None

    weekly_details: list[TravelWeekDetail] = []
    monthly_aggregates: dict[tuple[int, int], dict] = defaultdict(lambda: {"travel_days": 0, "value": Decimal("0")})

    # Get first rate to use as the "effective rate" for display
    if work_weeks:
        first_week = work_weeks[0][0]
        if first_week.start_date:
            result.daily_rate = get_travel_rate(industry, travel_distance_km, first_week.start_date)

    for week, work_days in work_weeks:
        if week.start_date is None:
            continue

        # Check for gap - if there's a discontinuity, reset cycle
        if prev_week_end is not None:
            # If more than 7 days gap, reset cycle
            days_gap = (week.start_date - prev_week_end).days
            if days_gap > 7:
                cycle_position = 0

        # Increment cycle position
        cycle_position += 1
        if has_lodging and cycle_weeks > 0:
            current_cycle_pos = ((cycle_position - 1) % cycle_weeks) + 1
        else:
            current_cycle_pos = None

        # Determine week pattern
        if has_lodging and current_cycle_pos is not None:
            week_pattern = cycle_lookup.get(current_cycle_pos, "full_lodging")
        else:
            week_pattern = "no_lodging"

        # Compute travel days
        travel_days = compute_week_travel(work_days, week_pattern)

        # Get rate for this week
        daily_rate = get_travel_rate(industry, travel_distance_km, week.start_date)

        # Compute value
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
            cycle_position=current_cycle_pos,
            week_pattern=week_pattern,
            travel_days=travel_days,
            daily_rate=daily_rate,
            week_travel_value=week_travel_value,
        )
        weekly_details.append(detail)

        # Aggregate by month (week belongs to month of start_date)
        month_key = (week.start_date.year, week.start_date.month)
        monthly_aggregates[month_key]["travel_days"] += travel_days
        monthly_aggregates[month_key]["value"] += week_travel_value

        prev_week_end = week.end_date

    # Build monthly breakdown
    monthly_breakdown = []
    for month_key in sorted(monthly_aggregates.keys()):
        agg = monthly_aggregates[month_key]
        monthly_breakdown.append(TravelMonthlyBreakdown(
            month=month_key,
            travel_days=agg["travel_days"],
            claim_amount=agg["value"],
        ))

    # Compute totals
    grand_total_travel_days = sum(d.travel_days for d in weekly_details)
    grand_total_value = sum(d.week_travel_value for d in weekly_details)

    result.weekly_detail = weekly_details
    result.monthly_breakdown = monthly_breakdown
    result.grand_total_travel_days = grand_total_travel_days
    result.grand_total_value = grand_total_value
    result.claim_before_deductions = grand_total_value

    return result
