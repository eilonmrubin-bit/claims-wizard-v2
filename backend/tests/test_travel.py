"""Tests for travel allowance (דמי נסיעות) module.

See docs/skills/travel/SKILL.md for test cases.

Updated for new period-based LodgingInput structure.
New formula: travel_days = work_days + visits - nights
"""

import pytest
from datetime import date
from decimal import Decimal

from app.modules.travel import compute_travel, compute_weekly_travel_days, get_work_days_in_week
from app.ssot import Week, Shift, LodgingInput, LodgingPeriod


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
    nights_per_unit: int = 4,
    visits_per_unit: int = 1,
) -> LodgingPeriod:
    """Create a LodgingPeriod for testing."""
    return LodgingPeriod(
        id=period_id,
        start=start,
        end=end,
        pattern_type=pattern_type,
        nights_per_unit=nights_per_unit,
        visits_per_unit=visits_per_unit,
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
        """Weekly lodging, 4 nights, 1 visit: travel_days = work_days + 1 - 4."""
        # 4 nights/week, 1 visit/week
        period = make_lodging_period("LP1", date(2024, 1, 1), date(2024, 12, 31), "weekly", 4, 1)
        # 5 work days: 5 + 1 - 4 = 2
        assert compute_weekly_travel_days(5, period) == 2
        # 3 work days: 3 + 1 - 4 = 0
        assert compute_weekly_travel_days(3, period) == 0
        # 6 work days: 6 + 1 - 4 = 3
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

    def test_negative_result_clamped_to_zero(self):
        """Travel days can't be negative."""
        # 4 nights, 1 visit, 1 work day: 1 + 1 - 4 = -2 → 0
        period = make_lodging_period("LP1", date(2024, 1, 1), date(2024, 12, 31), "weekly", 4, 1)
        assert compute_weekly_travel_days(1, period) == 0
        assert compute_weekly_travel_days(2, period) == 0  # 2 + 1 - 4 = -1 → 0


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
                    nights_per_unit=4,
                    visits_per_unit=1,
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
                    nights_per_unit=4,
                    visits_per_unit=1,
                ),
                make_lodging_period(
                    "LP2",
                    date(2024, 2, 1),
                    date(2024, 2, 29),
                    pattern_type="weekly",
                    nights_per_unit=3,
                    visits_per_unit=2,
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
        travel_days = 3 + 1 - 4 = 0 (clamped to 0 from negative)
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
                    nights_per_unit=4,
                    visits_per_unit=1,
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
        # 3 + 1 - 4 = 0 (clamped from negative)
        assert result.weekly_detail[0].travel_days == 0


class TestCase7SingleDayLodgingWeek:
    """Case 7 — Single work day in lodging week.

    Input:
        lodging: weekly, 4 nights, 1 visit
        work_days = 1 (holiday week, only 1 day worked)

    Expected:
        travel_days = 1 + 1 - 4 = -2 → clamped to 0
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
                    nights_per_unit=4,
                    visits_per_unit=1,
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
        # 1 + 1 - 4 = -2 → 0
        assert result.weekly_detail[0].travel_days == 0


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
                    nights_per_unit=4,
                    visits_per_unit=1,
                ),
                make_lodging_period(
                    "LP2",
                    date(2024, 1, 22),
                    date(2024, 1, 31),  # Week 4 only
                    pattern_type="weekly",
                    nights_per_unit=4,
                    visits_per_unit=1,
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
                    nights_per_unit=4,
                    visits_per_unit=1,
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
