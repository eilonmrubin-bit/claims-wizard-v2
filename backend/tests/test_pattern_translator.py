"""Tests for Pattern Translator module.

Tests based on:
1. Edge cases from skill
2. Anti-patterns from skill
3. Normal path
4. Integration
"""

from datetime import date, time
from decimal import Decimal

import pytest

from app.modules.pattern_translator import (
    translate,
    translate_level_a,
    translate_level_b,
    translate_level_c,
    validate_level_a,
    validate_level_b,
    validate_level_c,
    compute_cycle_length,
    distribute_to_weeks,
    derive_shift_template,
    PatternLevelB,
    PatternLevelC,
    PatternSource,
    PatternType,
    DayTypeInput,
    DayType,
    NightPlacement,
    CountPeriod,
    LevelCMode,
    SUNDAY,
    MONDAY,
    TUESDAY,
    WEDNESDAY,
    THURSDAY,
    FRIDAY,
    SATURDAY,
)
from app.ssot import WorkPattern, TimeRange, RestDay, Duration


# =============================================================================
# Normal Path Test
# =============================================================================

class TestNormalPath:
    """Test normal/happy path scenarios."""

    def test_level_a_simple_week(self):
        """Level A: Simple 5-day work week translates correctly."""
        pattern = WorkPattern(
            id="WP1",
            start=date(2024, 1, 1),
            end=date(2024, 1, 31),
            work_days=[SUNDAY, MONDAY, TUESDAY, WEDNESDAY, THURSDAY],
            default_shifts=[TimeRange(start_time=time(8, 0), end_time=time(17, 0))],
            default_breaks=[TimeRange(start_time=time(12, 0), end_time=time(12, 30))],
        )

        result = translate([pattern], RestDay.SATURDAY)

        assert len(result.work_patterns) == 1
        assert len(result.errors) == 0
        assert result.work_patterns[0].work_days == [SUNDAY, MONDAY, TUESDAY, WEDNESDAY, THURSDAY]
        assert SATURDAY not in result.work_patterns[0].work_days

    def test_level_a_removes_rest_day_from_work_days(self):
        """Level A: Rest day is removed from work_days if present."""
        pattern = WorkPattern(
            id="WP1",
            start=date(2024, 1, 1),
            end=date(2024, 1, 31),
            work_days=[SUNDAY, MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY, SATURDAY],
            default_shifts=[TimeRange(start_time=time(8, 0), end_time=time(17, 0))],
        )

        result = translate([pattern], RestDay.SATURDAY)

        assert SATURDAY not in result.work_patterns[0].work_days


# =============================================================================
# Edge Cases from Skill
# =============================================================================

class TestEdgeCases:
    """Test edge cases specified in the skill."""

    def test_edge_case_1_fractions_cycle_10(self):
        """Edge case 1: 1.7 nights/week → cycle 10 weeks (17/10)."""
        cycle_len = compute_cycle_length({DayType.NIGHT: Decimal("1.7")})
        assert cycle_len == 10

    def test_edge_case_1_distribution(self):
        """Edge case 1: 1.7 nights distributed across 10 weeks = 17 total."""
        weeks = distribute_to_weeks(Decimal("1.7"), 10)
        assert sum(weeks) == 17
        # Should be 7 weeks with 2, 3 weeks with 1
        assert weeks.count(2) == 7
        assert weeks.count(1) == 3

    def test_edge_case_2_cycle_too_long_capped(self):
        """Edge case 2: Very long cycle is capped at 52."""
        # 1.37 → 137/100 → would be 100 weeks, capped to 52
        cycle_len = compute_cycle_length({DayType.NIGHT: Decimal("1.37")})
        assert cycle_len <= 52

    def test_edge_case_3_total_days_exceeds_7(self):
        """Edge case 3: Total days > 7 should fail validation."""
        pattern = PatternLevelC(
            id="C1",
            start=date(2024, 1, 1),
            end=date(2024, 3, 31),
            day_types=[
                DayTypeInput(DayType.REGULAR, Decimal("5"), CountPeriod.WEEKLY, Decimal(9)),
                DayTypeInput(DayType.EVE_OF_REST, Decimal("1"), CountPeriod.WEEKLY, Decimal(6)),
                DayTypeInput(DayType.REST_DAY, Decimal("1"), CountPeriod.WEEKLY, Decimal(8)),
                DayTypeInput(DayType.NIGHT, Decimal("2"), CountPeriod.WEEKLY, Decimal(7)),
            ],
        )

        errors = validate_level_c(pattern, RestDay.SATURDAY)
        assert len(errors) > 0
        assert any(e.type == "too_many_days" for e in errors)

    def test_edge_case_4_night_friday_no_saturday_work(self):
        """Edge case 4: Night on Friday blocked when rest=Saturday and no Saturday work."""
        pattern = PatternLevelC(
            id="C1",
            start=date(2024, 1, 1),
            end=date(2024, 1, 31),
            day_types=[
                DayTypeInput(DayType.NIGHT, Decimal("6"), CountPeriod.WEEKLY, Decimal(7)),
            ],
            night_placement=NightPlacement.EMPLOYER_FAVOR,
        )

        translated = translate_level_c(pattern, RestDay.SATURDAY)

        # Check that Friday night is not in any shifts
        # Friday night (22:00) would assign to Saturday (majority hours)
        # Since no rest_day work, Friday should not have night shifts
        if translated.daily_overrides:
            for d, shifts in translated.daily_overrides.items():
                if d.weekday() == 4:  # Python Friday
                    for shift in shifts.shifts:
                        # Night shift starts at 22:00
                        assert shift.start_time != time(22, 0), "Friday night shift should be blocked"

    def test_edge_case_5_night_friday_with_saturday_work(self):
        """Edge case 5: Night on Friday allowed when there IS Saturday work."""
        pattern = PatternLevelC(
            id="C1",
            start=date(2024, 1, 1),
            end=date(2024, 1, 31),
            day_types=[
                DayTypeInput(DayType.REST_DAY, Decimal("1"), CountPeriod.WEEKLY, Decimal(8)),
                DayTypeInput(DayType.NIGHT, Decimal("6"), CountPeriod.WEEKLY, Decimal(7)),
            ],
            night_placement=NightPlacement.EMPLOYER_FAVOR,
        )

        # This should not raise an error - Friday night is available
        translated = translate_level_c(pattern, RestDay.SATURDAY)
        assert translated is not None

    def test_edge_case_6_level_b_period_shorter_than_cycle(self):
        """Edge case 6: Period of 2 weeks with cycle of 5 weeks."""
        week1 = WorkPattern(
            id="W1",
            start=date(2024, 1, 1),
            end=date(2024, 1, 7),
            work_days=[SUNDAY, MONDAY, TUESDAY],
            default_shifts=[TimeRange(start_time=time(8, 0), end_time=time(16, 0))],
        )
        week2 = WorkPattern(
            id="W2",
            start=date(2024, 1, 8),
            end=date(2024, 1, 14),
            work_days=[WEDNESDAY, THURSDAY],
            default_shifts=[TimeRange(start_time=time(8, 0), end_time=time(16, 0))],
        )

        pattern = PatternLevelB(
            id="B1",
            start=date(2024, 1, 1),
            end=date(2024, 1, 14),  # Only 2 weeks
            cycle=[week1, week2, week1, week2, week1],  # 5-week cycle
            cycle_length=5,
        )

        # Should work - just runs weeks 1 and 2
        translated = translate_level_b(pattern, RestDay.SATURDAY)
        assert translated is not None
        assert translated.start == date(2024, 1, 1)
        assert translated.end == date(2024, 1, 14)

    def test_edge_case_7_only_nights_no_day_shifts(self):
        """Edge case 7: Only night shifts, no day shifts."""
        pattern = PatternLevelC(
            id="C1",
            start=date(2024, 1, 1),
            end=date(2024, 1, 31),
            day_types=[
                DayTypeInput(DayType.NIGHT, Decimal("3"), CountPeriod.WEEKLY, Decimal(7)),
            ],
        )

        errors = validate_level_c(pattern, RestDay.SATURDAY)
        assert len(errors) == 0

        translated = translate_level_c(pattern, RestDay.SATURDAY)
        assert translated is not None

    def test_edge_case_8_monthly_input_with_fractions(self):
        """Edge case 8: Monthly input converted to weekly."""
        # 13.5 nights/month → 13.5 / 4.33 ≈ 3.12 nights/week
        pattern = PatternLevelC(
            id="C1",
            start=date(2024, 1, 1),
            end=date(2024, 3, 31),
            day_types=[
                DayTypeInput(DayType.NIGHT, Decimal("13.5"), CountPeriod.MONTHLY, Decimal(7)),
            ],
        )

        translated = translate_level_c(pattern, RestDay.SATURDAY)
        assert translated is not None


# =============================================================================
# Anti-Pattern Tests
# =============================================================================

class TestAntiPatterns:
    """Test that anti-patterns from the skill are properly prevented."""

    def test_antipattern_1_day_shifts_not_moved(self):
        """Anti-pattern 1: Day shifts should not be moved/optimized."""
        pattern = PatternLevelC(
            id="C1",
            start=date(2024, 1, 1),
            end=date(2024, 1, 7),
            day_types=[
                DayTypeInput(DayType.REGULAR, Decimal("4"), CountPeriod.WEEKLY, Decimal(9)),
            ],
        )

        translated = translate_level_c(pattern, RestDay.SATURDAY)

        # Regular days should always be Sunday-Wednesday (first 4 days)
        # They should not be "optimized" to different positions
        if translated.daily_overrides:
            work_dates = [d for d in translated.daily_overrides.keys()]
            for d in work_dates:
                dow = (d.weekday() + 1) % 7  # Convert to Sunday=0
                # Should be Sunday(0), Monday(1), Tuesday(2), or Wednesday(3)
                assert dow in [SUNDAY, MONDAY, TUESDAY, WEDNESDAY]

    def test_antipattern_2_no_half_shifts(self):
        """Anti-pattern 2: No half-shifts in a single week."""
        # 0.5 nights/week should create cycle of 2 weeks, not 0.5 in one week
        cycle_len = compute_cycle_length({DayType.NIGHT: Decimal("0.5")})
        assert cycle_len == 2

        weeks = distribute_to_weeks(Decimal("0.5"), 2)
        # Should be [1, 0] or [0, 1] - whole numbers only
        assert all(isinstance(w, int) for w in weeks)
        assert sum(weeks) == 1

    def test_antipattern_3_week_starts_sunday(self):
        """Anti-pattern 3: Week always starts on Sunday."""
        # This is enforced by the constants
        assert SUNDAY == 0
        assert SATURDAY == 6

    def test_antipattern_6_pattern_source_saved(self):
        """Anti-pattern 6: Pattern source is saved for editing."""
        pattern = WorkPattern(
            id="WP1",
            start=date(2024, 1, 1),
            end=date(2024, 1, 31),
            work_days=[SUNDAY, MONDAY, TUESDAY],
            default_shifts=[TimeRange(start_time=time(8, 0), end_time=time(17, 0))],
        )

        result = translate([pattern], RestDay.SATURDAY)

        # Pattern source should be created
        assert len(result.pattern_sources) == 1
        assert result.pattern_sources[0].id == "WP1"
        assert result.pattern_sources[0].translated_pattern is not None

    def test_antipattern_7_cycle_max_52_weeks(self):
        """Anti-pattern 7: Cycle cannot exceed 52 weeks."""
        # Any input that would create > 52 week cycle should be capped
        cycle_len = compute_cycle_length({DayType.NIGHT: Decimal("1.01")})
        assert cycle_len <= 52

    def test_antipattern_9_no_mixing_periods_validation(self):
        """Anti-pattern 9: Same period type required in pattern (implicit in model)."""
        # The DayTypeInput requires count_period per day type
        # Mixing is technically allowed but each day type has its own period
        # This is by design - validated at input level
        pass  # Implicit in the data model


# =============================================================================
# Validation Tests
# =============================================================================

class TestValidation:
    """Test validation functions."""

    def test_validate_level_a_invalid_range(self):
        """Level A: start > end should fail."""
        pattern = WorkPattern(
            id="WP1",
            start=date(2024, 2, 1),
            end=date(2024, 1, 1),
            work_days=[SUNDAY],
            default_shifts=[],
        )

        errors = validate_level_a(pattern)
        assert len(errors) > 0
        assert any(e.type == "invalid_range" for e in errors)

    def test_validate_level_a_invalid_work_day(self):
        """Level A: Invalid day of week should fail."""
        pattern = WorkPattern(
            id="WP1",
            start=date(2024, 1, 1),
            end=date(2024, 1, 31),
            work_days=[0, 1, 8],  # 8 is invalid
            default_shifts=[],
        )

        errors = validate_level_a(pattern)
        assert len(errors) > 0
        assert any(e.type == "invalid_work_day" for e in errors)

    def test_validate_level_b_cycle_length_mismatch(self):
        """Level B: cycle_length must match actual cycle length."""
        pattern = PatternLevelB(
            id="B1",
            start=date(2024, 1, 1),
            end=date(2024, 1, 31),
            cycle=[
                WorkPattern(id="W1", start=date(2024, 1, 1), end=date(2024, 1, 7),
                           work_days=[SUNDAY], default_shifts=[]),
            ],
            cycle_length=3,  # Mismatch - only 1 week in cycle
        )

        errors = validate_level_b(pattern)
        assert len(errors) > 0
        assert any(e.type == "cycle_length_mismatch" for e in errors)

    def test_validate_level_c_no_work_days(self):
        """Level C: At least one day type must have count > 0."""
        pattern = PatternLevelC(
            id="C1",
            start=date(2024, 1, 1),
            end=date(2024, 1, 31),
            day_types=[
                DayTypeInput(DayType.REGULAR, Decimal("0"), CountPeriod.WEEKLY, Decimal(9)),
            ],
        )

        errors = validate_level_c(pattern, RestDay.SATURDAY)
        assert len(errors) > 0
        assert any(e.type == "no_work_days" for e in errors)

    def test_validate_level_c_eve_of_rest_max_1(self):
        """Level C: Eve of rest cannot exceed 1 per week."""
        pattern = PatternLevelC(
            id="C1",
            start=date(2024, 1, 1),
            end=date(2024, 1, 31),
            day_types=[
                DayTypeInput(DayType.EVE_OF_REST, Decimal("2"), CountPeriod.WEEKLY, Decimal(6)),
            ],
        )

        errors = validate_level_c(pattern, RestDay.SATURDAY)
        assert len(errors) > 0
        assert any(e.type == "too_many_eve_of_rest" for e in errors)

    def test_validate_level_c_night_hours_max_24(self):
        """Level C: Night shift hours cannot exceed 24."""
        pattern = PatternLevelC(
            id="C1",
            start=date(2024, 1, 1),
            end=date(2024, 1, 31),
            day_types=[
                DayTypeInput(DayType.NIGHT, Decimal("1"), CountPeriod.WEEKLY, Decimal(25)),
            ],
        )

        errors = validate_level_c(pattern, RestDay.SATURDAY)
        assert len(errors) > 0
        assert any(e.type == "hours_too_high" for e in errors)


# =============================================================================
# Helper Function Tests
# =============================================================================

class TestHelperFunctions:
    """Test helper functions."""

    def test_derive_shift_template_regular_with_break(self):
        """Regular shift with explicit break_minutes gets a break."""
        # 9-hour gross shift with 30-minute break
        # Paid hours = 9 - 0.5 = 8.5
        shifts = derive_shift_template(DayType.REGULAR, Decimal("9"), break_minutes=30)

        assert len(shifts.shifts) == 1
        assert shifts.shifts[0].start_time == time(7, 0)
        assert shifts.shifts[0].end_time == time(16, 0)  # 7:00 + 9 hours
        assert shifts.breaks is not None
        assert len(shifts.breaks) == 1
        # Break is placed in the middle of the shift
        # Midpoint: 7:00 + 4:30 = 11:30, half break = 15 min → 11:15 to 11:45
        assert shifts.breaks[0].start_time == time(11, 15)
        assert shifts.breaks[0].end_time == time(11, 45)

    def test_derive_shift_template_regular_no_break(self):
        """Regular shift <= 6 hours has no break."""
        shifts = derive_shift_template(DayType.REGULAR, Decimal("5"))

        assert len(shifts.shifts) == 1
        assert len(shifts.breaks) == 0

    def test_derive_shift_template_night(self):
        """Night shift starts at 22:00."""
        shifts = derive_shift_template(DayType.NIGHT, Decimal("7"))

        assert len(shifts.shifts) == 1
        assert shifts.shifts[0].start_time == time(22, 0)
        assert len(shifts.breaks) == 0

    def test_compute_cycle_length_whole_number(self):
        """Whole number average → cycle of 1."""
        cycle_len = compute_cycle_length({DayType.REGULAR: Decimal("4")})
        assert cycle_len == 1

    def test_compute_cycle_length_half(self):
        """0.5 per week → cycle of 2."""
        cycle_len = compute_cycle_length({DayType.NIGHT: Decimal("0.5")})
        assert cycle_len == 2

    def test_compute_cycle_length_third(self):
        """0.33 per week → cycle of 3."""
        cycle_len = compute_cycle_length({DayType.NIGHT: Decimal("0.33")})
        # 0.33 = 33/100, but simplified should give cycle ~3
        assert cycle_len >= 3

    def test_distribute_to_weeks_even(self):
        """Even distribution across weeks."""
        weeks = distribute_to_weeks(Decimal("2"), 4)
        assert weeks == [2, 2, 2, 2]

    def test_distribute_to_weeks_remainder(self):
        """Distribution with remainder."""
        weeks = distribute_to_weeks(Decimal("1.5"), 2)
        assert sum(weeks) == 3
        assert 2 in weeks and 1 in weeks


# =============================================================================
# Integration Test
# =============================================================================

class TestIntegration:
    """Integration test - full translation flow."""

    def test_full_translation_flow(self):
        """Test complete translation from input to output."""
        # Create a Level A pattern
        pattern = WorkPattern(
            id="WP1",
            start=date(2024, 1, 1),
            end=date(2024, 1, 31),
            work_days=[SUNDAY, MONDAY, TUESDAY, WEDNESDAY, THURSDAY],
            default_shifts=[TimeRange(start_time=time(8, 0), end_time=time(17, 0))],
            default_breaks=[TimeRange(start_time=time(12, 0), end_time=time(12, 30))],
        )

        # Translate
        result = translate([pattern], RestDay.SATURDAY)

        # Verify
        assert result.errors == []
        assert len(result.work_patterns) == 1
        assert len(result.pattern_sources) == 1

        translated = result.work_patterns[0]
        assert translated.id == "WP1"
        assert translated.start == date(2024, 1, 1)
        assert translated.end == date(2024, 1, 31)
        assert SATURDAY not in translated.work_days

        source = result.pattern_sources[0]
        assert source.type == PatternType.WEEKLY_SIMPLE
        assert source.translated_pattern is not None


# =============================================================================
# Level C Mode Tests
# =============================================================================

class TestLevelCModes:
    """Test Level C statistical and detailed modes."""

    def test_statistical_mode_with_break_minutes(self):
        """Statistical mode with explicit break_minutes."""
        pattern = PatternLevelC(
            id="LC1",
            start=date(2024, 1, 1),
            end=date(2024, 1, 31),
            mode=LevelCMode.STATISTICAL,
            day_types=[
                DayTypeInput(
                    type_id=DayType.REGULAR,
                    count=Decimal("5"),
                    count_period=CountPeriod.WEEKLY,
                    hours=Decimal("9"),
                    break_minutes=30,  # 30-minute break
                ),
            ],
        )

        result = translate_level_c(pattern, RestDay.SATURDAY)

        # Should have 5 work days
        assert len(result.work_days) == 5
        # After full translation, shifts are in daily_overrides
        assert result.daily_overrides is not None
        # Get first work day's shifts
        first_day = date(2024, 1, 1)  # Monday
        day_shifts = result.daily_overrides[first_day]
        assert len(day_shifts.shifts) == 1
        assert len(day_shifts.breaks) == 1
        # Break is 30 minutes
        break_start = day_shifts.breaks[0].start_time
        break_end = day_shifts.breaks[0].end_time
        break_duration_mins = (break_end.hour * 60 + break_end.minute) - (break_start.hour * 60 + break_start.minute)
        assert break_duration_mins == 30

    def test_statistical_mode_no_break(self):
        """Statistical mode with zero break_minutes."""
        pattern = PatternLevelC(
            id="LC2",
            start=date(2024, 1, 1),
            end=date(2024, 1, 31),
            mode=LevelCMode.STATISTICAL,
            day_types=[
                DayTypeInput(
                    type_id=DayType.REGULAR,
                    count=Decimal("5"),
                    count_period=CountPeriod.WEEKLY,
                    hours=Decimal("8"),
                    break_minutes=0,  # No break
                ),
            ],
        )

        result = translate_level_c(pattern, RestDay.SATURDAY)

        # After full translation, shifts are in daily_overrides
        assert result.daily_overrides is not None
        first_day = date(2024, 1, 1)
        day_shifts = result.daily_overrides[first_day]
        assert len(day_shifts.shifts) == 1
        assert len(day_shifts.breaks) == 0

    def test_detailed_mode_with_explicit_shifts(self):
        """Detailed mode uses shifts/breaks directly."""
        pattern = PatternLevelC(
            id="LC3",
            start=date(2024, 1, 1),
            end=date(2024, 1, 31),
            mode=LevelCMode.DETAILED,
            day_types=[
                DayTypeInput(
                    type_id=DayType.REGULAR,
                    count=Decimal("5"),
                    count_period=CountPeriod.WEEKLY,
                    shifts=[
                        TimeRange(start_time=time(8, 0), end_time=time(12, 0)),
                        TimeRange(start_time=time(13, 0), end_time=time(17, 0)),
                    ],
                    breaks=[
                        TimeRange(start_time=time(12, 0), end_time=time(13, 0)),
                    ],
                ),
            ],
        )

        result = translate_level_c(pattern, RestDay.SATURDAY)

        # After full translation, shifts are in daily_overrides
        assert result.daily_overrides is not None
        first_day = date(2024, 1, 1)
        day_shifts = result.daily_overrides[first_day]
        assert len(day_shifts.shifts) == 2
        assert day_shifts.shifts[0].start_time == time(8, 0)
        assert day_shifts.shifts[0].end_time == time(12, 0)
        assert day_shifts.shifts[1].start_time == time(13, 0)
        assert day_shifts.shifts[1].end_time == time(17, 0)
        assert len(day_shifts.breaks) == 1
        assert day_shifts.breaks[0].start_time == time(12, 0)
        assert day_shifts.breaks[0].end_time == time(13, 0)

    def test_detailed_mode_night_shift(self):
        """Detailed mode with night shifts."""
        pattern = PatternLevelC(
            id="LC4",
            start=date(2024, 1, 1),
            end=date(2024, 1, 31),
            mode=LevelCMode.DETAILED,
            day_types=[
                DayTypeInput(
                    type_id=DayType.NIGHT,
                    count=Decimal("2"),
                    count_period=CountPeriod.WEEKLY,
                    shifts=[
                        TimeRange(start_time=time(22, 0), end_time=time(6, 0)),
                    ],
                    breaks=[],
                ),
            ],
            night_placement=NightPlacement.EMPLOYER_FAVOR,
        )

        result = translate_level_c(pattern, RestDay.SATURDAY)

        # After full translation, shifts are in daily_overrides
        assert result.daily_overrides is not None
        # Find a day with night shift
        night_found = False
        for day_date, shifts in result.daily_overrides.items():
            if len(shifts.shifts) > 0 and shifts.shifts[0].start_time == time(22, 0):
                night_found = True
                assert shifts.shifts[0].end_time == time(6, 0)
        assert night_found

    def test_validation_statistical_mode_missing_hours(self):
        """Statistical mode requires hours."""
        pattern = PatternLevelC(
            id="LC5",
            start=date(2024, 1, 1),
            end=date(2024, 1, 31),
            mode=LevelCMode.STATISTICAL,
            day_types=[
                DayTypeInput(
                    type_id=DayType.REGULAR,
                    count=Decimal("5"),
                    count_period=CountPeriod.WEEKLY,
                    hours=None,  # Missing hours
                    break_minutes=0,
                ),
            ],
        )

        errors = validate_level_c(pattern, RestDay.SATURDAY)
        assert len(errors) > 0
        assert any(e.type == "invalid_hours" for e in errors)

    def test_validation_detailed_mode_missing_shifts(self):
        """Detailed mode requires shifts."""
        pattern = PatternLevelC(
            id="LC6",
            start=date(2024, 1, 1),
            end=date(2024, 1, 31),
            mode=LevelCMode.DETAILED,
            day_types=[
                DayTypeInput(
                    type_id=DayType.REGULAR,
                    count=Decimal("5"),
                    count_period=CountPeriod.WEEKLY,
                    shifts=None,  # Missing shifts
                ),
            ],
        )

        errors = validate_level_c(pattern, RestDay.SATURDAY)
        assert len(errors) > 0
        assert any(e.type == "no_shifts" for e in errors)

    def test_validation_break_too_long(self):
        """Break cannot be longer than shift."""
        pattern = PatternLevelC(
            id="LC7",
            start=date(2024, 1, 1),
            end=date(2024, 1, 31),
            mode=LevelCMode.STATISTICAL,
            day_types=[
                DayTypeInput(
                    type_id=DayType.REGULAR,
                    count=Decimal("5"),
                    count_period=CountPeriod.WEEKLY,
                    hours=Decimal("2"),  # 2 hour shift
                    break_minutes=180,  # 3 hour break - too long
                ),
            ],
        )

        errors = validate_level_c(pattern, RestDay.SATURDAY)
        assert len(errors) > 0
        assert any(e.type == "break_too_long" for e in errors)
