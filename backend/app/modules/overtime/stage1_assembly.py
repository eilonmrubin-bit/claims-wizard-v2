"""Stage 1: Shift Assembly.

Groups raw work entries into shifts.
Gap between segments <= 3 hours = one shift with break.
Gap > 3 hours = two separate shifts.
"""

from datetime import datetime, date, time, timedelta
from decimal import Decimal
from dataclasses import dataclass, field

from ...ssot import DailyRecord, Shift, ShiftSegment, TimeRange


# Maximum gap to consider same shift (in hours)
MAX_GAP_HOURS = 3


def time_to_datetime(d: date, t: time) -> datetime:
    """Combine date and time into datetime."""
    return datetime.combine(d, t)


def datetime_diff_hours(start: datetime, end: datetime) -> Decimal:
    """Calculate hours between two datetimes."""
    diff = end - start
    total_seconds = diff.total_seconds()
    return Decimal(str(total_seconds)) / Decimal("3600")


def handle_overnight_shift(d: date, start_time: time, end_time: time) -> tuple[datetime, datetime]:
    """Handle shifts that cross midnight.

    If end_time <= start_time, the shift crosses midnight.
    """
    start_dt = time_to_datetime(d, start_time)

    if end_time <= start_time:
        # Crosses midnight - end is on next day
        next_day = d + timedelta(days=1)
        end_dt = time_to_datetime(next_day, end_time)
    else:
        end_dt = time_to_datetime(d, end_time)

    return start_dt, end_dt


def calculate_break_hours(
    breaks: list[TimeRange],
    shift_start: datetime,
    shift_end: datetime,
    d: date,
) -> Decimal:
    """Calculate total break hours that fall within the shift."""
    total = Decimal("0")

    for brk in breaks:
        brk_start, brk_end = handle_overnight_shift(d, brk.start_time, brk.end_time)

        # Clamp break to shift bounds
        effective_start = max(brk_start, shift_start)
        effective_end = min(brk_end, shift_end)

        if effective_end > effective_start:
            total += datetime_diff_hours(effective_start, effective_end)

    return total


def assemble_shifts(daily_records: list[DailyRecord]) -> list[Shift]:
    """Assemble shifts from daily records.

    For each work day, convert shift templates into actual Shift objects.
    Handles multi-segment shifts (gap <= 3h = same shift).

    Args:
        daily_records: List of daily records with shift templates

    Returns:
        List of assembled Shift objects
    """
    shifts: list[Shift] = []
    shift_counter = 0

    for record in daily_records:
        if not record.is_work_day or not record.shift_templates:
            continue

        # Sort shift templates by start time
        templates = sorted(record.shift_templates, key=lambda t: t.start_time)

        # Group templates into shifts based on gap rule
        current_segments: list[ShiftSegment] = []
        current_start: datetime | None = None
        current_end: datetime | None = None

        for template in templates:
            seg_start, seg_end = handle_overnight_shift(
                record.date, template.start_time, template.end_time
            )

            if current_segments:
                # Check gap from previous segment
                gap_hours = datetime_diff_hours(current_end, seg_start)

                if gap_hours > MAX_GAP_HOURS:
                    # Gap too large - finalize current shift and start new one
                    shift = _create_shift(
                        shift_counter,
                        record,
                        current_segments,
                        current_start,
                        current_end,
                    )
                    shifts.append(shift)
                    shift_counter += 1

                    # Start new shift
                    current_segments = []
                    current_start = seg_start

            else:
                current_start = seg_start

            current_segments.append(ShiftSegment(start=seg_start, end=seg_end))
            current_end = seg_end

        # Finalize last shift for this day
        if current_segments:
            shift = _create_shift(
                shift_counter,
                record,
                current_segments,
                current_start,
                current_end,
            )
            shifts.append(shift)
            shift_counter += 1

    return shifts


def _create_shift(
    shift_counter: int,
    record: DailyRecord,
    segments: list[ShiftSegment],
    start: datetime,
    end: datetime,
) -> Shift:
    """Create a Shift object from segments."""
    # Calculate gross hours (total time from start to end)
    gross_hours = datetime_diff_hours(start, end)

    # Calculate break hours
    break_hours = calculate_break_hours(
        record.break_templates,
        start,
        end,
        record.date,
    )

    # Net hours = gross - breaks
    net_hours = gross_hours - break_hours

    # Build break segments
    break_segments = []
    for brk in record.break_templates:
        brk_start, brk_end = handle_overnight_shift(record.date, brk.start_time, brk.end_time)
        if brk_start >= start and brk_end <= end:
            break_segments.append(ShiftSegment(start=brk_start, end=brk_end))

    return Shift(
        id=f"SHIFT_{shift_counter:04d}",
        date=record.date,
        shift_index=shift_counter,
        effective_period_id=record.effective_period_id,
        start=start,
        end=end,
        segments=segments,
        breaks=break_segments,
        net_hours=net_hours,
    )
