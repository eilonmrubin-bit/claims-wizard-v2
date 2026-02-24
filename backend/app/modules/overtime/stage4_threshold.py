"""Stage 4: Threshold Resolution.

Determines applicable daily threshold for each shift.
Handles exceptions: eve of rest, night shift.
"""

from datetime import datetime, date, time, timedelta
from decimal import Decimal

from ...ssot import Shift, Week, WeekType, RestDay, District
from .config import OTConfig, DEFAULT_CONFIG
from .shabbat_times import get_shabbat_times_range, ShabbatTime


def is_night_shift(shift: Shift, config: OTConfig) -> bool:
    """Check if shift qualifies as night shift.

    A shift is a night shift if >= min_hours fall within 22:00-06:00 band.
    """
    if shift.start is None or shift.end is None:
        return False

    # Calculate hours overlapping with night band (22:00-06:00)
    night_hours = Decimal("0")

    # Night band spans midnight, so we need to check two ranges:
    # 22:00-24:00 and 00:00-06:00
    current = shift.start
    while current < shift.end:
        hour = current.hour
        # Check if this hour is in night band
        if hour >= config.night_start_hour or hour < config.night_end_hour:
            # Calculate overlap for this segment
            segment_end = min(
                shift.end,
                current.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            )
            diff = segment_end - current
            night_hours += Decimal(str(diff.total_seconds())) / Decimal("3600")

        current = current.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

    return night_hours >= config.night_min_hours


def is_eve_of_rest(
    shift: Shift,
    rest_day: RestDay,
    district: District,
    shabbat_times: dict[date, ShabbatTime],
) -> bool:
    """Check if shift falls within eve of rest window.

    For Saturday rest: 24 hours before candle lighting.
    For Friday/Sunday rest: the calendar day before.

    A shift is classified as eve-of-rest if its START TIME falls within
    the eve window.
    """
    if shift.assigned_day is None or shift.start is None:
        return False

    if rest_day == RestDay.SATURDAY:
        # Find the relevant Friday (the one on or after the assigned day)
        assigned = shift.assigned_day
        days_until_friday = (4 - assigned.weekday()) % 7
        friday = assigned + timedelta(days=days_until_friday)

        # If assigned day is Sat/Sun, we want the previous Friday
        if assigned.weekday() >= 5:
            days_since_friday = (assigned.weekday() - 4) % 7
            friday = assigned - timedelta(days=days_since_friday)

        # Get candle lighting time from actual data
        shabbat = shabbat_times.get(friday)
        if shabbat:
            candles = shabbat.candles
        else:
            raise ValueError(f"No Shabbat times found for {friday} in district data")

        # Eve of rest window: 24 hours before candle lighting to candle lighting
        eve_start = candles - timedelta(hours=24)
        eve_end = candles

        # Check if shift's START TIME falls within eve window
        return eve_start <= shift.start < eve_end

    elif rest_day == RestDay.FRIDAY:
        # Eve of Friday rest = Thursday (any shift on Thursday)
        return shift.assigned_day.weekday() == 3  # Thursday

    elif rest_day == RestDay.SUNDAY:
        # Eve of Sunday rest = Saturday (any shift on Saturday)
        return shift.assigned_day.weekday() == 5  # Saturday

    return False


def resolve_thresholds(
    shifts: list[Shift],
    weeks: list[Week],
    rest_day: RestDay,
    district: District,
    config: OTConfig | None = None,
) -> list[Shift]:
    """Resolve threshold for each shift.

    Args:
        shifts: List of assigned shifts
        weeks: List of classified weeks
        rest_day: Employee's rest day
        district: Employee's district (for Shabbat times)
        config: OT configuration (uses default if None)

    Returns:
        Shifts with threshold and threshold_reason populated
    """
    if config is None:
        config = DEFAULT_CONFIG

    # Build week lookup
    week_lookup = {w.id: w for w in weeks}

    # Get date range and load Shabbat times
    if shifts and rest_day == RestDay.SATURDAY:
        start_date = min(s.assigned_day for s in shifts if s.assigned_day)
        end_date = max(s.assigned_day for s in shifts if s.assigned_day)
        shabbat_times = get_shabbat_times_range(start_date, end_date, district)
    else:
        shabbat_times = {}

    for shift in shifts:
        week = week_lookup.get(shift.assigned_week)
        if not week:
            # Shouldn't happen, but default to 5-day threshold
            shift.threshold = config.threshold_5day
            shift.threshold_reason = "default (week not found)"
            continue

        # Start with base threshold by week type
        if week.week_type == WeekType.FIVE_DAY:
            threshold = config.threshold_5day
            reason = "5-day week"
        else:
            threshold = config.threshold_6day
            reason = "6-day week"

        # Check exceptions (both reduce to 7.0)
        is_eve = is_eve_of_rest(shift, rest_day, district, shabbat_times)
        is_night = is_night_shift(shift, config)

        if is_eve and is_night:
            threshold = config.threshold_eve_rest
            reason = "eve of rest + night shift"
        elif is_eve:
            threshold = config.threshold_eve_rest
            reason = "eve of rest"
        elif is_night:
            threshold = config.threshold_night
            reason = "night shift"

        shift.threshold = threshold
        shift.threshold_reason = reason

    return shifts
