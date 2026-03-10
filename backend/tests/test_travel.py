"""Tests for travel allowance (דמי נסיעות) module.

See docs/skills/travel/SKILL.md for test cases.

Updated for new period-based LodgingInput structure.
Formula: travel_days = max(2 * visits, work_days + visits - nights)
Floor is 2 × visits because every visit has departure + return.
"""

import pytest
from datetime import date
from decimal import Decimal

from app.modules.travel import compute_travel, compute_weekly_travel_days, compute_block_travel_days, get_work_days_in_week
from app.ssot import Week, Shift, LodgingInput, LodgingPeriod, VisitGroup


def make_week(
    week_id: str,
    start_date: date,
    end_date: date,
) -> Week:
    """Create a Week object for testing."""
    return Week(
        id=week_id,
        start_date=start_date,
        end_date=end_date,
    )


def make_shift(
    shift_id: str,
    assigned_week: str,
    assigned_day: date,
    effective_period_id: str = "ep1",
) -> Shift:
    """Create a Shift object for testing."""
    return Shift(
        id=shift_id,
        date=assigned_day,  # Required positional argument
        assigned_week=assigned_week,
        assigned_day=assigned_day,
        effective_period_id=effective_period_id,
    )


def make_lodging_period(
    period_id: str,
    start: date,
    end: date,
    pattern_type: str = "weekly",
    total_nights: int = 4,
    total_visits: int = 1,
    visit_groups: list[VisitGroup] | None = None,
    cycle_weeks: int = 1,
) -> LodgingPeriod:
    """Create a LodgingPeriod with visit groups for testing.

    Args:
        total_nights: Total nights per unit (week or month)
        total_visits: Total visits per unit (week or month)
        visit_groups: Explicit visit groups (overrides total_nights/total_visits)
        cycle_weeks: Number of consecutive work weeks per cycle (for weekly pattern)

    Creates visit groups to match the total_nights and total_visits.
    """
    if visit_groups is None and pattern_type != "none":
        # Create visit groups to match totals
        if total_visits == 0:
            visit_groups = []
        elif total_nights % total_visits == 0:
            # Even division - single group
            nights_per = total_nights // total_visits
            visit_groups = [VisitGroup(id="VG1", nights_per_visit=nights_per, count=total_visits)]
        else:
            # Uneven division - create multiple groups to match totals
            # e.g., total_nights=3, total_visits=2 → [{1, 1}, {2, 1}]
            base_nights = total_nights // total_visits
            remainder = total_nights % total_visits
            visit_groups = []
            for i in range(total_visits):
                nights = base_nights + (1 if i < remainder else 0)
                visit_groups.append(VisitGroup(id=f"VG{i+1}", nights_per_visit=nights, count=1))
    elif visit_groups is None:
        visit_groups = []

    return LodgingPeriod(
        id=period_id,
        start=start,
        end=end,
        pattern_type=pattern_type,
        cycle_weeks=cycle_weeks,
        visit_groups=visit_groups,
    )


def mock_travel_rate(industry: str, distance_km: Decimal | None, target_date: date) -> Decimal:
    """Mock travel rate lookup for testing."""
    if industry == "construction":
        if distance_km is not None and distance_km >= 40:
            return Decimal("39.60")
        else:
            return Decimal("26.40")
    else:
        return Decimal("22.60")


class TestComputeWeeklyTravelDays:
    """Tests for compute_weekly_travel_days helper function."""

    def test_no_lodging(self):
        """No lodging: all work days are travel days."""
        assert compute_weekly_travel_days(5, None) == 5
        assert compute_weekly_travel_days(3, None) == 3
        assert compute_weekly_travel_days(0, None) == 0

    def test_pattern_none(self):
        """Pattern type 'none': all work days are travel days."""
        period = make_lodging_period("LP1", date(2024, 1, 1), date(2024, 12, 31), "none", 0, 0)
        assert compute_weekly_travel_days(5, period) == 5
        assert compute_weekly_travel_days(3, period) == 3

    def test_weekly_lodging_standard(self):
        """Weekly lodging, 4 nights, 1 visit: travel_days = max(2, work_days + 1 - 4)."""
        # 4 nights/week, 1 visit/week. Floor is 2 × 1 = 2
        period = make_lodging_period("LP1", date(2024, 1, 1), date(2024, 12, 31), "weekly", 4, 1)
        # 5 work days: max(2, 5+1-4) = max(2, 2) = 2
        assert compute_weekly_travel_days(5, period) == 2
        # 3 work days: max(2, 3+1-4) = max(2, 0) = 2 (floor kicks in)
        assert compute_weekly_travel_days(3, period) == 2
        # 6 work days: max(2, 6+1-4) = max(2, 3) = 3
        assert compute_weekly_travel_days(6, period) == 3

    def test_weekly_lodging_custom_pattern(self):
        """Weekly lodging with custom nights/visits."""
        # 3 nights/week, 2 visits/week
        period = make_lodging_period("LP1", date(2024, 1, 1), date(2024, 12, 31), "weekly", 3, 2)
        # 5 work days: 5 + 2 - 3 = 4
        assert compute_weekly_travel_days(5, period) == 4

    def test_weekly_lodging_no_work_days(self):
        """Weekly lodging with 0 work days: 0 travel days."""
        period = make_lodging_period("LP1", date(2024, 1, 1), date(2024, 12, 31), "weekly", 4, 1)
        assert compute_weekly_travel_days(0, period) == 0

    def test_floor_is_2_times_visits(self):
        """Travel days floor is 2 × visits (every visit has departure + return).

        NOTE: work_days=1 is a special case (BUG FIX) — returns 1, not floor.
        For work_days >= 2, the floor of 2 × visits applies.
        """
        period = make_lodging_period("LP1", date(2024, 1, 1), date(2024, 12, 31), "weekly", 4, 1)
        # BUG FIX: work_days=1 → 1 (single day = departure OR return only)
        assert compute_weekly_travel_days(1, period) == 1
        assert compute_weekly_travel_days(2, period) == 2  # max(2, 2+1-4) = max(2, -1) = 2
        assert compute_weekly_travel_days(3, period) == 2  # max(2, 3+1-4) = max(2, 0) = 2


class TestGetWorkDaysInWeek:
    """Tests for get_work_days_in_week helper function."""

    def test_counts_distinct_days(self):
        """Should count distinct calendar days, not shifts."""
        week = make_week("w1", date(2024, 1, 1), date(2024, 1, 7))
        shifts = [
            make_shift("s1", "w1", date(2024, 1, 1)),
            make_shift("s2", "w1", date(2024, 1, 1)),  # Same day
            make_shift("s3", "w1", date(2024, 1, 2)),
            make_shift("s4", "w1", date(2024, 1, 3)),
        ]
        assert get_work_days_in_week(week, shifts) == 3  # Jan 1, 2, 3

    def test_ignores_other_weeks(self):
        """Should only count shifts in the specified week."""
        week1 = make_week("w1", date(2024, 1, 1), date(2024, 1, 7))
        shifts = [
            make_shift("s1", "w1", date(2024, 1, 1)),
            make_shift("s2", "w2", date(2024, 1, 8)),  # Different week
        ]
        assert get_work_days_in_week(week1, shifts) == 1


class TestCase1GeneralWorkerNoLodging:
    """Case 1 — General worker, no lodging, 3 months.

    Input:
        industry: "general"
        employment: 2024-01-01 – 2024-03-31
        work pattern: 5 days/week (Mon–Fri)
        lodging: none
        daily_rate: 22.6 ₪

    Expected:
        ~13 work weeks × 5 work_days × 22.6 = ~1,469 ₪
        travel_days per week = 5
        grand_total_travel_days ≈ 65
        grand_total_value ≈ 65 × 22.6 = 1,469 ₪
    """

    def test_general_worker_no_lodging_3_months(self):
        from datetime import timedelta

        # Create 13 weeks of work (Jan 1 - Mar 31, 2024)
        weeks = []
        shifts = []
        shift_count = 0

        # Generate weeks starting from first Monday of 2024 (Jan 1 is Monday)
        week_start = date(2024, 1, 1)
        for week_num in range(13):
            week_id = f"w{week_num + 1}"
            week_end = week_start + timedelta(days=6)

            weeks.append(make_week(week_id, week_start, week_end))

            # Add 5 shifts (Mon-Fri) for each week
            for day_offset in range(5):
                shift_date = week_start + timedelta(days=day_offset)
                shift_count += 1
                shifts.append(make_shift(f"s{shift_count}", week_id, shift_date))

            # Move to next week
            week_start = week_end + timedelta(days=1)

        result = compute_travel(
            industry="general",
            travel_distance_km=None,
            lodging_input=None,
            weeks=weeks,
            shifts=shifts,
            get_travel_rate=mock_travel_rate,
            right_enabled=True,
        )

        assert result.industry == "general"
        assert result.daily_rate == Decimal("22.60")
        assert result.has_lodging is False

        # Each week should have 5 travel days
        for detail in result.weekly_detail:
            assert detail.travel_days == detail.work_days

        # Total should be approximately 65 days × 22.6 = 1,469
        assert result.grand_total_travel_days == 65
        assert result.grand_total_value == Decimal("65") * Decimal("22.60")


class TestCase2ConstructionUnder40km:
    """Case 2 — Construction, <40km, no lodging.

    Input:
        industry: "construction"
        travel_distance_km: 15
        lodging: none
        daily_rate: 26.4 ₪
        employment: 2024-01-01 – 2024-01-31
        work pattern: 5 days/week

    Expected:
        ~4 work weeks × 5 work_days × 26.4 = ~528 ₪
    """

    def test_construction_under_40km_no_lodging(self):
        weeks = []
        shifts = []
        shift_count = 0

        # 4 weeks in January 2024
        week_start = date(2024, 1, 1)
        for week_num in range(4):
            week_id = f"w{week_num + 1}"
            week_end = date(2024, 1, week_start.day + 6)
            weeks.append(make_week(week_id, week_start, week_end))

            # 5 shifts per week
            for day_offset in range(5):
                shift_count += 1
                shift_date = date(2024, 1, week_start.day + day_offset)
                shifts.append(make_shift(f"s{shift_count}", week_id, shift_date))

            week_start = date(2024, 1, week_start.day + 7)

        result = compute_travel(
            industry="construction",
            travel_distance_km=Decimal("15"),
            lodging_input=None,
            weeks=weeks,
            shifts=shifts,
            get_travel_rate=mock_travel_rate,
            right_enabled=True,
        )

        assert result.industry == "construction"
        assert result.distance_km == Decimal("15")
        assert result.distance_tier == "standard"
        assert result.daily_rate == Decimal("26.40")
        assert result.has_lodging is False

        # 4 weeks × 5 days × 26.4 = 528
        assert result.grand_total_travel_days == 20
        assert result.grand_total_value == Decimal("528.00")


class TestCase3ConstructionOver40km:
    """Case 3 — Construction, ≥40km, no lodging.

    Input:
        industry: "construction"
        travel_distance_km: 60
        lodging: none
        daily_rate: 39.6 ₪
        employment: 2024-01-01 – 2024-01-31
        work pattern: 5 days/week

    Expected:
        ~4 work weeks × 5 × 39.6 = ~792 ₪
    """

    def test_construction_over_40km_no_lodging(self):
        weeks = []
        shifts = []
        shift_count = 0

        # 4 weeks in January 2024
        week_start = date(2024, 1, 1)
        for week_num in range(4):
            week_id = f"w{week_num + 1}"
            week_end = date(2024, 1, week_start.day + 6)
            weeks.append(make_week(week_id, week_start, week_end))

            for day_offset in range(5):
                shift_count += 1
                shift_date = date(2024, 1, week_start.day + day_offset)
                shifts.append(make_shift(f"s{shift_count}", week_id, shift_date))

            week_start = date(2024, 1, week_start.day + 7)

        result = compute_travel(
            industry="construction",
            travel_distance_km=Decimal("60"),
            lodging_input=None,
            weeks=weeks,
            shifts=shifts,
            get_travel_rate=mock_travel_rate,
            right_enabled=True,
        )

        assert result.industry == "construction"
        assert result.distance_km == Decimal("60")
        assert result.distance_tier == "far"
        assert result.daily_rate == Decimal("39.60")

        # 4 weeks × 5 days × 39.6 = 792
        assert result.grand_total_travel_days == 20
        assert result.grand_total_value == Decimal("792.00")


class TestCase4ConstructionWeeklyLodging:
    """Case 4 — Construction, weekly lodging (most common case).

    Input:
        industry: "construction"
        travel_distance_km: 30
        lodging: weekly pattern, 4 nights/week, 1 visit/week
        daily_rate: 26.4 ₪
        employment: 2024-01-01 – 2024-03-31
        work pattern: 5 days/week (Mon–Fri)

    Using new formula: travel_days = work_days + visits - nights
    Per week: 5 + 1 - 4 = 2 travel days

    Expected:
        ~13 weeks × 2 travel_days = 26
        grand_total_value = 26 × 26.4 = 686.4 ₪
    """

    def test_construction_weekly_lodging(self):
        from datetime import timedelta

        weeks = []
        shifts = []
        shift_count = 0

        # 13 weeks (Jan-Mar 2024)
        week_start = date(2024, 1, 1)
        for week_num in range(13):
            week_id = f"w{week_num + 1}"
            week_end = week_start + timedelta(days=6)

            weeks.append(make_week(week_id, week_start, week_end))

            # 5 shifts per week
            for day_offset in range(5):
                shift_count += 1
                shift_date = week_start + timedelta(days=day_offset)
                shifts.append(make_shift(f"s{shift_count}", week_id, shift_date))

            # Next week start
            week_start = week_end + timedelta(days=1)

        lodging_input = LodgingInput(
            periods=[
                make_lodging_period(
                    "LP1",
                    date(2024, 1, 1),
                    date(2024, 3, 31),
                    pattern_type="weekly",
                    total_nights=4,
                    total_visits=1,
                )
            ]
        )

        result = compute_travel(
            industry="construction",
            travel_distance_km=Decimal("30"),
            lodging_input=lodging_input,
            weeks=weeks,
            shifts=shifts,
            get_travel_rate=mock_travel_rate,
            right_enabled=True,
        )

        assert result.industry == "construction"
        assert result.distance_tier == "standard"
        assert result.daily_rate == Decimal("26.40")
        assert result.has_lodging is True
        assert result.lodging_periods_count == 1

        # Each week should have 2 travel days (5 + 1 - 4 = 2)
        for detail in result.weekly_detail:
            assert detail.week_pattern == "weekly_lodging"
            assert detail.travel_days == 2

        # 13 weeks × 2 travel days = 26
        assert result.grand_total_travel_days == 26
        # 26 × 26.4 = 686.4
        assert result.grand_total_value == Decimal("686.40")


class TestCase5ConstructionMultiplePeriods:
    """Case 5 — Construction, multiple lodging periods.

    Tests that different lodging periods apply to different date ranges.

    Input:
        lodging: Two periods
            Period 1: Jan 2024, weekly, 4 nights/week, 1 visit
            Period 2: Feb 2024, weekly, 3 nights/week, 2 visits
        work_days/week: 5
        daily_rate: 26.4

    Expected:
        Jan weeks (4): 5 + 1 - 4 = 2 travel_days each = 8 travel days
        Feb weeks (4): 5 + 2 - 3 = 4 travel_days each = 16 travel days
        Total: 24 travel_days
    """

    def test_construction_multiple_periods(self):
        from datetime import timedelta

        weeks = []
        shifts = []
        shift_count = 0

        # 4 weeks in January
        week_start = date(2024, 1, 1)
        for week_num in range(4):
            week_id = f"w{week_num + 1}"
            week_end = week_start + timedelta(days=6)
            weeks.append(make_week(week_id, week_start, week_end))

            for day_offset in range(5):
                shift_count += 1
                shift_date = week_start + timedelta(days=day_offset)
                shifts.append(make_shift(f"s{shift_count}", week_id, shift_date))

            week_start = week_start + timedelta(days=7)

        # 4 weeks in February
        week_start = date(2024, 2, 5)  # First Monday of Feb 2024
        for week_num in range(4):
            week_id = f"w{week_num + 5}"
            week_end = week_start + timedelta(days=6)
            weeks.append(make_week(week_id, week_start, week_end))

            for day_offset in range(5):
                shift_count += 1
                shift_date = week_start + timedelta(days=day_offset)
                shifts.append(make_shift(f"s{shift_count}", week_id, shift_date))

            week_start = week_start + timedelta(days=7)

        lodging_input = LodgingInput(
            periods=[
                make_lodging_period(
                    "LP1",
                    date(2024, 1, 1),
                    date(2024, 1, 31),
                    pattern_type="weekly",
                    total_nights=4,
                    total_visits=1,
                ),
                make_lodging_period(
                    "LP2",
                    date(2024, 2, 1),
                    date(2024, 2, 29),
                    pattern_type="weekly",
                    total_nights=3,
                    total_visits=2,
                ),
            ]
        )

        result = compute_travel(
            industry="construction",
            travel_distance_km=Decimal("25"),
            lodging_input=lodging_input,
            weeks=weeks,
            shifts=shifts,
            get_travel_rate=mock_travel_rate,
            right_enabled=True,
        )

        assert result.has_lodging is True
        assert result.lodging_periods_count == 2

        # Check January weeks (first 4): 5 + 1 - 4 = 2
        for detail in result.weekly_detail[:4]:
            assert detail.travel_days == 2

        # Check February weeks (next 4): 5 + 2 - 3 = 4
        for detail in result.weekly_detail[4:]:
            assert detail.travel_days == 4

        # Total: 4×2 + 4×4 = 8 + 16 = 24 travel days
        assert result.grand_total_travel_days == 24
        # 24 × 26.4 = 633.6
        assert result.grand_total_value == Decimal("633.60")


class TestCase6PartialWeekEmploymentStart:
    """Case 6 — Partial week, employment starts mid-week (lodging mode).

    Input:
        industry: "construction", travel_distance_km: 20
        lodging: weekly, 4 nights, 1 visit
        employment start: 2024-01-03 (Wednesday)
        first week: work_days=3 (Wed, Thu, Fri)

    Expected:
        travel_days = max(2*1, 3+1-4) = max(2, 0) = 2
        Floor is 2 × visits because every visit has departure + return.
    """

    def test_partial_week_employment_start_lodging(self):
        # Single week starting mid-week
        week = make_week("w1", date(2024, 1, 1), date(2024, 1, 7))
        shifts = [
            make_shift("s1", "w1", date(2024, 1, 3)),  # Wednesday
            make_shift("s2", "w1", date(2024, 1, 4)),  # Thursday
            make_shift("s3", "w1", date(2024, 1, 5)),  # Friday
        ]

        lodging_input = LodgingInput(
            periods=[
                make_lodging_period(
                    "LP1",
                    date(2024, 1, 1),
                    date(2024, 12, 31),
                    pattern_type="weekly",
                    total_nights=4,
                    total_visits=1,
                )
            ]
        )

        result = compute_travel(
            industry="construction",
            travel_distance_km=Decimal("20"),
            lodging_input=lodging_input,
            weeks=[week],
            shifts=shifts,
            get_travel_rate=mock_travel_rate,
            right_enabled=True,
        )

        assert len(result.weekly_detail) == 1
        assert result.weekly_detail[0].work_days == 3
        assert result.weekly_detail[0].week_pattern == "weekly_lodging"
        # max(2*1, 3+1-4) = max(2, 0) = 2 (floor is 2 × visits)
        assert result.weekly_detail[0].travel_days == 2


class TestCase7SingleDayLodgingWeek:
    """Case 7 — Single work day in lodging week.

    Input:
        lodging: weekly, 4 nights, 1 visit
        work_days = 1 (holiday week, only 1 day worked)

    Expected (after BUG FIX):
        travel_days = 1
        Single work day = departure only OR return only, not both.
        This is a fix to the old behavior that returned 2.
    """

    def test_single_day_lodging_week(self):
        week = make_week("w1", date(2024, 1, 1), date(2024, 1, 7))
        shifts = [
            make_shift("s1", "w1", date(2024, 1, 1)),  # Only one day worked
        ]

        lodging_input = LodgingInput(
            periods=[
                make_lodging_period(
                    "LP1",
                    date(2024, 1, 1),
                    date(2024, 12, 31),
                    pattern_type="weekly",
                    total_nights=4,
                    total_visits=1,
                )
            ]
        )

        result = compute_travel(
            industry="construction",
            travel_distance_km=Decimal("25"),
            lodging_input=lodging_input,
            weeks=[week],
            shifts=shifts,
            get_travel_rate=mock_travel_rate,
            right_enabled=True,
        )

        assert len(result.weekly_detail) == 1
        assert result.weekly_detail[0].work_days == 1
        # BUG FIX: work_days=1 → 1 (not 2)
        assert result.weekly_detail[0].travel_days == 1


class TestCase8PeriodGap:
    """Case 8 — Lodging period gap.

    Tests that weeks outside lodging periods get no_lodging treatment.

    Input:
        Lodging period 1: Jan 1-14
        Lodging period 2: Jan 22-31
        Gap: Jan 15-21

    Expected:
        Weeks 1-2: weekly_lodging pattern
        Week 3: no_lodging (in gap)
        Week 4: weekly_lodging pattern
    """

    def test_period_gap(self):
        weeks = []
        shifts = []
        shift_count = 0

        # 4 weeks in January
        for week_num in range(4):
            week_id = f"w{week_num + 1}"
            week_start = date(2024, 1, 1 + week_num * 7)
            week_end = date(2024, 1, 7 + week_num * 7)
            weeks.append(make_week(week_id, week_start, week_end))

            for day_offset in range(5):
                shift_count += 1
                shift_date = date(2024, 1, week_start.day + day_offset)
                shifts.append(make_shift(f"s{shift_count}", week_id, shift_date))

        lodging_input = LodgingInput(
            periods=[
                make_lodging_period(
                    "LP1",
                    date(2024, 1, 1),
                    date(2024, 1, 14),  # Weeks 1-2
                    pattern_type="weekly",
                    total_nights=4,
                    total_visits=1,
                ),
                make_lodging_period(
                    "LP2",
                    date(2024, 1, 22),
                    date(2024, 1, 31),  # Week 4 only
                    pattern_type="weekly",
                    total_nights=4,
                    total_visits=1,
                ),
            ]
        )

        result = compute_travel(
            industry="construction",
            travel_distance_km=Decimal("25"),
            lodging_input=lodging_input,
            weeks=weeks,
            shifts=shifts,
            get_travel_rate=mock_travel_rate,
            right_enabled=True,
        )

        assert len(result.weekly_detail) == 4

        # Weeks 1-2: weekly_lodging, 2 travel days each
        assert result.weekly_detail[0].week_pattern == "weekly_lodging"
        assert result.weekly_detail[0].travel_days == 2
        assert result.weekly_detail[1].week_pattern == "weekly_lodging"
        assert result.weekly_detail[1].travel_days == 2

        # Week 3: no_lodging (gap), 5 travel days
        assert result.weekly_detail[2].week_pattern == "no_lodging"
        assert result.weekly_detail[2].travel_days == 5

        # Week 4: weekly_lodging, 2 travel days
        assert result.weekly_detail[3].week_pattern == "weekly_lodging"
        assert result.weekly_detail[3].travel_days == 2

        # Total: 2 + 2 + 5 + 2 = 11 travel days
        assert result.grand_total_travel_days == 11


class TestRightToggleDisabled:
    """Test that disabled right toggle returns empty result."""

    def test_disabled_toggle_returns_empty(self):
        week = make_week("w1", date(2024, 1, 1), date(2024, 1, 7))
        shifts = [make_shift("s1", "w1", date(2024, 1, 1))]

        result = compute_travel(
            industry="general",
            travel_distance_km=None,
            lodging_input=None,
            weeks=[week],
            shifts=shifts,
            get_travel_rate=mock_travel_rate,
            right_enabled=False,  # Disabled
        )

        assert result.grand_total_travel_days == 0
        assert result.grand_total_value == Decimal("0")
        assert len(result.weekly_detail) == 0


class TestMonthlyBreakdown:
    """Tests for monthly aggregation."""

    def test_monthly_breakdown_groups_by_month(self):
        """Weeks should be grouped by their start_date month."""
        # Create 2 weeks: one in January, one in February
        weeks = [
            make_week("w1", date(2024, 1, 22), date(2024, 1, 28)),
            make_week("w2", date(2024, 2, 5), date(2024, 2, 11)),
        ]
        shifts = [
            make_shift("s1", "w1", date(2024, 1, 22)),
            make_shift("s2", "w1", date(2024, 1, 23)),
            make_shift("s3", "w2", date(2024, 2, 5)),
            make_shift("s4", "w2", date(2024, 2, 6)),
        ]

        result = compute_travel(
            industry="general",
            travel_distance_km=None,
            lodging_input=None,
            weeks=weeks,
            shifts=shifts,
            get_travel_rate=mock_travel_rate,
            right_enabled=True,
        )

        assert len(result.monthly_breakdown) == 2
        assert result.monthly_breakdown[0].month == (2024, 1)
        assert result.monthly_breakdown[0].travel_days == 2
        assert result.monthly_breakdown[0].claim_amount == Decimal("45.20")  # 2 × 22.6

        assert result.monthly_breakdown[1].month == (2024, 2)
        assert result.monthly_breakdown[1].travel_days == 2
        assert result.monthly_breakdown[1].claim_amount == Decimal("45.20")


class TestDistanceThreshold:
    """Tests for construction distance threshold."""

    def test_distance_exactly_40km_uses_far_tier(self):
        """Distance exactly 40km should use far tier (39.6)."""
        week = make_week("w1", date(2024, 1, 1), date(2024, 1, 7))
        shifts = [make_shift("s1", "w1", date(2024, 1, 1))]

        result = compute_travel(
            industry="construction",
            travel_distance_km=Decimal("40"),  # Exactly 40
            lodging_input=None,
            weeks=[week],
            shifts=shifts,
            get_travel_rate=mock_travel_rate,
            right_enabled=True,
        )

        assert result.distance_tier == "far"
        assert result.daily_rate == Decimal("39.60")

    def test_distance_39km_uses_standard_tier(self):
        """Distance 39km should use standard tier (26.4)."""
        week = make_week("w1", date(2024, 1, 1), date(2024, 1, 7))
        shifts = [make_shift("s1", "w1", date(2024, 1, 1))]

        result = compute_travel(
            industry="construction",
            travel_distance_km=Decimal("39"),
            lodging_input=None,
            weeks=[week],
            shifts=shifts,
            get_travel_rate=mock_travel_rate,
            right_enabled=True,
        )

        assert result.distance_tier == "standard"
        assert result.daily_rate == Decimal("26.40")


class TestNonConstructionIgnoresLodging:
    """Tests that non-construction industries ignore lodging input."""

    def test_general_ignores_lodging_input(self):
        """General industry should ignore lodging_input even if provided."""
        week = make_week("w1", date(2024, 1, 1), date(2024, 1, 7))
        shifts = [
            make_shift("s1", "w1", date(2024, 1, 1)),
            make_shift("s2", "w1", date(2024, 1, 2)),
            make_shift("s3", "w1", date(2024, 1, 3)),
            make_shift("s4", "w1", date(2024, 1, 4)),
            make_shift("s5", "w1", date(2024, 1, 5)),
        ]

        # Lodging input is provided but should be ignored for general
        lodging_input = LodgingInput(
            periods=[
                make_lodging_period(
                    "LP1",
                    date(2024, 1, 1),
                    date(2024, 12, 31),
                    pattern_type="weekly",
                    total_nights=4,
                    total_visits=1,
                )
            ]
        )

        result = compute_travel(
            industry="general",  # Not construction
            travel_distance_km=None,
            lodging_input=lodging_input,  # Should be ignored
            weeks=[week],
            shifts=shifts,
            get_travel_rate=mock_travel_rate,
            right_enabled=True,
        )

        # Should NOT apply lodging logic - all 5 days are travel days
        assert result.has_lodging is False
        assert result.weekly_detail[0].travel_days == 5  # NOT 2
        assert result.weekly_detail[0].week_pattern == "no_lodging"


class TestMonthlyLodgingCalendarDayCounting:
    """Tests for monthly lodging pattern calendar-based work day counting.

    Critical fix: Monthly work days must be counted by calendar date, not week attribution.
    A day belongs to month M if its calendar date falls within M, regardless of which week
    it belongs to in the OT pipeline.

    Anti-pattern #9 from SKILL: DO NOT count monthly work_days by week attribution
    (week.start_date). This causes months with 5 Mondays to get 25 work days instead
    of actual ~22.
    """

    def test_january_2023_five_mondays_calendar_counting(self):
        """January 2023 has 5 Mondays - verify calendar-based counting.

        January 2023:
        - Jan 2 (Mon) starts week 1
        - Jan 9 (Mon) starts week 2
        - Jan 16 (Mon) starts week 3
        - Jan 23 (Mon) starts week 4
        - Jan 30 (Mon) starts week 5 (continues into Feb)

        Week 5 (Jan 30 - Feb 5) has:
        - Jan 30, Jan 31: 2 days in January
        - Feb 1-3: 3 days in February

        By week attribution (WRONG): 5 weeks × 5 days = 25 work days in January
        By calendar date (CORRECT): 22 work days in January (4 full weeks + 2 days)

        With monthly lodging (20 nights, 7 visits):
        Floor is 2 × 7 = 14 travel days
        Formula: max(14, work_days + 7 - 20)
        January (22 work days): max(14, 22+7-20) = max(14, 9) = 14
        February (3 work days): max(14, 3+7-20) = max(14, -10) = 14
        """
        from datetime import timedelta

        weeks = []
        shifts = []
        shift_count = 0

        # Create 5 weeks starting from Jan 2, 2023 (first Monday)
        week_starts = [
            date(2023, 1, 2),   # Week 1
            date(2023, 1, 9),   # Week 2
            date(2023, 1, 16),  # Week 3
            date(2023, 1, 23),  # Week 4
            date(2023, 1, 30),  # Week 5 (spans Jan-Feb)
        ]

        for week_num, week_start in enumerate(week_starts):
            week_id = f"w{week_num + 1}"
            week_end = week_start + timedelta(days=6)
            weeks.append(make_week(week_id, week_start, week_end))

            # Add 5 shifts (Mon-Fri) for each week
            for day_offset in range(5):
                shift_date = week_start + timedelta(days=day_offset)
                shift_count += 1
                shifts.append(make_shift(f"s{shift_count}", week_id, shift_date))

        # Monthly lodging: 20 nights/month, 7 visits/month
        # (Example from skill: [{14 nights, 1 visit}, {1 night, 6 visits}])
        lodging_input = LodgingInput(
            periods=[
                make_lodging_period(
                    "LP1",
                    date(2023, 1, 1),
                    date(2023, 2, 28),
                    pattern_type="monthly",
                    total_nights=20,
                    total_visits=7,
                )
            ]
        )

        result = compute_travel(
            industry="construction",
            travel_distance_km=Decimal("25"),
            lodging_input=lodging_input,
            weeks=weeks,
            shifts=shifts,
            get_travel_rate=mock_travel_rate,
            right_enabled=True,
        )

        # Find January's breakdown
        jan_breakdown = next(
            (b for b in result.monthly_breakdown if b.month == (2023, 1)),
            None
        )
        feb_breakdown = next(
            (b for b in result.monthly_breakdown if b.month == (2023, 2)),
            None
        )

        # January has 22 work days by calendar (not 25 by week attribution)
        # travel_days = max(2*7, 22+7-20) = max(14, 9) = 14
        assert jan_breakdown is not None
        assert jan_breakdown.travel_days == 14  # Floor is 2 × 7 visits

        # February has 3 work days (from week 5: Feb 1, 2, 3)
        # travel_days = max(2*7, 3+7-20) = max(14, -10) = 14
        assert feb_breakdown is not None
        assert feb_breakdown.travel_days == 14  # Floor is 2 × 7 visits


class TestEmptyWeeks:
    """Tests for handling weeks with no work."""

    def test_skips_weeks_with_no_shifts(self):
        """Weeks with no shifts should be skipped."""
        weeks = [
            make_week("w1", date(2024, 1, 1), date(2024, 1, 7)),
            make_week("w2", date(2024, 1, 8), date(2024, 1, 14)),  # No shifts
            make_week("w3", date(2024, 1, 15), date(2024, 1, 21)),
        ]
        shifts = [
            make_shift("s1", "w1", date(2024, 1, 1)),
            # No shifts for w2
            make_shift("s2", "w3", date(2024, 1, 15)),
        ]

        result = compute_travel(
            industry="general",
            travel_distance_km=None,
            lodging_input=None,
            weeks=weeks,
            shifts=shifts,
            get_travel_rate=mock_travel_rate,
            right_enabled=True,
        )

        # Only 2 weeks should appear in weekly_detail
        assert len(result.weekly_detail) == 2
        assert result.grand_total_travel_days == 2


class TestDenseLodgingMonthlyPattern:
    """Tests for dense lodging monthly patterns where floor (2 × visits) kicks in.

    From skill verification table:
    | work_days | visits | nights | travel_days              |
    | 23        | 7      | 20     | max(14, 10) = 14         |
    | 20        | 7      | 20     | max(14, 7) = 14          |

    These test cases verify the corrected formula: max(2 × visits, work_days + visits - nights)
    """

    def test_dense_lodging_january_2023_23_work_days(self):
        """Dense lodging — January 2023 with 23 work days.

        23 work days, 7 visits, 20 nights
        Formula: max(2*7, 23+7-20) = max(14, 10) = 14 travel days

        The floor (14) kicks in because the formula result (10) is below it.
        """
        from datetime import timedelta

        # January 2023 starts with Jan 1 (Sunday), Jan 2 (Monday)
        # Create weeks to get exactly 23 work days in January
        # Week 1: Jan 2-6 (5 days)
        # Week 2: Jan 9-13 (5 days)
        # Week 3: Jan 16-20 (5 days)
        # Week 4: Jan 23-27 (5 days)
        # Week 5: Jan 30-31 (3 days in January, continue to Feb)
        # Total: 5+5+5+5+3 = 23 days

        weeks = []
        shifts = []
        shift_count = 0

        # Create 5 weeks
        week_starts = [
            date(2023, 1, 2),
            date(2023, 1, 9),
            date(2023, 1, 16),
            date(2023, 1, 23),
            date(2023, 1, 30),
        ]

        for week_num, week_start in enumerate(week_starts):
            week_id = f"w{week_num + 1}"
            week_end = week_start + timedelta(days=6)
            weeks.append(make_week(week_id, week_start, week_end))

            # For week 5, only add Jan 30, 31 (Mon, Tue) + Feb 1 (Wed)
            # But we want exactly 23 in January, so we control the shifts
            if week_num < 4:
                # Full week: 5 days
                for day_offset in range(5):
                    shift_date = week_start + timedelta(days=day_offset)
                    shift_count += 1
                    shifts.append(make_shift(f"s{shift_count}", week_id, shift_date))
            else:
                # Week 5: only Jan 30, 31 (3 Jan days: Mon, Tue + Feb starts Wed)
                for day_offset in range(3):  # Mon, Tue, Wed = Jan 30, 31, Feb 1
                    shift_date = week_start + timedelta(days=day_offset)
                    shift_count += 1
                    shifts.append(make_shift(f"s{shift_count}", week_id, shift_date))

        lodging_input = LodgingInput(
            periods=[
                make_lodging_period(
                    "LP1",
                    date(2023, 1, 1),
                    date(2023, 1, 31),
                    pattern_type="monthly",
                    total_nights=20,
                    total_visits=7,
                )
            ]
        )

        result = compute_travel(
            industry="construction",
            travel_distance_km=Decimal("25"),
            lodging_input=lodging_input,
            weeks=weeks,
            shifts=shifts,
            get_travel_rate=mock_travel_rate,
            right_enabled=True,
        )

        jan_breakdown = next(
            (b for b in result.monthly_breakdown if b.month == (2023, 1)),
            None
        )

        # January: 23 work days (by calendar), max(14, 23+7-20) = max(14, 10) = 14
        assert jan_breakdown is not None
        assert jan_breakdown.travel_days == 14

    def test_dense_lodging_february_2023_20_work_days(self):
        """Dense lodging — February 2023 with 20 work days.

        20 work days, 7 visits, 20 nights
        Formula: max(2*7, 20+7-20) = max(14, 7) = 14 travel days

        The floor (14) kicks in because the formula result (7) is below it.
        """
        from datetime import timedelta

        # February 2023: Feb 1 (Wed) to Feb 28 (Tue)
        # Work weeks: Feb 6-10, Feb 13-17, Feb 20-24, Feb 27-28
        # Let's simplify: 4 full weeks × 5 = 20 work days

        weeks = []
        shifts = []
        shift_count = 0

        week_starts = [
            date(2023, 2, 6),
            date(2023, 2, 13),
            date(2023, 2, 20),
            date(2023, 2, 27),
        ]

        for week_num, week_start in enumerate(week_starts):
            week_id = f"w{week_num + 1}"
            week_end = week_start + timedelta(days=6)
            weeks.append(make_week(week_id, week_start, week_end))

            # Add 5 shifts (Mon-Fri) for each week
            for day_offset in range(5):
                shift_date = week_start + timedelta(days=day_offset)
                # Only add shifts that fall in February
                if shift_date.month == 2:
                    shift_count += 1
                    shifts.append(make_shift(f"s{shift_count}", week_id, shift_date))

        lodging_input = LodgingInput(
            periods=[
                make_lodging_period(
                    "LP1",
                    date(2023, 2, 1),
                    date(2023, 2, 28),
                    pattern_type="monthly",
                    total_nights=20,
                    total_visits=7,
                )
            ]
        )

        result = compute_travel(
            industry="construction",
            travel_distance_km=Decimal("25"),
            lodging_input=lodging_input,
            weeks=weeks,
            shifts=shifts,
            get_travel_rate=mock_travel_rate,
            right_enabled=True,
        )

        feb_breakdown = next(
            (b for b in result.monthly_breakdown if b.month == (2023, 2)),
            None
        )

        # February: 20 work days, max(14, 20+7-20) = max(14, 7) = 14
        assert feb_breakdown is not None
        assert feb_breakdown.travel_days == 14


class TestCrossMonthWeekSplit:
    """Tests for proportional splitting of weeks that cross month boundaries.

    For weekly lodging patterns, weeks crossing month boundaries must be split
    proportionally based on work days in each month.

    Anti-pattern from SKILL §7: DO NOT attribute the entire week to the month
    of its start_date. A week starting Jan 29 with 3 work days in Jan and 2 in Feb
    must contribute 3/5 of its travel days to January and 2/5 to February.
    """

    def test_week_crossing_jan_feb_weekly_lodging(self):
        """Week 2023-01-29 – 2023-02-04 with weekly lodging pattern.

        Week spans Jan-Feb with 5 work days (Sun-Thu):
        - Jan 29, 30, 31: 3 work days in January
        - Feb 1, 2: 2 work days in February

        With weekly lodging (4 nights, 1 visit): travel_days = 2

        Expected split:
        - January: 3/5 × 2 = 1.2 → rounds to 1
        - February: 2/5 × 2 = 0.8 → rounds to 1
        """
        from datetime import timedelta

        # Single week crossing Jan-Feb
        week = make_week("w1", date(2023, 1, 29), date(2023, 2, 4))

        # 5 work days: Sun-Thu = Jan 29, 30, 31, Feb 1, 2
        shifts = [
            make_shift("s1", "w1", date(2023, 1, 29)),  # Sunday
            make_shift("s2", "w1", date(2023, 1, 30)),  # Monday
            make_shift("s3", "w1", date(2023, 1, 31)),  # Tuesday
            make_shift("s4", "w1", date(2023, 2, 1)),   # Wednesday
            make_shift("s5", "w1", date(2023, 2, 2)),   # Thursday
        ]

        lodging_input = LodgingInput(
            periods=[
                make_lodging_period(
                    "LP1",
                    date(2023, 1, 1),
                    date(2023, 2, 28),
                    pattern_type="weekly",
                    total_nights=4,
                    total_visits=1,
                )
            ]
        )

        result = compute_travel(
            industry="construction",
            travel_distance_km=Decimal("25"),
            lodging_input=lodging_input,
            weeks=[week],
            shifts=shifts,
            get_travel_rate=mock_travel_rate,
            right_enabled=True,
        )

        # Weekly detail shows 2 travel days for the week
        assert len(result.weekly_detail) == 1
        assert result.weekly_detail[0].travel_days == 2

        # Monthly breakdown should split proportionally
        jan_breakdown = next(
            (b for b in result.monthly_breakdown if b.month == (2023, 1)),
            None
        )
        feb_breakdown = next(
            (b for b in result.monthly_breakdown if b.month == (2023, 2)),
            None
        )

        # January: 3/5 × 2 = 1.2 → rounds to 1
        assert jan_breakdown is not None
        assert jan_breakdown.travel_days == 1

        # February: 2/5 × 2 = 0.8 → rounds to 1
        assert feb_breakdown is not None
        assert feb_breakdown.travel_days == 1

        # Total should still be 2 (rounding may distribute differently)
        assert result.grand_total_travel_days == 2

    def test_week_crossing_month_no_lodging(self):
        """Week crossing month boundary without lodging (all work days are travel days).

        Week 2023-01-29 – 2023-02-04 with 5 work days:
        - Jan 29, 30, 31: 3 work days in January
        - Feb 1, 2: 2 work days in February

        No lodging: travel_days = work_days = 5

        Expected split:
        - January: 3/5 × 5 = 3 travel days
        - February: 2/5 × 5 = 2 travel days
        """
        week = make_week("w1", date(2023, 1, 29), date(2023, 2, 4))

        shifts = [
            make_shift("s1", "w1", date(2023, 1, 29)),
            make_shift("s2", "w1", date(2023, 1, 30)),
            make_shift("s3", "w1", date(2023, 1, 31)),
            make_shift("s4", "w1", date(2023, 2, 1)),
            make_shift("s5", "w1", date(2023, 2, 2)),
        ]

        result = compute_travel(
            industry="general",
            travel_distance_km=None,
            lodging_input=None,
            weeks=[week],
            shifts=shifts,
            get_travel_rate=mock_travel_rate,
            right_enabled=True,
        )

        assert result.weekly_detail[0].travel_days == 5

        jan_breakdown = next(
            (b for b in result.monthly_breakdown if b.month == (2023, 1)),
            None
        )
        feb_breakdown = next(
            (b for b in result.monthly_breakdown if b.month == (2023, 2)),
            None
        )

        # January: 3/5 × 5 = 3 travel days
        assert jan_breakdown is not None
        assert jan_breakdown.travel_days == 3

        # February: 2/5 × 5 = 2 travel days
        assert feb_breakdown is not None
        assert feb_breakdown.travel_days == 2

        assert result.grand_total_travel_days == 5


# =============================================================================
# cycle_weeks Tests — Multi-Week Lodging Cycles
# =============================================================================

class TestComputeBlockTravelDays:
    """Tests for compute_block_travel_days helper function."""

    def test_no_lodging(self):
        """No lodging: all work days are travel days."""
        assert compute_block_travel_days(5, None) == 5
        assert compute_block_travel_days(3, None) == 3
        assert compute_block_travel_days(0, None) == 0

    def test_single_work_day_returns_1(self):
        """BUG FIX: Single work day should return 1 (departure OR return, not both).

        A single work day at start/end of employment = departure only OR return only.
        The old formula returned 2 (floor of 2 × visits), which was incorrect.
        """
        period = make_lodging_period("LP1", date(2024, 1, 1), date(2024, 12, 31), "weekly", 4, 1)
        # BUG FIX: work_days=1 → 1 (not 2)
        assert compute_block_travel_days(1, period) == 1

    def test_block_work_days_greater_than_1(self):
        """Normal case: block_work_days > 1 uses standard formula."""
        period = make_lodging_period("LP1", date(2024, 1, 1), date(2024, 12, 31), "weekly", 4, 1)
        # 5 work days: max(2, 5+1-4) = max(2, 2) = 2
        assert compute_block_travel_days(5, period) == 2
        # 10 work days (for cycle_weeks=2): max(2, 10+1-4) = max(2, 7) = 7
        # Note: with 10 nights for 2 weeks: max(2, 10+1-10) = max(2, 1) = 2
        period_2wk = make_lodging_period("LP2", date(2024, 1, 1), date(2024, 12, 31), "weekly", 10, 1)
        assert compute_block_travel_days(10, period_2wk) == 2


class TestCaseACycleWeeks1FullWeek:
    """Case A — cycle_weeks=1, full week (existing behavior must be preserved).

    visit_groups=[{nights_per_visit:4, count:1}], cycle_weeks=1
    work_days=5 → max(2, 5+1-4) = 2 ✓
    """

    def test_cycle_weeks_1_full_week(self):
        from datetime import timedelta

        week = make_week("w1", date(2024, 1, 1), date(2024, 1, 7))
        shifts = [
            make_shift(f"s{i+1}", "w1", date(2024, 1, 1) + timedelta(days=i))
            for i in range(5)
        ]

        lodging_input = LodgingInput(
            periods=[
                make_lodging_period(
                    "LP1",
                    date(2024, 1, 1),
                    date(2024, 12, 31),
                    pattern_type="weekly",
                    total_nights=4,
                    total_visits=1,
                    cycle_weeks=1,  # Standard weekly
                )
            ]
        )

        result = compute_travel(
            industry="construction",
            travel_distance_km=Decimal("25"),
            lodging_input=lodging_input,
            weeks=[week],
            shifts=shifts,
            get_travel_rate=mock_travel_rate,
            right_enabled=True,
        )

        assert len(result.weekly_detail) == 1
        assert result.weekly_detail[0].work_days == 5
        # max(2, 5+1-4) = 2
        assert result.weekly_detail[0].travel_days == 2
        assert result.grand_total_travel_days == 2


class TestCaseBCycleWeeks1SingleWorkDay:
    """Case B — cycle_weeks=1, single work day (BUG FIX).

    visit_groups=[{nights_per_visit:4, count:1}], cycle_weeks=1
    work_days=1 → 1 ✓ (was: 2 — incorrect)
    """

    def test_cycle_weeks_1_single_work_day_bug_fix(self):
        week = make_week("w1", date(2024, 1, 1), date(2024, 1, 7))
        shifts = [make_shift("s1", "w1", date(2024, 1, 1))]  # Single work day

        lodging_input = LodgingInput(
            periods=[
                make_lodging_period(
                    "LP1",
                    date(2024, 1, 1),
                    date(2024, 12, 31),
                    pattern_type="weekly",
                    total_nights=4,
                    total_visits=1,
                    cycle_weeks=1,
                )
            ]
        )

        result = compute_travel(
            industry="construction",
            travel_distance_km=Decimal("25"),
            lodging_input=lodging_input,
            weeks=[week],
            shifts=shifts,
            get_travel_rate=mock_travel_rate,
            right_enabled=True,
        )

        assert len(result.weekly_detail) == 1
        assert result.weekly_detail[0].work_days == 1
        # BUG FIX: Single work day = 1 (not 2)
        assert result.weekly_detail[0].travel_days == 1
        assert result.grand_total_travel_days == 1


class TestCaseCCycleWeeks2FullBlock:
    """Case C — cycle_weeks=2, full block (2 consecutive work weeks).

    visit_groups=[{nights_per_visit:10, count:1}], cycle_weeks=2
    week1=5 days, week2=5 days → block_work_days=10
    max(2, 10+1-10) = 2 → each week gets 1 travel day ✓
    """

    def test_cycle_weeks_2_full_block(self):
        from datetime import timedelta

        weeks = [
            make_week("w1", date(2024, 1, 1), date(2024, 1, 7)),
            make_week("w2", date(2024, 1, 8), date(2024, 1, 14)),
        ]
        shifts = []
        shift_count = 0
        for week_idx, week in enumerate(weeks):
            for day_offset in range(5):
                shift_count += 1
                shift_date = week.start_date + timedelta(days=day_offset)
                shifts.append(make_shift(f"s{shift_count}", week.id, shift_date))

        lodging_input = LodgingInput(
            periods=[
                make_lodging_period(
                    "LP1",
                    date(2024, 1, 1),
                    date(2024, 12, 31),
                    pattern_type="weekly",
                    total_nights=10,  # 10 nights per 2-week cycle
                    total_visits=1,
                    cycle_weeks=2,  # 2-week cycle
                )
            ]
        )

        result = compute_travel(
            industry="construction",
            travel_distance_km=Decimal("25"),
            lodging_input=lodging_input,
            weeks=weeks,
            shifts=shifts,
            get_travel_rate=mock_travel_rate,
            right_enabled=True,
        )

        assert len(result.weekly_detail) == 2
        # Block: 10 work days, max(2, 10+1-10) = 2
        # Each week gets proportional share: 5/10 × 2 = 1
        assert result.weekly_detail[0].travel_days == 1
        assert result.weekly_detail[1].travel_days == 1
        assert result.grand_total_travel_days == 2


class TestCaseDCycleWeeks2PartialBlock:
    """Case D — cycle_weeks=2, partial block (single week at end of employment).

    cycle_weeks=2, but last block contains only 1 week
    work_days=5 → block_work_days=5
    max(2, 5+1-10) = max(2,-4) = 2
    → The partial block gets 2 travel days (departure + return — still a complete visit) ✓
    """

    def test_cycle_weeks_2_partial_block(self):
        from datetime import timedelta

        # Two full blocks of 2 weeks, then one partial block with 1 week
        weeks = [
            make_week("w1", date(2024, 1, 1), date(2024, 1, 7)),
            make_week("w2", date(2024, 1, 8), date(2024, 1, 14)),
            make_week("w3", date(2024, 1, 15), date(2024, 1, 21)),
            make_week("w4", date(2024, 1, 22), date(2024, 1, 28)),
            make_week("w5", date(2024, 1, 29), date(2024, 2, 4)),  # Partial block (only 1 week)
        ]
        shifts = []
        shift_count = 0
        for week in weeks:
            for day_offset in range(5):
                shift_count += 1
                shift_date = week.start_date + timedelta(days=day_offset)
                shifts.append(make_shift(f"s{shift_count}", week.id, shift_date))

        lodging_input = LodgingInput(
            periods=[
                make_lodging_period(
                    "LP1",
                    date(2024, 1, 1),
                    date(2024, 2, 28),
                    pattern_type="weekly",
                    total_nights=10,
                    total_visits=1,
                    cycle_weeks=2,
                )
            ]
        )

        result = compute_travel(
            industry="construction",
            travel_distance_km=Decimal("25"),
            lodging_input=lodging_input,
            weeks=weeks,
            shifts=shifts,
            get_travel_rate=mock_travel_rate,
            right_enabled=True,
        )

        assert len(result.weekly_detail) == 5

        # Block 1 (w1, w2): 10 work days → max(2, 10+1-10) = 2, each gets 1
        assert result.weekly_detail[0].travel_days == 1
        assert result.weekly_detail[1].travel_days == 1

        # Block 2 (w3, w4): 10 work days → max(2, 10+1-10) = 2, each gets 1
        assert result.weekly_detail[2].travel_days == 1
        assert result.weekly_detail[3].travel_days == 1

        # Block 3 (w5 only — partial): 5 work days → max(2, 5+1-10) = max(2, -4) = 2
        assert result.weekly_detail[4].travel_days == 2

        # Total: 1+1 + 1+1 + 2 = 6
        assert result.grand_total_travel_days == 6


class TestCaseECycleWeeks2SingleWorkDayInBlock:
    """Case E — cycle_weeks=2, single week in block with only 1 work day.

    cycle_weeks=2, block contains only 1 week with work_days=1
    → travel_days = 1 ✓ (BUG FIX applies to blocks too)
    """

    def test_cycle_weeks_2_single_work_day_block(self):
        week = make_week("w1", date(2024, 1, 1), date(2024, 1, 7))
        shifts = [make_shift("s1", "w1", date(2024, 1, 1))]  # Single work day

        lodging_input = LodgingInput(
            periods=[
                make_lodging_period(
                    "LP1",
                    date(2024, 1, 1),
                    date(2024, 12, 31),
                    pattern_type="weekly",
                    total_nights=10,
                    total_visits=1,
                    cycle_weeks=2,
                )
            ]
        )

        result = compute_travel(
            industry="construction",
            travel_distance_km=Decimal("25"),
            lodging_input=lodging_input,
            weeks=[week],
            shifts=shifts,
            get_travel_rate=mock_travel_rate,
            right_enabled=True,
        )

        assert len(result.weekly_detail) == 1
        assert result.weekly_detail[0].work_days == 1
        # BUG FIX: Single work day in block = 1 (not 2)
        assert result.weekly_detail[0].travel_days == 1
        assert result.grand_total_travel_days == 1


class TestCycleWeeksWithDifferentPeriods:
    """Test cycle_weeks transitions when moving between different lodging periods."""

    def test_different_cycle_weeks_in_different_periods(self):
        """Period 1: cycle_weeks=1, Period 2: cycle_weeks=2"""
        from datetime import timedelta

        weeks = [
            make_week("w1", date(2024, 1, 1), date(2024, 1, 7)),   # Period 1 (cycle=1)
            make_week("w2", date(2024, 1, 8), date(2024, 1, 14)),  # Period 1 (cycle=1)
            make_week("w3", date(2024, 1, 15), date(2024, 1, 21)), # Period 2 (cycle=2)
            make_week("w4", date(2024, 1, 22), date(2024, 1, 28)), # Period 2 (cycle=2)
        ]
        shifts = []
        shift_count = 0
        for week in weeks:
            for day_offset in range(5):
                shift_count += 1
                shift_date = week.start_date + timedelta(days=day_offset)
                shifts.append(make_shift(f"s{shift_count}", week.id, shift_date))

        lodging_input = LodgingInput(
            periods=[
                make_lodging_period(
                    "LP1",
                    date(2024, 1, 1),
                    date(2024, 1, 14),
                    pattern_type="weekly",
                    total_nights=4,
                    total_visits=1,
                    cycle_weeks=1,  # Weekly
                ),
                make_lodging_period(
                    "LP2",
                    date(2024, 1, 15),
                    date(2024, 1, 31),
                    pattern_type="weekly",
                    total_nights=10,
                    total_visits=1,
                    cycle_weeks=2,  # Bi-weekly
                ),
            ]
        )

        result = compute_travel(
            industry="construction",
            travel_distance_km=Decimal("25"),
            lodging_input=lodging_input,
            weeks=weeks,
            shifts=shifts,
            get_travel_rate=mock_travel_rate,
            right_enabled=True,
        )

        assert len(result.weekly_detail) == 4

        # Period 1 (w1, w2): cycle_weeks=1, each week computed separately
        # 5 work days: max(2, 5+1-4) = 2
        assert result.weekly_detail[0].travel_days == 2
        assert result.weekly_detail[1].travel_days == 2

        # Period 2 (w3, w4): cycle_weeks=2, computed as a block
        # Block: 10 work days, max(2, 10+1-10) = 2, each gets 1
        assert result.weekly_detail[2].travel_days == 1
        assert result.weekly_detail[3].travel_days == 1

        # Total: 2+2 + 1+1 = 6
        assert result.grand_total_travel_days == 6
