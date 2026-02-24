"""Stage 6: Weekly Overtime Detection.

Detects weekly OT when sum of regular hours > 42.
Attributes weekly OT to shifts chronologically.
Applies unified tier assignment per shift.
"""

from decimal import Decimal
from collections import defaultdict

from ...ssot import Shift, Week
from .config import OTConfig, DEFAULT_CONFIG


def detect_weekly_ot(
    shifts: list[Shift],
    weeks: list[Week],
    config: OTConfig | None = None,
) -> tuple[list[Shift], list[Week]]:
    """Detect weekly overtime.

    Rules:
    1. Sum regular hours (Tier 0 only) across all shifts in week
    2. If sum > 42 -> excess = weekly overtime
    3. Attribute weekly OT to shifts chronologically
    4. Combine daily + weekly OT, then apply tier assignment:
       - First 2 hours OT = Tier 1
       - Rest = Tier 2

    Args:
        shifts: List of shifts with daily OT populated
        weeks: List of classified weeks
        config: OT configuration (uses default if None)

    Returns:
        (shifts, weeks) with weekly OT populated
    """
    if config is None:
        config = DEFAULT_CONFIG

    # Group shifts by week
    shifts_by_week: dict[str, list[Shift]] = defaultdict(list)
    for shift in shifts:
        shifts_by_week[shift.assigned_week].append(shift)

    # Build week lookup
    week_lookup = {w.id: w for w in weeks}

    for week_id, week_shifts in shifts_by_week.items():
        # Sort by start time (chronological order)
        week_shifts.sort(key=lambda s: s.start or s.date)

        # Sum regular hours
        total_regular = sum(s.regular_hours for s in week_shifts)

        week = week_lookup.get(week_id)
        if week:
            week.total_regular_hours = total_regular

        if total_regular <= config.weekly_cap:
            # No weekly OT
            if week:
                week.weekly_ot_hours = Decimal("0")
            for shift in week_shifts:
                shift.weekly_ot_hours = Decimal("0")
            continue

        # Weekly OT = excess over cap
        weekly_ot_total = total_regular - config.weekly_cap
        if week:
            week.weekly_ot_hours = weekly_ot_total

        # Attribute to shifts chronologically
        # Walk through shifts accumulating regular hours
        accumulated_regular = Decimal("0")
        remaining_ot = weekly_ot_total

        for shift in week_shifts:
            if remaining_ot <= 0:
                shift.weekly_ot_hours = Decimal("0")
                continue

            prev_accumulated = accumulated_regular
            accumulated_regular += shift.regular_hours

            if accumulated_regular <= config.weekly_cap:
                # Haven't crossed threshold yet
                shift.weekly_ot_hours = Decimal("0")
            else:
                # This is a crossover shift or beyond
                if prev_accumulated >= config.weekly_cap:
                    # Already past threshold - all regular becomes weekly OT
                    ot_from_this_shift = min(shift.regular_hours, remaining_ot)
                else:
                    # Crossover shift
                    # How much regular reaches exactly 42?
                    regular_to_cap = config.weekly_cap - prev_accumulated
                    # Rest becomes weekly OT
                    ot_from_this_shift = min(
                        shift.regular_hours - regular_to_cap,
                        remaining_ot
                    )

                shift.weekly_ot_hours = ot_from_this_shift
                # Reduce regular_hours by weekly OT amount
                shift.regular_hours -= ot_from_this_shift
                remaining_ot -= ot_from_this_shift

        # Now apply unified tier assignment per shift
        # Total OT = daily_ot + weekly_ot
        # First 2h = Tier 1, rest = Tier 2
        for shift in week_shifts:
            total_ot = shift.daily_ot_hours + shift.weekly_ot_hours

            # Reset tiers and recalculate
            tier1 = min(total_ot, config.tier1_max_hours)
            tier2 = total_ot - tier1

            shift.ot_tier1_hours = tier1
            shift.ot_tier2_hours = tier2

    return shifts, weeks
