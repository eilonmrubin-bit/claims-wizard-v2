"""Aggregator module — aggregates shifts to monthly level.

Groups shifts into:
1. period_month_records: (effective_period × month) with hours fields
2. month_aggregates: monthly totals across all periods

See docs/skills/aggregator/SKILL.md for complete documentation.
"""

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from app.ssot import (
    Shift,
    PeriodMonthRecord,
    MonthAggregate,
)


@dataclass
class AggregatorResult:
    """Result of aggregator computation."""
    period_month_records: list[PeriodMonthRecord]
    month_aggregates: list[MonthAggregate]


def _aggregate_by_period_month(shifts: list[Shift]) -> list[PeriodMonthRecord]:
    """Group shifts by (effective_period_id, year, month).

    Returns list of PeriodMonthRecord with hours fields populated.
    """
    # Group shifts into buckets
    buckets: dict[tuple[str, int, int], list[Shift]] = defaultdict(list)

    for shift in shifts:
        if shift.assigned_day is None:
            continue
        key = (
            shift.effective_period_id,
            shift.assigned_day.year,
            shift.assigned_day.month,
        )
        buckets[key].append(shift)

    # Compute aggregates for each bucket
    result = []
    for (ep_id, year, month), bucket_shifts in buckets.items():
        # Count distinct work days
        work_days = len(set(s.assigned_day for s in bucket_shifts))
        shifts_count = len(bucket_shifts)

        # Sum hours
        total_regular = sum(
            (s.regular_hours for s in bucket_shifts),
            start=Decimal("0"),
        )
        total_ot = sum(
            (s.ot_tier1_hours + s.ot_tier2_hours for s in bucket_shifts),
            start=Decimal("0"),
        )

        # Compute averages (no division by zero - bucket is never empty)
        avg_per_day = total_regular / Decimal(work_days) if work_days > 0 else Decimal("0")
        avg_per_shift = total_regular / Decimal(shifts_count) if shifts_count > 0 else Decimal("0")

        # Total hours (regular + OT) for salary conversion
        # A daily wage covers the entire shift, not just regular hours
        total_hours = total_regular + total_ot
        avg_total_per_day = total_hours / Decimal(work_days) if work_days > 0 else Decimal("0")
        avg_total_per_shift = total_hours / Decimal(shifts_count) if shifts_count > 0 else Decimal("0")

        result.append(PeriodMonthRecord(
            effective_period_id=ep_id,
            month=(year, month),
            work_days_count=work_days,
            shifts_count=shifts_count,
            total_regular_hours=total_regular,
            total_ot_hours=total_ot,
            avg_regular_hours_per_day=avg_per_day,
            avg_regular_hours_per_shift=avg_per_shift,
            avg_total_hours_per_day=avg_total_per_day,
            avg_total_hours_per_shift=avg_total_per_shift,
        ))

    # Sort by period_id, then by month for consistent output
    result.sort(key=lambda r: (r.effective_period_id, r.month))
    return result


def _aggregate_by_month(
    period_month_records: list[PeriodMonthRecord],
) -> list[MonthAggregate]:
    """Aggregate period_month_records by month (across all periods).

    Returns list of MonthAggregate with hours fields populated.
    """
    buckets: dict[tuple[int, int], list[PeriodMonthRecord]] = defaultdict(list)

    for pmr in period_month_records:
        buckets[pmr.month].append(pmr)

    result = []
    for month, pmrs in buckets.items():
        total_regular = sum(
            (p.total_regular_hours for p in pmrs),
            start=Decimal("0"),
        )
        total_ot = sum(
            (p.total_ot_hours for p in pmrs),
            start=Decimal("0"),
        )
        total_work_days = sum(p.work_days_count for p in pmrs)
        total_shifts = sum(p.shifts_count for p in pmrs)

        result.append(MonthAggregate(
            month=month,
            total_regular_hours=total_regular,
            total_ot_hours=total_ot,
            total_work_days=total_work_days,
            total_shifts=total_shifts,
        ))

    # Sort by month for consistent output
    result.sort(key=lambda r: r.month)
    return result


def run_aggregator(shifts: list[Shift]) -> AggregatorResult:
    """Main entry point for aggregator module.

    Args:
        shifts: List of shifts from OT pipeline (stages 1-7)

    Returns:
        AggregatorResult with period_month_records and month_aggregates
    """
    period_month_records = _aggregate_by_period_month(shifts)
    month_aggregates = _aggregate_by_month(period_month_records)

    return AggregatorResult(
        period_month_records=period_month_records,
        month_aggregates=month_aggregates,
    )
