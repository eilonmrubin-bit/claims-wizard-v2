"""Stage 7: Rest Window Placement.

Computes optimal 36-hour rest window placement per week.
Minimizes work hours in window (outside Shabbat core).
"""

from datetime import datetime, date, time, timedelta
from decimal import Decimal
from collections import defaultdict

from ...ssot import Shift, Week, RestDay, District
from .shabbat_times import get_shabbat_times_range, ShabbatTime


# Rest window must be exactly 36 hours
REST_WINDOW_HOURS = 36


def get_shabbat_bounds(
    week_start: date,
    rest_day: RestDay,
    district: District,
    shabbat_times: dict[date, ShabbatTime],
) -> tuple[datetime, datetime]:
    """Get Shabbat start and end for the week.

    For Saturday rest: Friday candles to Saturday havdalah.
    For other rest days: use simple calendar day bounds.
    """
    if rest_day == RestDay.SATURDAY:
        # Find Friday in this week
        days_to_friday = (4 - week_start.weekday()) % 7
        friday = week_start + timedelta(days=days_to_friday)

        # Get actual times from CSV data
        shabbat = shabbat_times.get(friday)
        if shabbat:
            return shabbat.candles, shabbat.havdalah
        else:
            raise ValueError(f"No Shabbat times found for {friday} in district data")

    elif rest_day == RestDay.FRIDAY:
        # Friday 00:00 to Saturday 00:00
        days_to_friday = (4 - week_start.weekday()) % 7
        friday = week_start + timedelta(days=days_to_friday)
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


def _advance_time(
    start_time: datetime,
    net_hours: Decimal,
    break_intervals: list[tuple[datetime, datetime]],
) -> datetime:
    """Advance 'net_hours' on the timeline, skipping breaks.

    This correctly maps net work hours to gross time positions.
    """
    remaining = float(net_hours)
    current = start_time

    for b_start, b_end in break_intervals:
        if remaining <= 0:
            break
        if b_start <= current:
            # Break already passed or we're inside it
            current = max(current, b_end)
            continue
        # Calculate work time before this break
        work_before_break = (b_start - current).total_seconds() / 3600
        if work_before_break >= remaining:
            return current + timedelta(hours=remaining)
        remaining -= work_before_break
        current = b_end

    return current + timedelta(hours=remaining)


def _overlap_hours(
    start1: datetime,
    end1: datetime,
    start2: datetime,
    end2: datetime,
) -> Decimal:
    """Calculate overlap hours between two time ranges (gross, without break adjustment)."""
    overlap_start = max(start1, start2)
    overlap_end = min(end1, end2)

    if overlap_end > overlap_start:
        diff = overlap_end - overlap_start
        return Decimal(str(diff.total_seconds())) / Decimal("3600")

    return Decimal("0")


def _net_overlap_hours(
    zone_start: datetime,
    zone_end: datetime,
    window_start: datetime,
    window_end: datetime,
    break_intervals: list[tuple[datetime, datetime]],
) -> Decimal:
    """Calculate overlap between a tier zone and the rest window, minus breaks.

    Returns net hours (breaks subtracted from the overlap).
    """
    raw = _overlap_hours(zone_start, zone_end, window_start, window_end)

    # Subtract breaks that fall in BOTH the zone AND the window
    for b_start, b_end in break_intervals:
        effective_start = max(b_start, zone_start, window_start)
        effective_end = min(b_end, zone_end, window_end)
        if effective_end > effective_start:
            diff = effective_end - effective_start
            raw -= Decimal(str(diff.total_seconds())) / Decimal("3600")

    return max(raw, Decimal("0"))


def classify_shift_rest_window(
    shift: Shift,
    window_start: datetime,
    window_end: datetime,
) -> None:
    """Classify shift hours as rest window or non-rest.

    Hours are classified by their actual position in the shift:
    - Regular hours are the FIRST hours (up to threshold)
    - OT Tier 1 are the NEXT 2 hours
    - OT Tier 2 are the remaining hours

    Each category is split based on actual overlap with the rest window.
    Breaks are properly accounted for when mapping net hours to time positions.
    """
    if shift.start is None or shift.end is None:
        return

    # Build sorted break intervals
    break_intervals = sorted(
        [(b.start, b.end) for b in (shift.breaks or [])],
        key=lambda x: x[0]
    )

    # Calculate time boundaries for each tier, skipping breaks
    regular_end = _advance_time(shift.start, shift.regular_hours, break_intervals)
    tier1_end = _advance_time(regular_end, shift.ot_tier1_hours, break_intervals)
    # tier2 goes to shift.end

    # Calculate net overlap of each tier with rest window (subtracting breaks)
    shift.rest_window_regular_hours = _net_overlap_hours(
        shift.start, regular_end, window_start, window_end, break_intervals
    )
    shift.non_rest_regular_hours = shift.regular_hours - shift.rest_window_regular_hours

    shift.rest_window_ot_tier1_hours = _net_overlap_hours(
        regular_end, tier1_end, window_start, window_end, break_intervals
    )
    shift.non_rest_ot_tier1_hours = shift.ot_tier1_hours - shift.rest_window_ot_tier1_hours

    shift.rest_window_ot_tier2_hours = _net_overlap_hours(
        tier1_end, shift.end, window_start, window_end, break_intervals
    )
    shift.non_rest_ot_tier2_hours = shift.ot_tier2_hours - shift.rest_window_ot_tier2_hours


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

    Handles cross-week rest windows: the 36-hour window may extend into
    the adjacent week, so we must consider adjacent week shifts for both
    optimization and classification.

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
    if shifts and rest_day == RestDay.SATURDAY:
        all_dates = [s.assigned_day for s in shifts if s.assigned_day]
        start_date = min(all_dates) if all_dates else date.today()
        end_date = max(all_dates) if all_dates else date.today()
        shabbat_times = get_shabbat_times_range(start_date, end_date, district)
    else:
        shabbat_times = {}

    # Sort weeks chronologically
    sorted_weeks = sorted(weeks, key=lambda w: w.start_date)
    week_index = {w.id: i for i, w in enumerate(sorted_weeks)}

    # === PASS 1: Optimize window placement ===
    # For optimization, include adjacent week's boundary shifts
    for week in sorted_weeks:
        week_shifts = shifts_by_week.get(week.id, [])

        shabbat_start, shabbat_end = get_shabbat_bounds(
            week.start_date,
            rest_day,
            district,
            shabbat_times,
        )

        # Collect shifts relevant to optimization:
        # own week + last day of prev week + first day of next week
        optimization_shifts = list(week_shifts)

        idx = week_index[week.id]

        # Previous week's last-day shifts (e.g., Friday from prev week)
        if idx > 0:
            prev_week = sorted_weeks[idx - 1]
            prev_shifts = shifts_by_week.get(prev_week.id, [])
            for s in prev_shifts:
                if s.assigned_day and s.assigned_day >= week.start_date - timedelta(days=1):
                    optimization_shifts.append(s)

        # Next week's first-day shifts (e.g., Sunday from next week)
        if idx < len(sorted_weeks) - 1:
            next_week = sorted_weeks[idx + 1]
            next_shifts = shifts_by_week.get(next_week.id, [])
            for s in next_shifts:
                if s.assigned_day and week.end_date and s.assigned_day <= week.end_date + timedelta(days=1):
                    optimization_shifts.append(s)

        window_start, window_end = optimize_rest_window(
            optimization_shifts,
            shabbat_start,
            shabbat_end,
        )

        week.rest_window_start = window_start
        week.rest_window_end = window_end

        # Work hours in window (from ALL relevant shifts, not just week_shifts)
        week.rest_window_work_hours = calculate_work_in_window(
            optimization_shifts,
            window_start,
            window_end,
        )

    # === PASS 2: Classify each shift against relevant windows ===
    for week in sorted_weeks:
        week_shifts = shifts_by_week.get(week.id, [])

        # Classify own shifts against own window
        for shift in week_shifts:
            classify_shift_rest_window(
                shift,
                week.rest_window_start,
                week.rest_window_end,
            )

        # Also check: does this week's window extend into adjacent weeks?
        idx = week_index[week.id]

        # Check next week's shifts against THIS week's window
        if idx < len(sorted_weeks) - 1:
            next_week = sorted_weeks[idx + 1]
            next_shifts = shifts_by_week.get(next_week.id, [])
            for shift in next_shifts:
                if shift.start and week.rest_window_end and shift.start < week.rest_window_end:
                    # This shift overlaps with current week's rest window
                    # Only classify if not already classified by its own week
                    already_has_rest = (
                        shift.rest_window_regular_hours > 0 or
                        shift.rest_window_ot_tier1_hours > 0 or
                        shift.rest_window_ot_tier2_hours > 0
                    )
                    if not already_has_rest:
                        classify_shift_rest_window(
                            shift,
                            week.rest_window_start,
                            week.rest_window_end,
                        )

        # Check previous week's shifts against THIS week's window
        if idx > 0:
            prev_week = sorted_weeks[idx - 1]
            prev_shifts = shifts_by_week.get(prev_week.id, [])
            for shift in prev_shifts:
                if shift.end and week.rest_window_start and shift.end > week.rest_window_start:
                    already_has_rest = (
                        shift.rest_window_regular_hours > 0 or
                        shift.rest_window_ot_tier1_hours > 0 or
                        shift.rest_window_ot_tier2_hours > 0
                    )
                    if not already_has_rest:
                        classify_shift_rest_window(
                            shift,
                            week.rest_window_start,
                            week.rest_window_end,
                        )

    return shifts, weeks
