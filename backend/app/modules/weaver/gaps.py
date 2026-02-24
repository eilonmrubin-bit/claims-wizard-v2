"""Stage 4: Detect employment gaps and compute total employment summary.

Gaps are identified between employment_periods (not effective_periods).
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from app.ssot import (
    Duration,
    EmploymentGap,
    TotalEmployment,
)

from .sweep import compute_duration


def detect_gaps(employment_periods: list[Any]) -> list[EmploymentGap]:
    """Detect gaps between employment periods.

    A gap exists when there's at least one day between the end of one
    employment period and the start of the next.
    """
    if len(employment_periods) < 2:
        return []

    # Sort by start date
    sorted_eps = sorted(employment_periods, key=lambda x: x.start)

    gaps = []

    for i in range(1, len(sorted_eps)):
        prev = sorted_eps[i - 1]
        curr = sorted_eps[i]

        gap_start = prev.end + timedelta(days=1)

        # Gap exists if there's at least one day
        if gap_start < curr.start:
            gap_end = curr.start - timedelta(days=1)

            gaps.append(EmploymentGap(
                start=gap_start,
                end=gap_end,
                duration=compute_duration(gap_start, gap_end),
                before_period_id=prev.id,
                after_period_id=curr.id,
            ))

    return gaps


def sum_durations(periods: list[Any]) -> Duration:
    """Sum durations of multiple periods.

    Uses compute_duration for each period and sums the results.
    """
    if not periods:
        return Duration()

    total_days = 0

    for period in periods:
        if hasattr(period, 'start') and hasattr(period, 'end'):
            days = (period.end - period.start).days + 1
            total_days += days
        elif hasattr(period, 'duration') and hasattr(period.duration, 'days'):
            total_days += period.duration.days

    # Compute duration from total days
    if total_days == 0:
        return Duration()

    months_decimal = Decimal(total_days) / Decimal("30")
    years_decimal = Decimal(total_days) / Decimal("365")
    months_whole = total_days // 30
    days_remainder = total_days % 30
    years_whole = total_days // 365
    remaining_after_years = total_days % 365
    months_remainder = remaining_after_years // 30

    return Duration(
        days=total_days,
        months_decimal=months_decimal,
        years_decimal=years_decimal,
        months_whole=months_whole,
        days_remainder=days_remainder,
        years_whole=years_whole,
        months_remainder=months_remainder,
        display="",
    )


def compute_total_employment(
    employment_periods: list[Any],
    gaps: list[EmploymentGap]
) -> TotalEmployment:
    """Compute summary of entire employment period."""
    if not employment_periods:
        return TotalEmployment()

    # Sort by start date
    sorted_eps = sorted(employment_periods, key=lambda x: x.start)

    first_day = sorted_eps[0].start
    last_day = sorted_eps[-1].end

    # Total duration (from first to last, including gaps)
    total_duration = compute_duration(first_day, last_day)

    # Worked duration (sum of all employment periods)
    worked_duration = sum_durations(employment_periods)

    # Gap duration (sum of all gaps)
    gap_duration = sum_durations(gaps)

    return TotalEmployment(
        first_day=first_day,
        last_day=last_day,
        total_duration=total_duration,
        worked_duration=worked_duration,
        gap_duration=gap_duration,
        periods_count=len(employment_periods),
        gaps_count=len(gaps),
    )
