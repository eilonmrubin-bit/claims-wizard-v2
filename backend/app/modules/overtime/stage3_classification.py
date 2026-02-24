"""Stage 3: Week Classification.

Determines week type (5/6 day) based on distinct work days.
"""

from datetime import date, timedelta
from collections import defaultdict

from ...ssot import Shift, Week, WeekType
from .stage2_assignment import get_week_start_end


def classify_weeks(shifts: list[Shift]) -> list[Week]:
    """Classify weeks based on distinct work days.

    Args:
        shifts: List of assigned shifts (with assigned_week populated)

    Returns:
        List of Week objects with week_type classification
    """
    # Group shifts by week
    shifts_by_week: dict[str, list[Shift]] = defaultdict(list)
    for shift in shifts:
        shifts_by_week[shift.assigned_week].append(shift)

    weeks: list[Week] = []

    for week_id, week_shifts in sorted(shifts_by_week.items()):
        # Count distinct work days
        distinct_days = set()
        for shift in week_shifts:
            if shift.assigned_day:
                distinct_days.add(shift.assigned_day)

        distinct_work_days = len(distinct_days)

        # Determine week type
        if distinct_work_days > 5:
            week_type = WeekType.SIX_DAY
        else:
            week_type = WeekType.FIVE_DAY

        # Get week boundaries
        week_start, week_end = get_week_start_end(week_id)

        # Parse year and week number from ID
        year = int(week_id[:4])
        week_number = int(week_id[6:])

        week = Week(
            id=week_id,
            year=year,
            week_number=week_number,
            start_date=week_start,
            end_date=week_end,
            distinct_work_days=distinct_work_days,
            week_type=week_type,
        )
        weeks.append(week)

    return weeks
