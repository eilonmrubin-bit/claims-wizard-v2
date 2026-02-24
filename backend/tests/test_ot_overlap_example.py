"""Example: Shift overlapping with rest window."""

from datetime import date, time
from decimal import Decimal

from app.ssot import DailyRecord, TimeRange, RestDay, District
from app.modules.overtime import run_overtime_stages_1_to_7


def run_overlap_example():
    """Demonstrate shift overlapping with rest window."""

    print("=" * 70)
    print("SHIFT OVERLAPPING WITH REST WINDOW")
    print("=" * 70)
    print()

    # Friday shift 14:00-22:00 (8 hours)
    # Rest window starts at ~16:30 (candle lighting)
    # So: 2.5h outside window (14:00-16:30), 5.5h inside window (16:30-22:00)

    print("INPUT:")
    print("-" * 40)
    print("Date: Friday, January 12, 2024")
    print("Shift: 14:00 - 22:00 (8 hours)")
    print("Rest day: Saturday")
    print("Candle lighting: ~16:30 (default)")
    print()

    record = DailyRecord(
        date=date(2024, 1, 12),  # Friday
        effective_period_id="EP1",
        day_of_week=4,  # Friday
        is_work_day=True,
        is_rest_day=False,
        shift_templates=[TimeRange(start_time=time(14, 0), end_time=time(22, 0))],
        break_templates=[],
    )

    result = run_overtime_stages_1_to_7(
        [record], RestDay.SATURDAY, District.TEL_AVIV
    )

    shift = result.shifts[0]
    week = result.weeks[0]

    print("THRESHOLD:")
    print("-" * 40)
    print(f"Threshold: {shift.threshold} ({shift.threshold_reason})")
    print(f"Friday = eve of rest -> threshold 7.0")
    print()

    print("OT DETECTION:")
    print("-" * 40)
    print(f"Net hours: {shift.net_hours}")
    print(f"Regular: {shift.regular_hours}")
    print(f"OT Tier 1: {shift.ot_tier1_hours}")
    print(f"OT Tier 2: {shift.ot_tier2_hours}")
    print()

    print("REST WINDOW:")
    print("-" * 40)
    print(f"Window start: {week.rest_window_start}")
    print(f"Window end: {week.rest_window_end}")
    print(f"Shift: {shift.start} to {shift.end}")
    print()

    print("HOUR CLASSIFICATION:")
    print("-" * 40)
    print(f"Hours INSIDE rest window (150%/175%/200% rates):")
    print(f"  Regular: {shift.rest_window_regular_hours:.2f}")
    print(f"  OT Tier 1: {shift.rest_window_ot_tier1_hours:.2f}")
    print(f"  OT Tier 2: {shift.rest_window_ot_tier2_hours:.2f}")
    print()
    print(f"Hours OUTSIDE rest window (100%/125%/150% rates):")
    print(f"  Regular: {shift.non_rest_regular_hours:.2f}")
    print(f"  OT Tier 1: {shift.non_rest_ot_tier1_hours:.2f}")
    print(f"  OT Tier 2: {shift.non_rest_ot_tier2_hours:.2f}")
    print()

    # Calculate actual overlap
    window_start = week.rest_window_start
    shift_start = shift.start
    shift_end = shift.end

    if shift_start < window_start < shift_end:
        hours_before_window = (window_start - shift_start).total_seconds() / 3600
        hours_in_window = (shift_end - window_start).total_seconds() / 3600
        print("ACTUAL OVERLAP CALCULATION:")
        print("-" * 40)
        print(f"Shift start: {shift_start.strftime('%H:%M')}")
        print(f"Window start: {window_start.strftime('%H:%M')}")
        print(f"Shift end: {shift_end.strftime('%H:%M')}")
        print(f"Hours before window: {hours_before_window:.1f}h")
        print(f"Hours in window: {hours_in_window:.1f}h")
        print()

    print("PRICING IMPACT (Stage 8):")
    print("-" * 40)
    print("Inside rest window:")
    print("  - Regular hours: 150% rate (50% claim)")
    print("  - OT Tier 1: 175% rate (75% claim)")
    print("  - OT Tier 2: 200% rate (100% claim)")
    print()
    print("Outside rest window:")
    print("  - Regular hours: 100% rate (0% claim)")
    print("  - OT Tier 1: 125% rate (25% claim)")
    print("  - OT Tier 2: 150% rate (50% claim)")


if __name__ == "__main__":
    run_overlap_example()
