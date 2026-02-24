"""Tests for overtime calculation stages 1-7.

Based on test cases from skill documentation.
"""

from datetime import date, time, datetime, timedelta
from decimal import Decimal

import pytest

from app.ssot import (
    DailyRecord,
    TimeRange,
    Shift,
    Week,
    RestDay,
    District,
    WeekType,
)
from app.modules.overtime import (
    OTConfig,
    assemble_shifts,
    assign_shifts,
    classify_weeks,
    resolve_thresholds,
    detect_daily_ot,
    detect_weekly_ot,
    place_rest_windows,
    run_overtime_stages_1_to_7,
)


# =============================================================================
# Helpers
# =============================================================================

def make_daily_record(
    d: date,
    shift_start: time,
    shift_end: time,
    break_start: time = None,
    break_end: time = None,
    ep_id: str = "EP1",
) -> DailyRecord:
    """Create a daily record for testing."""
    return DailyRecord(
        date=d,
        effective_period_id=ep_id,
        day_of_week=d.weekday(),
        is_work_day=True,
        is_rest_day=False,
        shift_templates=[TimeRange(start_time=shift_start, end_time=shift_end)],
        break_templates=[TimeRange(start_time=break_start, end_time=break_end)] if break_start else [],
    )


# =============================================================================
# Stage 1: Shift Assembly Tests
# =============================================================================

class TestStage1Assembly:
    """Tests for shift assembly."""

    def test_simple_shift(self):
        """Simple shift with break."""
        record = make_daily_record(
            date(2024, 1, 7),
            time(8, 0), time(17, 0),
            time(12, 0), time(12, 30),
        )
        shifts = assemble_shifts([record])

        assert len(shifts) == 1
        assert shifts[0].net_hours == Decimal("8.5")  # 9h - 0.5h break

    def test_overnight_shift(self):
        """Shift crossing midnight."""
        record = make_daily_record(
            date(2024, 1, 7),
            time(22, 0), time(6, 0),  # Crosses midnight
        )
        shifts = assemble_shifts([record])

        assert len(shifts) == 1
        assert shifts[0].net_hours == Decimal("8")  # 22:00 to 06:00 = 8h

    def test_no_break(self):
        """Shift without break."""
        record = make_daily_record(
            date(2024, 1, 7),
            time(8, 0), time(14, 0),
        )
        shifts = assemble_shifts([record])

        assert len(shifts) == 1
        assert shifts[0].net_hours == Decimal("6")


# =============================================================================
# Stage 2: Shift Assignment Tests
# =============================================================================

class TestStage2Assignment:
    """Tests for day and week assignment."""

    def test_same_day_assignment(self):
        """Shift within one day."""
        record = make_daily_record(date(2024, 1, 7), time(8, 0), time(17, 0))
        shifts = assemble_shifts([record])
        shifts = assign_shifts(shifts)

        assert shifts[0].assigned_day == date(2024, 1, 7)

    def test_overnight_majority_rule(self):
        """Overnight shift uses majority rule."""
        record = make_daily_record(
            date(2024, 1, 7),
            time(20, 0), time(4, 0),  # 4h Sun, 4h Mon - tie = earlier
        )
        shifts = assemble_shifts([record])
        shifts = assign_shifts(shifts)

        # 20:00-24:00 = 4h on Sunday, 00:00-04:00 = 4h on Monday
        # Tie -> earlier day (Sunday)
        assert shifts[0].assigned_day == date(2024, 1, 7)

    def test_overnight_majority_next_day(self):
        """Overnight shift majority on next day."""
        record = make_daily_record(
            date(2024, 1, 7),
            time(23, 0), time(7, 0),  # 1h Sun, 7h Mon
        )
        shifts = assemble_shifts([record])
        shifts = assign_shifts(shifts)

        # Majority on Monday
        assert shifts[0].assigned_day == date(2024, 1, 8)


# =============================================================================
# Stage 3: Week Classification Tests
# =============================================================================

class TestStage3Classification:
    """Tests for week classification."""

    def test_five_day_week(self):
        """5 work days = 5-day week."""
        records = [
            make_daily_record(date(2024, 1, 7 + i), time(8, 0), time(17, 0))
            for i in range(5)  # Sun-Thu
        ]
        shifts = assemble_shifts(records)
        shifts = assign_shifts(shifts)
        weeks = classify_weeks(shifts)

        assert len(weeks) == 1
        assert weeks[0].week_type == WeekType.FIVE_DAY
        assert weeks[0].distinct_work_days == 5

    def test_six_day_week(self):
        """6 work days = 6-day week."""
        records = [
            make_daily_record(date(2024, 1, 7 + i), time(8, 0), time(17, 0))
            for i in range(6)  # Sun-Fri
        ]
        shifts = assemble_shifts(records)
        shifts = assign_shifts(shifts)
        weeks = classify_weeks(shifts)

        assert len(weeks) == 1
        assert weeks[0].week_type == WeekType.SIX_DAY
        assert weeks[0].distinct_work_days == 6


# =============================================================================
# Stage 4: Threshold Resolution Tests
# =============================================================================

class TestStage4Threshold:
    """Tests for threshold resolution."""

    def test_threshold_5day_week(self):
        """5-day week threshold = 8.4."""
        records = [make_daily_record(date(2024, 1, 7), time(8, 0), time(17, 0))]
        shifts = assemble_shifts(records)
        shifts = assign_shifts(shifts)
        weeks = classify_weeks(shifts)
        shifts = resolve_thresholds(shifts, weeks, RestDay.SATURDAY, District.TEL_AVIV)

        assert shifts[0].threshold == Decimal("8.4")

    def test_threshold_6day_week(self):
        """6-day week threshold = 8.0 (except eve of rest = 7.0)."""
        records = [
            make_daily_record(date(2024, 1, 7 + i), time(8, 0), time(17, 0))
            for i in range(6)  # Sun-Fri
        ]
        shifts = assemble_shifts(records)
        shifts = assign_shifts(shifts)
        weeks = classify_weeks(shifts)
        shifts = resolve_thresholds(shifts, weeks, RestDay.SATURDAY, District.TEL_AVIV)

        # Sun-Thu have 8.0 threshold, Friday (eve of rest) has 7.0
        for shift in shifts:
            if shift.assigned_day.weekday() == 4:  # Friday
                assert shift.threshold == Decimal("7.0")
                assert "eve" in shift.threshold_reason
            else:
                assert shift.threshold == Decimal("8.0")

    def test_night_shift_threshold(self):
        """Night shift threshold = 7.0."""
        # Shift with >= 2 hours in 22:00-06:00
        record = make_daily_record(date(2024, 1, 7), time(20, 0), time(5, 0))
        shifts = assemble_shifts([record])
        shifts = assign_shifts(shifts)
        weeks = classify_weeks(shifts)
        shifts = resolve_thresholds(shifts, weeks, RestDay.SATURDAY, District.TEL_AVIV)

        assert shifts[0].threshold == Decimal("7.0")
        assert "night" in shifts[0].threshold_reason


# =============================================================================
# Stage 5: Daily OT Detection Tests
# =============================================================================

class TestStage5DailyOT:
    """Tests for daily OT detection."""

    def test_no_ot(self):
        """No OT when under threshold."""
        record = make_daily_record(date(2024, 1, 7), time(8, 0), time(16, 0))  # 8h
        shifts = assemble_shifts([record])
        shifts = assign_shifts(shifts)
        weeks = classify_weeks(shifts)
        shifts = resolve_thresholds(shifts, weeks, RestDay.SATURDAY, District.TEL_AVIV)
        shifts = detect_daily_ot(shifts)

        assert shifts[0].regular_hours == Decimal("8")
        assert shifts[0].ot_tier1_hours == Decimal("0")
        assert shifts[0].ot_tier2_hours == Decimal("0")

    def test_tier1_only(self):
        """OT within first 2 hours = Tier 1 only."""
        # 10h shift, 8.4 threshold -> 1.6h OT (all Tier 1)
        record = make_daily_record(date(2024, 1, 7), time(8, 0), time(18, 0))
        shifts = assemble_shifts([record])
        shifts = assign_shifts(shifts)
        weeks = classify_weeks(shifts)
        shifts = resolve_thresholds(shifts, weeks, RestDay.SATURDAY, District.TEL_AVIV)
        shifts = detect_daily_ot(shifts)

        assert shifts[0].regular_hours == Decimal("8.4")
        assert shifts[0].ot_tier1_hours == Decimal("1.6")
        assert shifts[0].ot_tier2_hours == Decimal("0")

    def test_tier1_and_tier2(self):
        """OT beyond 2 hours = Tier 2."""
        # 11h shift, 8.4 threshold -> 2.6h OT (2h Tier 1 + 0.6h Tier 2)
        record = make_daily_record(date(2024, 1, 7), time(7, 0), time(18, 0))
        shifts = assemble_shifts([record])
        shifts = assign_shifts(shifts)
        weeks = classify_weeks(shifts)
        shifts = resolve_thresholds(shifts, weeks, RestDay.SATURDAY, District.TEL_AVIV)
        shifts = detect_daily_ot(shifts)

        assert shifts[0].regular_hours == Decimal("8.4")
        assert shifts[0].ot_tier1_hours == Decimal("2")
        assert shifts[0].ot_tier2_hours == Decimal("0.6")


# =============================================================================
# Stage 6: Weekly OT Detection Tests
# =============================================================================

class TestStage6WeeklyOT:
    """Tests for weekly OT detection."""

    def test_no_weekly_ot(self):
        """No weekly OT when under 42."""
        # 5 shifts × 8h = 40h, no weekly OT
        records = [
            make_daily_record(date(2024, 1, 7 + i), time(8, 0), time(16, 0))
            for i in range(5)
        ]
        shifts = assemble_shifts(records)
        shifts = assign_shifts(shifts)
        weeks = classify_weeks(shifts)
        shifts = resolve_thresholds(shifts, weeks, RestDay.SATURDAY, District.TEL_AVIV)
        shifts = detect_daily_ot(shifts)
        shifts, weeks = detect_weekly_ot(shifts, weeks)

        assert weeks[0].weekly_ot_hours == Decimal("0")
        for shift in shifts:
            assert shift.weekly_ot_hours == Decimal("0")

    def test_weekly_ot_basic(self):
        """Weekly OT when over 42."""
        # 6 shifts × 8h = 48h gross, but Friday has threshold 7.0
        # So 5 shifts × 8h regular + 1 shift × 7h regular = 47h regular
        # Friday's extra hour goes to daily OT, not regular
        # Weekly OT = 47 - 42 = 5h
        records = [
            make_daily_record(date(2024, 1, 7 + i), time(8, 0), time(16, 0))
            for i in range(6)
        ]
        shifts = assemble_shifts(records)
        shifts = assign_shifts(shifts)
        weeks = classify_weeks(shifts)
        shifts = resolve_thresholds(shifts, weeks, RestDay.SATURDAY, District.TEL_AVIV)
        shifts = detect_daily_ot(shifts)
        shifts, weeks = detect_weekly_ot(shifts, weeks)

        # Friday contributes 7h regular + 1h daily OT
        # Other 5 days contribute 8h regular each = 40h
        # Total regular = 47h -> 5h weekly OT
        assert weeks[0].weekly_ot_hours == Decimal("5")


# =============================================================================
# Integration Tests (from skill)
# =============================================================================

class TestIntegration:
    """Integration test cases from skill documentation."""

    def test_case1_simple_week_no_ot(self):
        """Case 1: 5 shifts × 8h, week type 5 -> 40h regular, 0h OT."""
        records = [
            make_daily_record(date(2024, 1, 7 + i), time(8, 0), time(16, 0))
            for i in range(5)
        ]
        result = run_overtime_stages_1_to_7(
            records, RestDay.SATURDAY, District.TEL_AVIV
        )

        assert result.success
        total_regular = sum(s.regular_hours for s in result.shifts)
        total_ot = sum(s.ot_tier1_hours + s.ot_tier2_hours for s in result.shifts)

        assert total_regular == Decimal("40")
        assert total_ot == Decimal("0")

    def test_case2_daily_ot_only(self):
        """Case 2: 5 shifts × 10h, week type 5 -> daily OT only."""
        records = [
            make_daily_record(date(2024, 1, 7 + i), time(8, 0), time(18, 0))
            for i in range(5)
        ]
        result = run_overtime_stages_1_to_7(
            records, RestDay.SATURDAY, District.TEL_AVIV
        )

        assert result.success
        # 10h per shift, 8.4 threshold -> 1.6h OT per shift
        for shift in result.shifts:
            assert shift.regular_hours == Decimal("8.4")
            assert shift.ot_tier1_hours == Decimal("1.6")
            assert shift.ot_tier2_hours == Decimal("0")

    def test_case3_weekly_ot_only(self):
        """Case 3: 6 shifts × 8h, week type 6.

        Friday has threshold 7.0 (eve of rest), so:
        - 5 shifts × 8h regular = 40h
        - 1 Friday shift: 7h regular + 1h daily OT
        - Total regular = 47h -> weekly OT = 5h
        """
        records = [
            make_daily_record(date(2024, 1, 7 + i), time(8, 0), time(16, 0))
            for i in range(6)
        ]
        result = run_overtime_stages_1_to_7(
            records, RestDay.SATURDAY, District.TEL_AVIV
        )

        assert result.success
        assert result.weeks[0].weekly_ot_hours == Decimal("5")

    def test_case5_night_shift(self):
        """Case 5: Night shift 20:00-05:00 -> threshold 7.0."""
        record = make_daily_record(date(2024, 1, 7), time(20, 0), time(5, 0))
        result = run_overtime_stages_1_to_7(
            [record], RestDay.SATURDAY, District.TEL_AVIV
        )

        assert result.success
        assert result.shifts[0].threshold == Decimal("7.0")
        # 9h shift, 7h threshold -> 2h OT
        assert result.shifts[0].regular_hours == Decimal("7.0")
        assert result.shifts[0].ot_tier1_hours == Decimal("2")


# =============================================================================
# Edge Case Tests (from skill documentation)
# =============================================================================

class TestEdgeCases:
    """Edge case tests from skill documentation."""

    def test_shift_crossing_midnight_majority_first_day(self):
        """Edge Case 1: Shift crossing midnight, majority on first day."""
        # 20:00-02:00 = 4h on day 1, 2h on day 2 -> assigned to day 1
        record = make_daily_record(date(2024, 1, 7), time(20, 0), time(2, 0))
        shifts = assemble_shifts([record])
        shifts = assign_shifts(shifts)

        assert shifts[0].assigned_day == date(2024, 1, 7)
        assert shifts[0].net_hours == Decimal("6")

    def test_shift_crossing_midnight_majority_second_day(self):
        """Edge Case 1: Shift crossing midnight, majority on second day."""
        # 23:00-08:00 = 1h on day 1, 8h on day 2 -> assigned to day 2
        record = make_daily_record(date(2024, 1, 7), time(23, 0), time(8, 0))
        shifts = assemble_shifts([record])
        shifts = assign_shifts(shifts)

        assert shifts[0].assigned_day == date(2024, 1, 8)
        assert shifts[0].net_hours == Decimal("9")

    def test_shift_crossing_week_boundary_majority_first_week(self):
        """Edge Case 2: Shift crossing Saturday 24:00, majority in first week."""
        # Saturday 20:00 - Sunday 02:00 = 4h Sat, 2h Sun -> assigned to Sat (week 1)
        # Jan 13, 2024 is Saturday
        record = make_daily_record(date(2024, 1, 13), time(20, 0), time(2, 0))
        shifts = assemble_shifts([record])
        shifts = assign_shifts(shifts)

        # Majority on Saturday -> week containing Jan 13
        assert shifts[0].assigned_day == date(2024, 1, 13)
        assert "2024-W02" in shifts[0].assigned_week

    def test_shift_crossing_week_boundary_majority_second_week(self):
        """Edge Case 2: Shift crossing Saturday 24:00, majority in second week."""
        # Saturday 23:00 - Sunday 07:00 = 1h Sat, 7h Sun -> assigned to Sun (week 2)
        # Jan 13, 2024 is Saturday, Jan 14 is Sunday
        record = make_daily_record(date(2024, 1, 13), time(23, 0), time(7, 0))
        shifts = assemble_shifts([record])
        shifts = assign_shifts(shifts)

        # Majority on Sunday -> week containing Jan 14
        assert shifts[0].assigned_day == date(2024, 1, 14)
        assert "2024-W03" in shifts[0].assigned_week

    def test_shift_overlapping_rest_window_split(self):
        """Edge Case 3: Shift crossing INTO rest window - split pricing.

        Friday 14:00-22:00 (8h), rest window starts ~16:37 (Tel Aviv Jan 12)
        -> ~2.62h outside window, ~5.38h inside window
        """
        # Jan 12, 2024 is Friday. Candle lighting in Tel Aviv ~16:37
        record = make_daily_record(date(2024, 1, 12), time(14, 0), time(22, 0))
        result = run_overtime_stages_1_to_7(
            [record], RestDay.SATURDAY, District.TEL_AVIV
        )

        assert result.success
        shift = result.shifts[0]
        week = result.weeks[0]

        # Verify rest window was set
        assert week.rest_window_start is not None
        assert week.rest_window_end is not None

        # This is eve of rest, threshold = 7.0
        assert shift.threshold == Decimal("7.0")
        # 8h shift - 7h threshold = 1h OT tier 1
        assert shift.regular_hours == Decimal("7.0")
        assert shift.ot_tier1_hours == Decimal("1")

        # Verify hours are split between inside/outside rest window
        total_in_window = (
            shift.rest_window_regular_hours +
            shift.rest_window_ot_tier1_hours +
            shift.rest_window_ot_tier2_hours
        )
        total_outside = (
            shift.non_rest_regular_hours +
            shift.non_rest_ot_tier1_hours +
            shift.non_rest_ot_tier2_hours
        )

        # Both should be > 0 (shift overlaps window boundary)
        assert total_in_window > Decimal("0")
        assert total_outside > Decimal("0")
        # Sum should equal total shift hours
        assert total_in_window + total_outside == shift.net_hours

    def test_two_shifts_same_day(self):
        """Edge Case 7: Multiple shifts in one calendar day.

        Each shift is independent for daily OT, all count toward weekly total.
        """
        # Two shifts on Sunday: 08:00-12:00 (4h) and 14:00-20:00 (6h)
        record1 = DailyRecord(
            date=date(2024, 1, 7),
            effective_period_id="EP1",
            day_of_week=0,
            is_work_day=True,
            is_rest_day=False,
            shift_templates=[TimeRange(start_time=time(8, 0), end_time=time(12, 0))],
            break_templates=[],
        )
        record2 = DailyRecord(
            date=date(2024, 1, 7),
            effective_period_id="EP1",
            day_of_week=0,
            is_work_day=True,
            is_rest_day=False,
            shift_templates=[TimeRange(start_time=time(14, 0), end_time=time(20, 0))],
            break_templates=[],
        )

        result = run_overtime_stages_1_to_7(
            [record1, record2], RestDay.SATURDAY, District.TEL_AVIV
        )

        assert result.success
        assert len(result.shifts) == 2

        # Both shifts assigned to same day
        assert result.shifts[0].assigned_day == date(2024, 1, 7)
        assert result.shifts[1].assigned_day == date(2024, 1, 7)

        # Each shift is independent for daily OT
        # 4h shift: all regular (< 8.4 threshold)
        assert result.shifts[0].net_hours == Decimal("4")
        assert result.shifts[0].regular_hours == Decimal("4")
        assert result.shifts[0].ot_tier1_hours == Decimal("0")

        # 6h shift: all regular (< 8.4 threshold)
        assert result.shifts[1].net_hours == Decimal("6")
        assert result.shifts[1].regular_hours == Decimal("6")
        assert result.shifts[1].ot_tier1_hours == Decimal("0")

        # Week still counts them separately for classification
        # 1 distinct work day -> 5-day week
        assert result.weeks[0].week_type == WeekType.FIVE_DAY

    def test_eve_of_rest_threshold_case6(self):
        """Case 6: Eve of rest threshold = 7.0.

        Friday shift when Shabbat candle lighting is ~16:37 (Tel Aviv Jan 12)
        Eve of rest starts 24h before = Thursday ~16:37
        Friday shift starts 07:00 -> inside eve-of-rest window -> threshold 7.0
        """
        # Thursday shift starting after 16:37 should be eve of rest
        # But let's test Friday which is definitely eve of rest
        record = make_daily_record(date(2024, 1, 12), time(7, 0), time(16, 0))
        result = run_overtime_stages_1_to_7(
            [record], RestDay.SATURDAY, District.TEL_AVIV
        )

        assert result.success
        shift = result.shifts[0]

        # Friday is eve of rest
        assert shift.threshold == Decimal("7.0")
        assert "eve" in shift.threshold_reason.lower()

        # 9h shift, 7h threshold -> 2h OT
        assert shift.regular_hours == Decimal("7.0")
        assert shift.ot_tier1_hours == Decimal("2")
        assert shift.ot_tier2_hours == Decimal("0")

    def test_partial_week_employment_starts_midweek(self):
        """Edge Case 11: Partial week - employment starts mid-week.

        Weekly OT threshold (42) still applies. Fewer shifts = less chance of reaching it.
        """
        # Employment starts Thursday (Jan 11), works Thu-Fri
        records = [
            make_daily_record(date(2024, 1, 11), time(8, 0), time(18, 0)),  # Thu, 10h
            make_daily_record(date(2024, 1, 12), time(8, 0), time(18, 0)),  # Fri, 10h
        ]
        result = run_overtime_stages_1_to_7(
            records, RestDay.SATURDAY, District.TEL_AVIV
        )

        assert result.success
        assert len(result.shifts) == 2

        # 2 distinct work days -> 5-day week classification
        assert result.weeks[0].week_type == WeekType.FIVE_DAY
        assert result.weeks[0].distinct_work_days == 2

        # Thu: 10h, threshold 8.4 (5-day week) -> 8.4 regular, 1.6 tier1
        thu_shift = [s for s in result.shifts if s.assigned_day == date(2024, 1, 11)][0]
        assert thu_shift.regular_hours == Decimal("8.4")
        assert thu_shift.ot_tier1_hours == Decimal("1.6")

        # Fri: 10h, threshold 7.0 (eve of rest) -> 7 regular, 2 tier1, 1 tier2
        fri_shift = [s for s in result.shifts if s.assigned_day == date(2024, 1, 12)][0]
        assert fri_shift.regular_hours == Decimal("7.0")
        assert fri_shift.ot_tier1_hours == Decimal("2")
        assert fri_shift.ot_tier2_hours == Decimal("1")

        # Total regular = 8.4 + 7 = 15.4 < 42 -> no weekly OT
        assert result.weeks[0].weekly_ot_hours == Decimal("0")

    def test_partial_week_employment_ends_midweek(self):
        """Edge Case 11: Partial week - employment ends mid-week.

        Weekly OT threshold (42) still applies.
        """
        # Employment ends Wednesday (Jan 10), worked Sun-Wed
        records = [
            make_daily_record(date(2024, 1, 7 + i), time(7, 0), time(18, 0))  # 11h each
            for i in range(4)  # Sun-Wed
        ]
        result = run_overtime_stages_1_to_7(
            records, RestDay.SATURDAY, District.TEL_AVIV
        )

        assert result.success
        assert len(result.shifts) == 4

        # 4 distinct work days -> 5-day week
        assert result.weeks[0].week_type == WeekType.FIVE_DAY

        # Each shift: 11h, threshold 8.4 -> 8.4 regular, 2 tier1, 0.6 tier2
        for shift in result.shifts:
            assert shift.regular_hours == Decimal("8.4")
            assert shift.ot_tier1_hours == Decimal("2")
            assert shift.ot_tier2_hours == Decimal("0.6")

        # Total regular = 4 × 8.4 = 33.6 < 42 -> no weekly OT
        assert result.weeks[0].weekly_ot_hours == Decimal("0")

    def test_case8_weekly_ot_across_multiple_shifts(self):
        """Case 8: Weekly OT across multiple shifts.

        Week: 5 shifts of 9h + 1 shift of 4h (6-day week)
        Daily OT: first 5 shifts have 1h tier1 each (threshold 8 in week 6)
        Regular: 5×8 + 4 = 44h -> 2h weekly OT in last shift
        Last shift (4h): 2h regular (reaching 42 total) + 2h weekly OT tier1
        """
        # 5 shifts × 9h + 1 shift × 4h
        records = [
            make_daily_record(date(2024, 1, 7 + i), time(8, 0), time(17, 0))  # 9h
            for i in range(5)  # Sun-Thu
        ]
        # Friday shift is 4h
        records.append(make_daily_record(date(2024, 1, 12), time(8, 0), time(12, 0)))  # 4h

        result = run_overtime_stages_1_to_7(
            records, RestDay.SATURDAY, District.TEL_AVIV
        )

        assert result.success
        assert len(result.shifts) == 6

        # 6-day week
        assert result.weeks[0].week_type == WeekType.SIX_DAY

        # First 5 shifts: 9h each, threshold 8.0 -> 8h regular, 1h tier1
        for i, shift in enumerate(result.shifts[:5]):
            assert shift.net_hours == Decimal("9")
            assert shift.threshold == Decimal("8.0")
            assert shift.regular_hours == Decimal("8.0")
            assert shift.ot_tier1_hours == Decimal("1")
            assert shift.ot_tier2_hours == Decimal("0")

        # Friday shift: 4h, threshold 7.0 (eve of rest)
        friday_shift = result.shifts[5]
        assert friday_shift.net_hours == Decimal("4")
        assert friday_shift.threshold == Decimal("7.0")

        # Weekly regular before Friday: 5 × 8 = 40h
        # Friday adds 4h regular -> total 44h -> weekly OT = 2h
        assert result.weeks[0].weekly_ot_hours == Decimal("2")

        # Friday shift breakdown:
        # - First 2h go to regular (reaching 42 total)
        # - Remaining 2h become weekly OT (which goes to tier1 since < 2h)
        # So: 2h regular, 2h OT tier1
        assert friday_shift.regular_hours == Decimal("2")
        assert friday_shift.ot_tier1_hours == Decimal("2")
        assert friday_shift.ot_tier2_hours == Decimal("0")

    def test_eve_of_rest_and_night_shift_combined(self):
        """Edge Case 8: Eve of rest AND night shift -> threshold still 7.0.

        No stacking - both reduce to 7.0, combined is still 7.0.
        """
        # Friday night shift: 20:00-05:00 (9h)
        # Eve of rest (Friday) + Night shift (>=2h in 22:00-06:00)
        record = make_daily_record(date(2024, 1, 12), time(20, 0), time(5, 0))
        result = run_overtime_stages_1_to_7(
            [record], RestDay.SATURDAY, District.TEL_AVIV
        )

        assert result.success
        shift = result.shifts[0]

        # Both conditions met, but threshold is still 7.0
        assert shift.threshold == Decimal("7.0")
        assert "eve" in shift.threshold_reason.lower() or "night" in shift.threshold_reason.lower()

        # 9h shift, 7h threshold -> 2h OT tier1
        assert shift.regular_hours == Decimal("7.0")
        assert shift.ot_tier1_hours == Decimal("2")
        assert shift.ot_tier2_hours == Decimal("0")
