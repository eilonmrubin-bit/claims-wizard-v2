"""Tests for travel allowance (דמי נסיעות) module.

See docs/skills/travel/SKILL.md for test cases.
"""

import pytest
from datetime import date
from decimal import Decimal

from app.modules.travel import compute_travel, compute_week_travel, get_work_days_in_week
from app.ssot import Week, Shift, LodgingInput, LodgingWeek


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


def mock_travel_rate(industry: str, distance_km: Decimal | None, target_date: date) -> Decimal:
    """Mock travel rate lookup for testing."""
    if industry == "construction":
        if distance_km is not None and distance_km >= 40:
            return Decimal("39.60")
        else:
            return Decimal("26.40")
    else:
        return Decimal("22.60")


class TestComputeWeekTravel:
    """Tests for compute_week_travel helper function."""

    def test_daily_return_pattern(self):
        """Daily return: all work days are travel days."""
        assert compute_week_travel(5, "daily_return") == 5
        assert compute_week_travel(3, "daily_return") == 3
        assert compute_week_travel(1, "daily_return") == 1
        assert compute_week_travel(0, "daily_return") == 0

    def test_no_lodging_pattern(self):
        """No lodging: all work days are travel days."""
        assert compute_week_travel(5, "no_lodging") == 5
        assert compute_week_travel(3, "no_lodging") == 3
        assert compute_week_travel(1, "no_lodging") == 1
        assert compute_week_travel(0, "no_lodging") == 0

    def test_full_lodging_pattern_standard_week(self):
        """Full lodging with 5 work days: 2 travel days (departure + return)."""
        assert compute_week_travel(5, "full_lodging") == 2

    def test_full_lodging_pattern_multiple_days(self):
        """Full lodging with 2+ work days: always 2 travel days."""
        assert compute_week_travel(6, "full_lodging") == 2
        assert compute_week_travel(4, "full_lodging") == 2
        assert compute_week_travel(3, "full_lodging") == 2
        assert compute_week_travel(2, "full_lodging") == 2

    def test_full_lodging_pattern_single_day(self):
        """Full lodging with 1 work day: 1 travel day (departure OR return)."""
        assert compute_week_travel(1, "full_lodging") == 1

    def test_full_lodging_pattern_no_work_days(self):
        """Full lodging with 0 work days: 0 travel days."""
        assert compute_week_travel(0, "full_lodging") == 0

    def test_unknown_pattern_falls_back_to_work_days(self):
        """Unknown pattern: treated as no lodging."""
        assert compute_week_travel(5, "unknown") == 5


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
        lodging: has_lodging=true, cycle_weeks=1,
                 cycle=[{week_in_cycle:1, pattern:"full_lodging"}]
        daily_rate: 26.4 ₪
        employment: 2024-01-01 – 2024-03-31
        work pattern: 5 days/week (Mon–Fri)

    Expected:
        Per week: work_days=5, pattern=full_lodging → travel_days=2
        ~13 weeks:
            grand_total_travel_days = 26
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
            has_lodging=True,
            cycle_weeks=1,
            cycle=[LodgingWeek(week_in_cycle=1, pattern="full_lodging")],
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
        assert result.lodging_cycle_weeks == 1

        # Each week should have 2 travel days (departure + return)
        for detail in result.weekly_detail:
            assert detail.week_pattern == "full_lodging"
            assert detail.travel_days == 2

        # 13 weeks × 2 travel days = 26
        assert result.grand_total_travel_days == 26
        # 26 × 26.4 = 686.4
        assert result.grand_total_value == Decimal("686.40")


class TestCase5ConstructionMixedCycle:
    """Case 5 — Construction, mixed cycle (3 weeks lodging + 1 week daily).

    Input:
        lodging: cycle_weeks=4,
            cycle=[{1:"full_lodging"},{2:"full_lodging"},{3:"full_lodging"},{4:"daily_return"}]
        work_days/week: 5
        daily_rate: 26.4

    Expected per 4-week cycle:
        Weeks 1,2,3 (full_lodging): 2 travel_days each = 6 travel days
        Week 4 (daily_return): 5 travel_days
        Total per cycle: 11 travel_days
    """

    def test_construction_mixed_cycle(self):
        # Create exactly 4 weeks for one complete cycle
        weeks = []
        shifts = []
        shift_count = 0

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

        lodging_input = LodgingInput(
            has_lodging=True,
            cycle_weeks=4,
            cycle=[
                LodgingWeek(week_in_cycle=1, pattern="full_lodging"),
                LodgingWeek(week_in_cycle=2, pattern="full_lodging"),
                LodgingWeek(week_in_cycle=3, pattern="full_lodging"),
                LodgingWeek(week_in_cycle=4, pattern="daily_return"),
            ],
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
        assert result.lodging_cycle_weeks == 4

        # Check each week's pattern and travel days
        assert result.weekly_detail[0].cycle_position == 1
        assert result.weekly_detail[0].week_pattern == "full_lodging"
        assert result.weekly_detail[0].travel_days == 2

        assert result.weekly_detail[1].cycle_position == 2
        assert result.weekly_detail[1].week_pattern == "full_lodging"
        assert result.weekly_detail[1].travel_days == 2

        assert result.weekly_detail[2].cycle_position == 3
        assert result.weekly_detail[2].week_pattern == "full_lodging"
        assert result.weekly_detail[2].travel_days == 2

        assert result.weekly_detail[3].cycle_position == 4
        assert result.weekly_detail[3].week_pattern == "daily_return"
        assert result.weekly_detail[3].travel_days == 5

        # Total: 2+2+2+5 = 11 travel days
        assert result.grand_total_travel_days == 11
        # 11 × 26.4 = 290.4
        assert result.grand_total_value == Decimal("290.40")


class TestCase6PartialWeekEmploymentStart:
    """Case 6 — Partial week, employment starts mid-week (lodging mode).

    Input:
        industry: "construction", travel_distance_km: 20
        lodging: cycle_weeks=1, cycle=[{1:"full_lodging"}]
        employment start: 2024-01-03 (Wednesday)
        first week: work_days=3 (Wed, Thu, Fri)

    Expected:
        Partial week at start:
            week_pattern = "full_lodging", work_days = 3
            → travel_days = 2
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
            has_lodging=True,
            cycle_weeks=1,
            cycle=[LodgingWeek(week_in_cycle=1, pattern="full_lodging")],
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
        assert result.weekly_detail[0].week_pattern == "full_lodging"
        assert result.weekly_detail[0].travel_days == 2  # Departure + return


class TestCase7SingleDayLodgingWeek:
    """Case 7 — Anti-pattern: single work day in lodging week.

    Input:
        lodging: full_lodging
        work_days = 1 (holiday week, only 1 day worked)

    Expected:
        travel_days = 1 (NOT 2)
    """

    def test_single_day_lodging_week(self):
        week = make_week("w1", date(2024, 1, 1), date(2024, 1, 7))
        shifts = [
            make_shift("s1", "w1", date(2024, 1, 1)),  # Only one day worked
        ]

        lodging_input = LodgingInput(
            has_lodging=True,
            cycle_weeks=1,
            cycle=[LodgingWeek(week_in_cycle=1, pattern="full_lodging")],
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
        assert result.weekly_detail[0].travel_days == 1  # NOT 2


class TestCase8CycleResetsAfterGap:
    """Case 8 — Cycle resets after employment gap.

    Input:
        Employment period 1: Jan–Mar 2023 (cycle_weeks=4, patterns: L,L,L,D)
        Gap: Apr–May 2023
        Employment period 2: Jun–Sep 2023

    Expected:
        Period 2 week 1 → cycle_position = 1 (resets)
        Period 2 week 2 → cycle_position = 2
    """

    def test_cycle_resets_after_gap(self):
        weeks = []
        shifts = []
        shift_count = 0

        # Period 1: 2 weeks in January
        for week_num in range(2):
            week_id = f"w{week_num + 1}"
            week_start = date(2023, 1, 1 + week_num * 7)
            week_end = date(2023, 1, 7 + week_num * 7)
            weeks.append(make_week(week_id, week_start, week_end))

            for day_offset in range(5):
                shift_count += 1
                shift_date = date(2023, 1, week_start.day + day_offset)
                shifts.append(make_shift(f"s{shift_count}", week_id, shift_date))

        # Gap: No weeks in April-May (more than 7 days gap)

        # Period 2: 2 weeks in June (starts June 5, well after gap)
        for week_num in range(2):
            week_id = f"w{week_num + 3}"
            week_start = date(2023, 6, 5 + week_num * 7)
            week_end = date(2023, 6, 11 + week_num * 7)
            weeks.append(make_week(week_id, week_start, week_end))

            for day_offset in range(5):
                shift_count += 1
                shift_date = date(2023, 6, week_start.day + day_offset)
                shifts.append(make_shift(f"s{shift_count}", week_id, shift_date))

        lodging_input = LodgingInput(
            has_lodging=True,
            cycle_weeks=4,
            cycle=[
                LodgingWeek(week_in_cycle=1, pattern="full_lodging"),
                LodgingWeek(week_in_cycle=2, pattern="full_lodging"),
                LodgingWeek(week_in_cycle=3, pattern="full_lodging"),
                LodgingWeek(week_in_cycle=4, pattern="daily_return"),
            ],
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

        # Period 1: weeks 1 and 2 should be cycle positions 1 and 2
        assert result.weekly_detail[0].cycle_position == 1
        assert result.weekly_detail[1].cycle_position == 2

        # Period 2: after gap, cycle resets - positions should be 1 and 2 again
        assert result.weekly_detail[2].cycle_position == 1  # Reset!
        assert result.weekly_detail[3].cycle_position == 2


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
            has_lodging=True,
            cycle_weeks=1,
            cycle=[LodgingWeek(week_in_cycle=1, pattern="full_lodging")],
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
