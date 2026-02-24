"""Stage 2: Shift Assignment (Day & Week).

Assigns each shift to a calendar day and week using majority rule.
Tie -> assign to earlier day/week.
"""

from datetime import datetime, date, timedelta
from decimal import Decimal

from ...ssot import Shift


def get_week_id(d: date) -> str:
    """Get week ID in format YYYY-Www.

    Week starts on Sunday (ISO week adjusted).
    """
    # Python's isocalendar uses Monday as week start
    # We need Sunday as week start
    # Shift the date by 1 day to align
    adjusted = d + timedelta(days=1)
    iso_year, iso_week, _ = adjusted.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def get_week_start_end(week_id: str) -> tuple[date, date]:
    """Get start (Sunday) and end (Saturday) dates for a week ID."""
    year = int(week_id[:4])
    week_num = int(week_id[6:])

    # Find the first day of the ISO week (Monday)
    jan4 = date(year, 1, 4)  # Jan 4 is always in week 1
    iso_week_start = jan4 - timedelta(days=jan4.weekday())
    monday = iso_week_start + timedelta(weeks=week_num - 1)

    # Our weeks start on Sunday (day before Monday)
    sunday = monday - timedelta(days=1)
    saturday = sunday + timedelta(days=6)

    return sunday, saturday


def calculate_hours_in_day(shift: Shift, target_date: date) -> Decimal:
    """Calculate hours of shift that fall within a specific calendar day."""
    day_start = datetime.combine(target_date, datetime.min.time())
    day_end = datetime.combine(target_date + timedelta(days=1), datetime.min.time())

    overlap_start = max(shift.start, day_start)
    overlap_end = min(shift.end, day_end)

    if overlap_end > overlap_start:
        diff = overlap_end - overlap_start
        return Decimal(str(diff.total_seconds())) / Decimal("3600")

    return Decimal("0")


def assign_shift_to_day(shift: Shift) -> date:
    """Assign shift to calendar day with majority of hours.

    Tie -> assign to earlier day.
    """
    if shift.start is None or shift.end is None:
        # Should not happen, but fallback to shift date
        return shift.date

    # Get all dates the shift spans
    start_date = shift.start.date()
    end_date = shift.end.date()

    if start_date == end_date:
        return start_date

    # Calculate hours per day
    best_date = start_date
    best_hours = Decimal("0")

    current_date = start_date
    while current_date <= end_date:
        hours = calculate_hours_in_day(shift, current_date)
        # Tie -> keep earlier date (since we iterate chronologically)
        if hours > best_hours:
            best_hours = hours
            best_date = current_date
        current_date += timedelta(days=1)

    return best_date


def calculate_hours_in_week(shift: Shift, week_id: str) -> Decimal:
    """Calculate hours of shift that fall within a specific week."""
    week_start, week_end = get_week_start_end(week_id)
    week_start_dt = datetime.combine(week_start, datetime.min.time())
    week_end_dt = datetime.combine(week_end + timedelta(days=1), datetime.min.time())

    overlap_start = max(shift.start, week_start_dt)
    overlap_end = min(shift.end, week_end_dt)

    if overlap_end > overlap_start:
        diff = overlap_end - overlap_start
        return Decimal(str(diff.total_seconds())) / Decimal("3600")

    return Decimal("0")


def assign_shift_to_week(shift: Shift, assigned_day: date) -> str:
    """Assign shift to week with majority of hours.

    Uses the assigned_day as primary reference.
    For shifts crossing week boundary, uses majority rule.
    """
    primary_week = get_week_id(assigned_day)

    if shift.start is None or shift.end is None:
        return primary_week

    # Check if shift might cross week boundary
    start_week = get_week_id(shift.start.date())
    end_week = get_week_id(shift.end.date())

    if start_week == end_week:
        return start_week

    # Calculate hours per week
    start_hours = calculate_hours_in_week(shift, start_week)
    end_hours = calculate_hours_in_week(shift, end_week)

    # Tie -> earlier week
    if start_hours >= end_hours:
        return start_week
    else:
        return end_week


def assign_shifts(shifts: list[Shift]) -> list[Shift]:
    """Assign all shifts to days and weeks.

    Updates each shift's assigned_day and assigned_week fields.

    Args:
        shifts: List of shifts from Stage 1

    Returns:
        Same shifts with assigned_day and assigned_week populated
    """
    for shift in shifts:
        shift.assigned_day = assign_shift_to_day(shift)
        shift.assigned_week = assign_shift_to_week(shift, shift.assigned_day)

    return shifts
