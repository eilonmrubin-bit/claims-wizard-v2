"""Snapshot utilities for querying SSOT data.

Provides functions to consolidate all SSOT data for a specific
day, week, or month into a single snapshot object.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..ssot import SSOT

from ..ssot import (
    DailyRecord,
    Shift,
    EffectivePeriod,
    SeniorityMonthly,
    PeriodMonthRecord,
    MonthAggregate,
    Week,
)


# =============================================================================
# Day Snapshot
# =============================================================================

@dataclass
class DaySnapshot:
    """All SSOT data for a specific day, consolidated in one place.

    Use get_day_snapshot(ssot, target_date) to create.
    """
    target_date: date

    # From daily_records
    daily_record: DailyRecord | None = None

    # From shifts (may be multiple per day)
    shifts: list[Shift] = field(default_factory=list)

    # From effective_periods
    effective_period: EffectivePeriod | None = None

    # From seniority_monthly (for the month containing target_date)
    seniority: SeniorityMonthly | None = None

    # From period_month_records (for the period×month containing target_date)
    salary: PeriodMonthRecord | None = None

    # From month_aggregates (for the month containing target_date)
    month_aggregate: MonthAggregate | None = None

    # From weeks (the week containing target_date)
    week: Week | None = None

    # Computed summary
    total_hours: Decimal = Decimal("0")
    total_ot_hours: Decimal = Decimal("0")
    total_claim: Decimal = Decimal("0")


def get_day_snapshot(ssot: "SSOT", target_date: date) -> DaySnapshot:
    """Get consolidated snapshot of all SSOT data for a specific day.

    Args:
        ssot: The SSOT to query
        target_date: The date to get data for

    Returns:
        DaySnapshot with all relevant data for that day
    """
    snapshot = DaySnapshot(target_date=target_date)

    # Find daily_record
    for dr in ssot.daily_records:
        if dr.date == target_date:
            snapshot.daily_record = dr
            break

    # Find all shifts for this day
    for shift in ssot.shifts:
        if shift.assigned_day == target_date:
            snapshot.shifts.append(shift)
            snapshot.total_hours += shift.net_hours
            snapshot.total_ot_hours += shift.ot_tier1_hours + shift.ot_tier2_hours
            if shift.claim_amount:
                snapshot.total_claim += shift.claim_amount

    # Find effective_period
    for ep in ssot.effective_periods:
        if ep.start <= target_date <= ep.end:
            snapshot.effective_period = ep
            break

    # Find seniority for this month
    target_month = (target_date.year, target_date.month)
    for sen in ssot.seniority_monthly:
        if sen.month == target_month:
            snapshot.seniority = sen
            break

    # Find salary (period_month_record)
    if snapshot.effective_period:
        for pmr in ssot.period_month_records:
            if (pmr.effective_period_id == snapshot.effective_period.id
                    and pmr.month == target_month):
                snapshot.salary = pmr
                break

    # Find month_aggregate
    for ma in ssot.month_aggregates:
        if ma.month == target_month:
            snapshot.month_aggregate = ma
            break

    # Find week
    for week in ssot.weeks:
        if week.start_date and week.end_date:
            if week.start_date <= target_date <= week.end_date:
                snapshot.week = week
                break

    return snapshot


def format_day_snapshot(snapshot: DaySnapshot) -> str:
    """Format a DaySnapshot as a readable string.

    Args:
        snapshot: The snapshot to format

    Returns:
        Human-readable string representation
    """
    lines = []
    lines.append(f"=== יום {snapshot.target_date} ===")
    lines.append("")

    # Daily record
    if snapshot.daily_record:
        dr = snapshot.daily_record
        work_str = "יום עבודה" if dr.is_work_day else "לא עובד"
        rest_str = " (יום מנוחה)" if dr.is_rest_day else ""
        lines.append(f"[רשומה יומית]")
        lines.append(f"  סטטוס: {work_str}{rest_str}")
        lines.append(f"  יום בשבוע: {dr.day_of_week}")
        lines.append(f"  תקופה: {dr.effective_period_id}")
        if dr.shift_templates:
            for i, st in enumerate(dr.shift_templates):
                lines.append(f"  משמרת {i+1}: {st.start_time} - {st.end_time}")
    else:
        lines.append("[רשומה יומית] לא נמצאה")

    lines.append("")

    # Shifts
    if snapshot.shifts:
        lines.append(f"[משמרות] ({len(snapshot.shifts)})")
        for shift in snapshot.shifts:
            lines.append(f"  {shift.id}:")
            lines.append(f"    שעות נטו: {shift.net_hours:.2f}")
            lines.append(f"    רגילות: {shift.regular_hours:.2f}")
            lines.append(f"    OT tier1: {shift.ot_tier1_hours:.2f}")
            lines.append(f"    OT tier2: {shift.ot_tier2_hours:.2f}")
            if shift.claim_amount:
                lines.append(f"    תביעה: {shift.claim_amount:.2f} ש״ח")
    else:
        lines.append("[משמרות] אין")

    lines.append("")

    # Effective period
    if snapshot.effective_period:
        ep = snapshot.effective_period
        lines.append(f"[תקופה אפקטיבית]")
        lines.append(f"  ID: {ep.id}")
        lines.append(f"  טווח: {ep.start} עד {ep.end}")
        lines.append(f"  שכר: {ep.salary_amount} ({ep.salary_type.value})")
    else:
        lines.append("[תקופה אפקטיבית] לא נמצאה")

    lines.append("")

    # Salary
    if snapshot.salary:
        sal = snapshot.salary
        lines.append(f"[שכר - חודש {sal.month}]")
        lines.append(f"  שעתי: {sal.salary_hourly:.2f} ש״ח")
        lines.append(f"  יומי: {sal.salary_daily:.2f} ש״ח")
        lines.append(f"  חודשי: {sal.salary_monthly:.2f} ש״ח")
        if sal.minimum_applied:
            lines.append(f"  * הופעל שכר מינימום: {sal.minimum_wage_value:.2f}")
    else:
        lines.append("[שכר] לא נמצא")

    lines.append("")

    # Seniority
    if snapshot.seniority:
        sen = snapshot.seniority
        lines.append(f"[ותק - חודש {sen.month}]")
        lines.append(f"  אצל נתבע: {sen.at_defendant_cumulative} חודשים")
        lines.append(f"  ענפי: {sen.total_industry_cumulative} חודשים")
    else:
        lines.append("[ותק] לא נמצא")

    lines.append("")

    # Week
    if snapshot.week:
        w = snapshot.week
        week_type_str = "5 ימים" if w.week_type.value == 5 else "6 ימים"
        lines.append(f"[שבוע {w.id}]")
        lines.append(f"  סוג: {week_type_str}")
        lines.append(f"  ימי עבודה: {w.distinct_work_days}")
        lines.append(f"  שעות רגילות: {w.total_regular_hours:.2f}")
        lines.append(f"  OT שבועי: {w.weekly_ot_hours:.2f}")
    else:
        lines.append("[שבוע] לא נמצא")

    lines.append("")

    # Summary
    lines.append(f"[סיכום יום]")
    lines.append(f"  סה״כ שעות: {snapshot.total_hours:.2f}")
    lines.append(f"  סה״כ OT: {snapshot.total_ot_hours:.2f}")
    lines.append(f"  סה״כ תביעה: {snapshot.total_claim:.2f} ש״ח")

    return "\n".join(lines)


# =============================================================================
# Week Snapshot
# =============================================================================

@dataclass
class WeekSnapshot:
    """All SSOT data for a specific week, consolidated in one place.

    Use get_week_snapshot(ssot, week_id) to create.
    """
    week_id: str

    # The week record
    week: Week | None = None

    # All daily records in this week
    daily_records: list[DailyRecord] = field(default_factory=list)

    # All shifts in this week
    shifts: list[Shift] = field(default_factory=list)

    # Effective periods active during this week
    effective_periods: list[EffectivePeriod] = field(default_factory=list)

    # Computed summary
    total_hours: Decimal = Decimal("0")
    total_regular_hours: Decimal = Decimal("0")
    total_ot_hours: Decimal = Decimal("0")
    total_claim: Decimal = Decimal("0")
    work_days_count: int = 0
    shifts_count: int = 0


def get_week_snapshot(ssot: "SSOT", week_id: str) -> WeekSnapshot:
    """Get consolidated snapshot of all SSOT data for a specific week.

    Args:
        ssot: The SSOT to query
        week_id: The week ID (e.g., "2023-W20")

    Returns:
        WeekSnapshot with all relevant data for that week
    """
    snapshot = WeekSnapshot(week_id=week_id)

    # Find the week
    for week in ssot.weeks:
        if week.id == week_id:
            snapshot.week = week
            break

    if not snapshot.week or not snapshot.week.start_date or not snapshot.week.end_date:
        return snapshot

    start = snapshot.week.start_date
    end = snapshot.week.end_date

    # Find all daily records in this week
    for dr in ssot.daily_records:
        if start <= dr.date <= end:
            snapshot.daily_records.append(dr)
            if dr.is_work_day:
                snapshot.work_days_count += 1

    # Find all shifts in this week
    for shift in ssot.shifts:
        if shift.assigned_week == week_id:
            snapshot.shifts.append(shift)
            snapshot.shifts_count += 1
            snapshot.total_hours += shift.net_hours
            snapshot.total_regular_hours += shift.regular_hours
            snapshot.total_ot_hours += shift.ot_tier1_hours + shift.ot_tier2_hours
            if shift.claim_amount:
                snapshot.total_claim += shift.claim_amount

    # Find effective periods active during this week
    ep_ids = set()
    for ep in ssot.effective_periods:
        if ep.start <= end and ep.end >= start:
            if ep.id not in ep_ids:
                snapshot.effective_periods.append(ep)
                ep_ids.add(ep.id)

    return snapshot


def format_week_snapshot(snapshot: WeekSnapshot) -> str:
    """Format a WeekSnapshot as a readable string.

    Args:
        snapshot: The snapshot to format

    Returns:
        Human-readable string representation
    """
    lines = []
    lines.append(f"=== שבוע {snapshot.week_id} ===")
    lines.append("")

    # Week info
    if snapshot.week:
        w = snapshot.week
        week_type_str = "5 ימים" if w.week_type.value == 5 else "6 ימים"
        lines.append(f"[פרטי שבוע]")
        lines.append(f"  טווח: {w.start_date} עד {w.end_date}")
        lines.append(f"  סוג: {week_type_str}")
        lines.append(f"  ימי עבודה בפועל: {w.distinct_work_days}")
        if w.is_partial:
            lines.append(f"  * שבוע חלקי: {w.partial_reason}")
        if w.rest_window_start and w.rest_window_end:
            lines.append(f"  חלון מנוחה: {w.rest_window_start} - {w.rest_window_end}")
    else:
        lines.append("[פרטי שבוע] לא נמצא")

    lines.append("")

    # Daily records summary
    lines.append(f"[ימים] ({len(snapshot.daily_records)})")
    for dr in sorted(snapshot.daily_records, key=lambda x: x.date):
        work_str = "V" if dr.is_work_day else "-"
        rest_str = "(מנוחה)" if dr.is_rest_day else ""
        lines.append(f"  {dr.date} [{work_str}] {rest_str}")

    lines.append("")

    # Shifts summary
    lines.append(f"[משמרות] ({snapshot.shifts_count})")
    if snapshot.shifts:
        # Group by day
        shifts_by_day: dict[date, list[Shift]] = {}
        for s in snapshot.shifts:
            if s.assigned_day:
                if s.assigned_day not in shifts_by_day:
                    shifts_by_day[s.assigned_day] = []
                shifts_by_day[s.assigned_day].append(s)

        for day in sorted(shifts_by_day.keys()):
            day_shifts = shifts_by_day[day]
            day_hours = sum(s.net_hours for s in day_shifts)
            day_claim = sum(s.claim_amount or Decimal("0") for s in day_shifts)
            lines.append(f"  {day}: {len(day_shifts)} משמרות, {day_hours:.2f} שעות, {day_claim:.2f} ש״ח")
    else:
        lines.append("  אין משמרות")

    lines.append("")

    # Effective periods
    lines.append(f"[תקופות אפקטיביות] ({len(snapshot.effective_periods)})")
    for ep in snapshot.effective_periods:
        lines.append(f"  {ep.id}: {ep.salary_amount} ({ep.salary_type.value})")

    lines.append("")

    # Summary
    lines.append(f"[סיכום שבוע]")
    lines.append(f"  ימי עבודה: {snapshot.work_days_count}")
    lines.append(f"  משמרות: {snapshot.shifts_count}")
    lines.append(f"  סה״כ שעות: {snapshot.total_hours:.2f}")
    lines.append(f"  שעות רגילות: {snapshot.total_regular_hours:.2f}")
    lines.append(f"  שעות OT: {snapshot.total_ot_hours:.2f}")
    lines.append(f"  סה״כ תביעה: {snapshot.total_claim:.2f} ש״ח")

    return "\n".join(lines)


# =============================================================================
# Month Snapshot
# =============================================================================

@dataclass
class MonthSnapshot:
    """All SSOT data for a specific month, consolidated in one place.

    Use get_month_snapshot(ssot, year, month) to create.
    """
    year: int
    month: int

    @property
    def month_tuple(self) -> tuple[int, int]:
        return (self.year, self.month)

    # Month aggregate
    month_aggregate: MonthAggregate | None = None

    # Period month records (may be multiple if salary changed mid-month)
    period_month_records: list[PeriodMonthRecord] = field(default_factory=list)

    # Seniority for this month
    seniority: SeniorityMonthly | None = None

    # All daily records in this month
    daily_records: list[DailyRecord] = field(default_factory=list)

    # All shifts in this month
    shifts: list[Shift] = field(default_factory=list)

    # All weeks that overlap this month
    weeks: list[Week] = field(default_factory=list)

    # Effective periods active during this month
    effective_periods: list[EffectivePeriod] = field(default_factory=list)

    # Computed summary
    total_hours: Decimal = Decimal("0")
    total_regular_hours: Decimal = Decimal("0")
    total_ot_hours: Decimal = Decimal("0")
    total_claim: Decimal = Decimal("0")
    work_days_count: int = 0
    shifts_count: int = 0
    avg_salary_hourly: Decimal = Decimal("0")


def get_month_snapshot(ssot: "SSOT", year: int, month: int) -> MonthSnapshot:
    """Get consolidated snapshot of all SSOT data for a specific month.

    Args:
        ssot: The SSOT to query
        year: The year
        month: The month (1-12)

    Returns:
        MonthSnapshot with all relevant data for that month
    """
    import calendar

    snapshot = MonthSnapshot(year=year, month=month)
    target_month = (year, month)

    # Get month boundaries
    _, last_day = calendar.monthrange(year, month)
    month_start = date(year, month, 1)
    month_end = date(year, month, last_day)

    # Find month aggregate
    for ma in ssot.month_aggregates:
        if ma.month == target_month:
            snapshot.month_aggregate = ma
            break

    # Find period month records
    for pmr in ssot.period_month_records:
        if pmr.month == target_month:
            snapshot.period_month_records.append(pmr)

    # Find seniority
    for sen in ssot.seniority_monthly:
        if sen.month == target_month:
            snapshot.seniority = sen
            break

    # Find daily records
    for dr in ssot.daily_records:
        if dr.date.year == year and dr.date.month == month:
            snapshot.daily_records.append(dr)
            if dr.is_work_day:
                snapshot.work_days_count += 1

    # Find shifts
    for shift in ssot.shifts:
        if shift.assigned_day and shift.assigned_day.year == year and shift.assigned_day.month == month:
            snapshot.shifts.append(shift)
            snapshot.shifts_count += 1
            snapshot.total_hours += shift.net_hours
            snapshot.total_regular_hours += shift.regular_hours
            snapshot.total_ot_hours += shift.ot_tier1_hours + shift.ot_tier2_hours
            if shift.claim_amount:
                snapshot.total_claim += shift.claim_amount

    # Find weeks that overlap this month
    week_ids = set()
    for week in ssot.weeks:
        if week.start_date and week.end_date:
            if week.start_date <= month_end and week.end_date >= month_start:
                if week.id not in week_ids:
                    snapshot.weeks.append(week)
                    week_ids.add(week.id)

    # Find effective periods
    ep_ids = set()
    for ep in ssot.effective_periods:
        if ep.start <= month_end and ep.end >= month_start:
            if ep.id not in ep_ids:
                snapshot.effective_periods.append(ep)
                ep_ids.add(ep.id)

    # Calculate average hourly salary
    if snapshot.period_month_records:
        total_salary = sum(pmr.salary_hourly for pmr in snapshot.period_month_records)
        snapshot.avg_salary_hourly = total_salary / len(snapshot.period_month_records)

    return snapshot


def format_month_snapshot(snapshot: MonthSnapshot) -> str:
    """Format a MonthSnapshot as a readable string.

    Args:
        snapshot: The snapshot to format

    Returns:
        Human-readable string representation
    """
    month_names = {
        1: "ינואר", 2: "פברואר", 3: "מרץ", 4: "אפריל",
        5: "מאי", 6: "יוני", 7: "יולי", 8: "אוגוסט",
        9: "ספטמבר", 10: "אוקטובר", 11: "נובמבר", 12: "דצמבר",
    }

    lines = []
    month_name = month_names.get(snapshot.month, str(snapshot.month))
    lines.append(f"=== {month_name} {snapshot.year} ===")
    lines.append("")

    # Month aggregate
    if snapshot.month_aggregate:
        ma = snapshot.month_aggregate
        lines.append(f"[אגרגט חודשי]")
        lines.append(f"  שעות רגילות: {ma.total_regular_hours:.2f}")
        lines.append(f"  שעות OT: {ma.total_ot_hours:.2f}")
        lines.append(f"  ימי עבודה: {ma.total_work_days}")
        lines.append(f"  משמרות: {ma.total_shifts}")
        lines.append(f"  היקף משרה: {ma.job_scope:.2%}")
    else:
        lines.append("[אגרגט חודשי] לא נמצא")

    lines.append("")

    # Salary records
    lines.append(f"[שכר] ({len(snapshot.period_month_records)} רשומות)")
    for pmr in snapshot.period_month_records:
        lines.append(f"  תקופה {pmr.effective_period_id}:")
        lines.append(f"    שעתי: {pmr.salary_hourly:.2f} ש״ח")
        lines.append(f"    יומי: {pmr.salary_daily:.2f} ש״ח")
        lines.append(f"    חודשי: {pmr.salary_monthly:.2f} ש״ח")
        if pmr.minimum_applied:
            lines.append(f"    * הופעל שכר מינימום")

    lines.append("")

    # Seniority
    if snapshot.seniority:
        sen = snapshot.seniority
        lines.append(f"[ותק]")
        lines.append(f"  אצל נתבע: {sen.at_defendant_cumulative} חודשים ({sen.at_defendant_years_cumulative:.2f} שנים)")
        lines.append(f"  ענפי: {sen.total_industry_cumulative} חודשים ({sen.total_industry_years_cumulative:.2f} שנים)")
    else:
        lines.append("[ותק] לא נמצא")

    lines.append("")

    # Weeks
    lines.append(f"[שבועות] ({len(snapshot.weeks)})")
    for w in sorted(snapshot.weeks, key=lambda x: x.start_date or date.min):
        week_type_str = "5 ימים" if w.week_type.value == 5 else "6 ימים"
        lines.append(f"  {w.id}: {week_type_str}, {w.distinct_work_days} ימי עבודה")

    lines.append("")

    # Effective periods
    lines.append(f"[תקופות אפקטיביות] ({len(snapshot.effective_periods)})")
    for ep in snapshot.effective_periods:
        lines.append(f"  {ep.id}: {ep.start} - {ep.end}")
        lines.append(f"    שכר: {ep.salary_amount} ({ep.salary_type.value})")

    lines.append("")

    # Daily summary
    lines.append(f"[ימים]")
    lines.append(f"  סה״כ ימים: {len(snapshot.daily_records)}")
    lines.append(f"  ימי עבודה: {snapshot.work_days_count}")

    lines.append("")

    # Summary
    lines.append(f"[סיכום חודש]")
    lines.append(f"  משמרות: {snapshot.shifts_count}")
    lines.append(f"  סה״כ שעות: {snapshot.total_hours:.2f}")
    lines.append(f"  שעות רגילות: {snapshot.total_regular_hours:.2f}")
    lines.append(f"  שעות OT: {snapshot.total_ot_hours:.2f}")
    lines.append(f"  סה״כ תביעה: {snapshot.total_claim:.2f} ש״ח")
    if snapshot.avg_salary_hourly > 0:
        lines.append(f"  שכר שעתי ממוצע: {snapshot.avg_salary_hourly:.2f} ש״ח")

    return "\n".join(lines)
