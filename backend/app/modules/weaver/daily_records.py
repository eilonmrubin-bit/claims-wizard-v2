"""Stage 3: Generate daily records for each day in effective periods.

Creates a DailyRecord for every calendar day within employment periods,
including non-work days.
"""

from datetime import date, timedelta
from typing import Any

from app.ssot import (
    DailyRecord,
    EffectivePeriod,
    TimeRange,
    DayShifts,
)


# Map rest_day string to day of week (0=Sunday..6=Saturday)
REST_DAY_MAP = {
    "saturday": 6,
    "friday": 5,
    "sunday": 0,
}


def is_rest_day(day_of_week: int, rest_day: str) -> bool:
    """Check if the given day of week is the rest day."""
    rest_dow = REST_DAY_MAP.get(rest_day, 6)  # Default to Saturday
    return day_of_week == rest_dow


def day_of_week(d: date) -> int:
    """Get day of week: 0=Sunday..6=Saturday.

    Python's weekday() returns 0=Monday..6=Sunday.
    We need 0=Sunday..6=Saturday for Israeli calendar.
    """
    # Python: Monday=0, Tuesday=1, ..., Sunday=6
    # We want: Sunday=0, Monday=1, ..., Saturday=6
    return (d.weekday() + 1) % 7


def is_work_day(
    d: date,
    dow: int,
    pattern_work_days: list[int],
    pattern_daily_overrides: dict | None,
) -> bool:
    """Check if the given day is a work day.

    For cyclic patterns (Level B), daily_overrides is authoritative:
    - If daily_overrides is present, a day is a work day IFF it's in daily_overrides
    - If daily_overrides is None/empty, fall back to pattern_work_days

    If the pattern includes the rest day, both is_work_day and is_rest_day
    will be True. The OT pipeline will apply rest-day rates (150%/200%).
    Rest day does NOT override the pattern.
    """
    # For cyclic patterns: daily_overrides is authoritative
    if pattern_daily_overrides:
        return d in pattern_daily_overrides

    # For simple weekly patterns: use work_days
    return dow in pattern_work_days


def get_shifts_for_day(
    ep: EffectivePeriod,
    d: date,
    dow: int
) -> list[TimeRange]:
    """Get shift templates for a specific day.

    Priority: daily_overrides > per_day > default_shifts
    """
    # Check daily_overrides first (specific date)
    if ep.pattern_daily_overrides and d in ep.pattern_daily_overrides:
        override = ep.pattern_daily_overrides[d]
        if hasattr(override, 'shifts') and override.shifts:
            return list(override.shifts)
        return []

    # Check per_day (day of week specific)
    if ep.pattern_per_day and dow in ep.pattern_per_day:
        per_day_config = ep.pattern_per_day[dow]
        if hasattr(per_day_config, 'shifts') and per_day_config.shifts:
            return list(per_day_config.shifts)

    # Fall back to default
    if ep.pattern_default_shifts:
        return list(ep.pattern_default_shifts)

    return []


def get_breaks_for_day(
    ep: EffectivePeriod,
    d: date,
    dow: int
) -> list[TimeRange]:
    """Get break templates for a specific day.

    Priority: daily_overrides > per_day > default_breaks
    """
    # Check daily_overrides first (specific date)
    if ep.pattern_daily_overrides and d in ep.pattern_daily_overrides:
        override = ep.pattern_daily_overrides[d]
        if hasattr(override, 'breaks') and override.breaks:
            return list(override.breaks)
        return []

    # Check per_day (day of week specific)
    if ep.pattern_per_day and dow in ep.pattern_per_day:
        per_day_config = ep.pattern_per_day[dow]
        if hasattr(per_day_config, 'breaks') and per_day_config.breaks:
            return list(per_day_config.breaks)

    # Fall back to default
    if ep.pattern_default_breaks:
        return list(ep.pattern_default_breaks)

    return []


def generate_daily_records(
    effective_periods: list[EffectivePeriod],
    rest_day: str
) -> list[DailyRecord]:
    """Generate daily records for all effective periods.

    Creates a record for every calendar day, including non-work days.
    Days in gaps between employment periods are NOT included.
    """
    records = []

    for ep in effective_periods:
        current = ep.start

        while current <= ep.end:
            dow = day_of_week(current)
            rest = is_rest_day(dow, rest_day)
            work = is_work_day(current, dow, ep.pattern_work_days, ep.pattern_daily_overrides)

            # Get shift and break templates
            if work:
                shifts = get_shifts_for_day(ep, current, dow)
                breaks = get_breaks_for_day(ep, current, dow)
            else:
                shifts = []
                breaks = []

            records.append(DailyRecord(
                date=current,
                effective_period_id=ep.id,
                day_of_week=dow,
                is_work_day=work,
                is_rest_day=rest,
                shift_templates=shifts,
                break_templates=breaks,
                day_segments=None,  # Filled by OT stage 3.5
            ))

            current += timedelta(days=1)

    return records
