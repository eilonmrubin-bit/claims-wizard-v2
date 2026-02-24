"""Manual example: One shift through all 7 OT stages.

This script demonstrates the overtime calculation pipeline with concrete numbers.
"""

from datetime import date, time, datetime, timedelta
from decimal import Decimal

from app.ssot import DailyRecord, TimeRange, RestDay, District, WeekType
from app.modules.overtime import (
    OTConfig,
    assemble_shifts,
    assign_shifts,
    classify_weeks,
    resolve_thresholds,
    detect_daily_ot,
    detect_weekly_ot,
    place_rest_windows,
)


def run_manual_example():
    """Run a single shift through all 7 stages with visible output."""

    print("=" * 70)
    print("OVERTIME CALCULATION - MANUAL EXAMPLE")
    print("=" * 70)
    print()

    # === INPUT ===
    print("INPUT:")
    print("-" * 40)
    print("Date: Sunday, January 7, 2024")
    print("Shift: 07:00 - 18:00 (11 hours gross)")
    print("Break: 12:00 - 12:30 (30 minutes)")
    print("Rest day: Saturday")
    print("District: Tel Aviv")
    print()

    # Create daily record
    daily_record = DailyRecord(
        date=date(2024, 1, 7),  # Sunday
        effective_period_id="EP1",
        day_of_week=0,  # Sunday
        is_work_day=True,
        is_rest_day=False,
        shift_templates=[TimeRange(start_time=time(7, 0), end_time=time(18, 0))],
        break_templates=[TimeRange(start_time=time(12, 0), end_time=time(12, 30))],
    )

    # === STAGE 1: SHIFT ASSEMBLY ===
    print("STAGE 1: SHIFT ASSEMBLY")
    print("-" * 40)
    shifts = assemble_shifts([daily_record])
    shift = shifts[0]
    print(f"Start: {shift.start}")
    print(f"End: {shift.end}")
    print(f"Gross hours: 11.0")
    print(f"Break: 0.5 hours")
    print(f"Net hours: {shift.net_hours}")
    print()

    # === STAGE 2: SHIFT ASSIGNMENT ===
    print("STAGE 2: SHIFT ASSIGNMENT")
    print("-" * 40)
    shifts = assign_shifts(shifts)
    shift = shifts[0]
    print(f"Assigned day: {shift.assigned_day} ({shift.assigned_day.strftime('%A')})")
    print(f"Assigned week: {shift.assigned_week}")
    print()

    # === STAGE 3: WEEK CLASSIFICATION ===
    print("STAGE 3: WEEK CLASSIFICATION")
    print("-" * 40)
    weeks = classify_weeks(shifts)
    week = weeks[0]
    print(f"Week ID: {week.id}")
    print(f"Distinct work days: {week.distinct_work_days}")
    print(f"Week type: {week.week_type.value}-day week")
    print()

    # === STAGE 4: THRESHOLD RESOLUTION ===
    print("STAGE 4: THRESHOLD RESOLUTION")
    print("-" * 40)
    config = OTConfig()
    shifts = resolve_thresholds(shifts, weeks, RestDay.SATURDAY, District.TEL_AVIV, config)
    shift = shifts[0]
    print(f"Week type: {week.week_type.value}-day -> base threshold: {config.threshold_5day if week.week_type == WeekType.FIVE_DAY else config.threshold_6day}")
    print(f"Is night shift: No (7:00-18:00, no hours in 22:00-06:00)")
    print(f"Is eve of rest: No (Sunday is not Thursday/Friday)")
    print(f"Final threshold: {shift.threshold}")
    print(f"Reason: {shift.threshold_reason}")
    print()

    # === STAGE 5: DAILY OT DETECTION ===
    print("STAGE 5: DAILY OT DETECTION")
    print("-" * 40)
    shifts = detect_daily_ot(shifts, config)
    shift = shifts[0]
    print(f"Net hours: {shift.net_hours}")
    print(f"Threshold: {shift.threshold}")
    print(f"Calculation:")
    print(f"  Regular (Tier 0): min({shift.net_hours}, {shift.threshold}) = {shift.regular_hours}")
    print(f"  Overtime: {shift.net_hours} - {shift.threshold} = {shift.daily_ot_hours}")
    print(f"  Tier 1 (first 2h OT): min({shift.daily_ot_hours}, 2) = {shift.ot_tier1_hours}")
    print(f"  Tier 2 (remaining): {shift.daily_ot_hours} - {shift.ot_tier1_hours} = {shift.ot_tier2_hours}")
    print()
    print(f"Result:")
    print(f"  Regular hours: {shift.regular_hours}")
    print(f"  OT Tier 1 hours: {shift.ot_tier1_hours}")
    print(f"  OT Tier 2 hours: {shift.ot_tier2_hours}")
    print()

    # === STAGE 6: WEEKLY OT DETECTION ===
    print("STAGE 6: WEEKLY OT DETECTION")
    print("-" * 40)
    shifts, weeks = detect_weekly_ot(shifts, weeks, config)
    shift = shifts[0]
    week = weeks[0]
    print(f"Weekly regular total: {week.total_regular_hours}")
    print(f"Weekly cap: {config.weekly_cap}")
    print(f"Weekly OT: {week.weekly_ot_hours} (only if total > 42)")
    print(f"Shift weekly OT: {shift.weekly_ot_hours}")
    print()
    print(f"Final tier assignment (unified):")
    print(f"  Total OT (daily + weekly): {shift.daily_ot_hours + shift.weekly_ot_hours}")
    print(f"  Tier 1: {shift.ot_tier1_hours}")
    print(f"  Tier 2: {shift.ot_tier2_hours}")
    print()

    # === STAGE 7: REST WINDOW PLACEMENT ===
    print("STAGE 7: REST WINDOW PLACEMENT")
    print("-" * 40)
    shifts, weeks = place_rest_windows(shifts, weeks, RestDay.SATURDAY, District.TEL_AVIV)
    shift = shifts[0]
    week = weeks[0]
    print(f"Rest window start: {week.rest_window_start}")
    print(f"Rest window end: {week.rest_window_end}")
    print(f"Work hours in window: {week.rest_window_work_hours}")
    print()
    print(f"Shift classification:")
    print(f"  In rest window: regular={shift.rest_window_regular_hours:.4f}, "
          f"tier1={shift.rest_window_ot_tier1_hours:.4f}, "
          f"tier2={shift.rest_window_ot_tier2_hours:.4f}")
    print(f"  Outside window: regular={shift.non_rest_regular_hours:.4f}, "
          f"tier1={shift.non_rest_ot_tier1_hours:.4f}, "
          f"tier2={shift.non_rest_ot_tier2_hours:.4f}")
    print()

    # === SUMMARY ===
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Input: 11h gross shift, 0.5h break")
    print(f"Net hours: {shift.net_hours}")
    print(f"Threshold: {shift.threshold} (5-day week)")
    print()
    print("Hour breakdown:")
    print(f"  Regular (100%): {shift.regular_hours} hours")
    print(f"  OT Tier 1 (125%): {shift.ot_tier1_hours} hours")
    print(f"  OT Tier 2 (150%): {shift.ot_tier2_hours} hours")
    print()
    print("Note: This shift is on Sunday (outside rest window).")
    print("Pricing (Stage 8) will apply regular-day rates.")


if __name__ == "__main__":
    run_manual_example()
