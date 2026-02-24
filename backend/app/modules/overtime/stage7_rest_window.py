"""Stage 7: Rest Window Placement.

Computes optimal 36-hour rest window placement per week.
Minimizes work hours in window (outside Shabbat core).
"""

from datetime import datetime, date, time, timedelta
from decimal import Decimal
from collections import defaultdict

from ...ssot import Shift, Week, RestDay, District
from .stage4_threshold import load_shabbat_times


# Rest window must be exactly 36 hours
REST_WINDOW_HOURS = 36


def get_shabbat_bounds(
    week_start: date,
    rest_day: RestDay,
    district: District,
    shabbat_times: dict,
) -> tuple[datetime, datetime]:
    """Get Shabbat start and end for the week.

    For Saturday rest: Friday candles to Saturday havdalah.
    For other rest days: use simple calendar day bounds.
    """
    if rest_day == RestDay.SATURDAY:
        # Find Friday in this week
        friday = week_start + timedelta(days=(4 - week_start.weekday()) % 7)
        if friday < week_start:
            friday += timedelta(days=7)

        if friday in shabbat_times:
            candles = shabbat_times[friday]["candles"]
            havdalah = shabbat_times[friday]["havdalah"]
        else:
            # Default times
            candles = datetime.combine(friday, time(16, 30))
            saturday = friday + timedelta(days=1)
            havdalah = datetime.combine(saturday, time(17, 30))

        return candles, havdalah

    elif rest_day == RestDay.FRIDAY:
        # Friday 00:00 to Saturday 00:00
        friday = week_start + timedelta(days=(4 - week_start.weekday()) % 7)
        return (
            datetime.combine(friday, time(0, 0)),
            datetime.combine(friday + timedelta(days=1), time(0, 0))
        )

    else:  # SUNDAY
        # Sunday 00:00 to Monday 00:00
        sunday = week_start
        return (
            datetime.combine(sunday, time(0, 0)),
            datetime.combine(sunday + timedelta(days=1), time(0, 0))
        )


def calculate_work_in_window(
    shifts: list[Shift],
    window_start: datetime,
    window_end: datetime,
) -> Decimal:
    """Calculate total work hours that fall within the window."""
    total = Decimal("0")

    for shift in shifts:
        if shift.start is None or shift.end is None:
            continue

        # Calculate overlap
        overlap_start = max(shift.start, window_start)
        overlap_end = min(shift.end, window_end)

        if overlap_end > overlap_start:
            diff = overlap_end - overlap_start
            total += Decimal(str(diff.total_seconds())) / Decimal("3600")

    return total


def classify_shift_rest_window(
    shift: Shift,
    window_start: datetime,
    window_end: datetime,
) -> None:
    """Classify shift hours as rest window or non-rest.

    Updates shift's rest_window_* and non_rest_* fields.
    """
    if shift.start is None or shift.end is None:
        return

    # Calculate hours inside and outside window
    overlap_start = max(shift.start, window_start)
    overlap_end = min(shift.end, window_end)

    if overlap_end > overlap_start:
        diff = overlap_end - overlap_start
        in_rest_hours = Decimal(str(diff.total_seconds())) / Decimal("3600")
    else:
        in_rest_hours = Decimal("0")

    out_rest_hours = shift.net_hours - in_rest_hours

    # Distribute regular and OT hours proportionally
    if shift.net_hours > 0:
        in_ratio = in_rest_hours / shift.net_hours
        out_ratio = out_rest_hours / shift.net_hours
    else:
        in_ratio = Decimal("0")
        out_ratio = Decimal("0")

    shift.rest_window_regular_hours = shift.regular_hours * in_ratio
    shift.rest_window_ot_tier1_hours = shift.ot_tier1_hours * in_ratio
    shift.rest_window_ot_tier2_hours = shift.ot_tier2_hours * in_ratio

    shift.non_rest_regular_hours = shift.regular_hours * out_ratio
    shift.non_rest_ot_tier1_hours = shift.ot_tier1_hours * out_ratio
    shift.non_rest_ot_tier2_hours = shift.ot_tier2_hours * out_ratio


def optimize_rest_window(
    shifts: list[Shift],
    shabbat_start: datetime,
    shabbat_end: datetime,
) -> tuple[datetime, datetime]:
    """Find optimal rest window placement.

    Window must:
    1. Be exactly 36 hours
    2. Fully cover Shabbat (candles to havdalah)
    3. Be continuous
    4. Minimize work hours in padding (outside Shabbat)
    """
    # Calculate Shabbat duration
    shabbat_diff = shabbat_end - shabbat_start
    shabbat_hours = Decimal(str(shabbat_diff.total_seconds())) / Decimal("3600")

    # Padding needed
    padding_hours = Decimal(str(REST_WINDOW_HOURS)) - shabbat_hours

    if padding_hours <= 0:
        # Shabbat >= 36 hours (shouldn't happen), just use Shabbat bounds
        return shabbat_start, shabbat_end

    # Generate breakpoints to test
    breakpoints = [Decimal("0"), padding_hours]

    for shift in shifts:
        if shift.start is None or shift.end is None:
            continue

        # Shifts before Shabbat
        if shift.end <= shabbat_start:
            before = shabbat_start - shift.end
            before_hours = Decimal(str(before.total_seconds())) / Decimal("3600")
            if Decimal("0") <= before_hours <= padding_hours:
                breakpoints.append(before_hours)

            before2 = shabbat_start - shift.start
            before2_hours = Decimal(str(before2.total_seconds())) / Decimal("3600")
            if Decimal("0") <= before2_hours <= padding_hours:
                breakpoints.append(before2_hours)

        # Shifts after Shabbat
        if shift.start >= shabbat_end:
            after = shift.start - shabbat_end
            after_hours = Decimal(str(after.total_seconds())) / Decimal("3600")
            before_val = padding_hours - after_hours
            if Decimal("0") <= before_val <= padding_hours:
                breakpoints.append(before_val)

            after2 = shift.end - shabbat_end
            after2_hours = Decimal(str(after2.total_seconds())) / Decimal("3600")
            before_val2 = padding_hours - after2_hours
            if Decimal("0") <= before_val2 <= padding_hours:
                breakpoints.append(before_val2)

    # Evaluate each breakpoint
    best_before = Decimal("0")
    best_work = None

    for before in set(breakpoints):
        if before < 0 or before > padding_hours:
            continue

        after = padding_hours - before
        window_start = shabbat_start - timedelta(hours=float(before))
        window_end = shabbat_end + timedelta(hours=float(after))

        # Calculate work in padding zones (not in Shabbat itself)
        before_work = calculate_work_in_window(shifts, window_start, shabbat_start)
        after_work = calculate_work_in_window(shifts, shabbat_end, window_end)
        total_work = before_work + after_work

        if best_work is None or total_work < best_work:
            best_work = total_work
            best_before = before
        elif total_work == best_work and after > (padding_hours - best_before):
            # Tie -> prefer padding after (larger after = smaller before)
            best_before = before

    after = padding_hours - best_before
    final_start = shabbat_start - timedelta(hours=float(best_before))
    final_end = shabbat_end + timedelta(hours=float(after))

    return final_start, final_end


def place_rest_windows(
    shifts: list[Shift],
    weeks: list[Week],
    rest_day: RestDay,
    district: District,
) -> tuple[list[Shift], list[Week]]:
    """Place rest windows for all weeks.

    Args:
        shifts: List of shifts with all OT calculated
        weeks: List of classified weeks
        rest_day: Employee's rest day
        district: Employee's district (for Shabbat times)

    Returns:
        (shifts, weeks) with rest window populated
    """
    # Group shifts by week
    shifts_by_week: dict[str, list[Shift]] = defaultdict(list)
    for shift in shifts:
        shifts_by_week[shift.assigned_week].append(shift)

    # Get date range and load Shabbat times
    if shifts:
        all_dates = [s.assigned_day for s in shifts if s.assigned_day]
        start_date = min(all_dates) if all_dates else date.today()
        end_date = max(all_dates) if all_dates else date.today()
        shabbat_times = load_shabbat_times(district, start_date, end_date)
    else:
        shabbat_times = {}

    for week in weeks:
        week_shifts = shifts_by_week.get(week.id, [])

        # Get Shabbat bounds for this week
        shabbat_start, shabbat_end = get_shabbat_bounds(
            week.start_date,
            rest_day,
            district,
            shabbat_times,
        )

        # Optimize window placement
        window_start, window_end = optimize_rest_window(
            week_shifts,
            shabbat_start,
            shabbat_end,
        )

        week.rest_window_start = window_start
        week.rest_window_end = window_end

        # Calculate work hours in window
        week.rest_window_work_hours = calculate_work_in_window(
            week_shifts,
            window_start,
            window_end,
        )

        # Classify each shift's hours
        for shift in week_shifts:
            classify_shift_rest_window(shift, window_start, window_end)

    return shifts, weeks
