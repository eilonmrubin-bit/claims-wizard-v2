"""Pattern Translator module.

Translates user-entered work patterns (Level A/B/C) into concrete
daily records with shift templates. All output is in Level A format.

See docs/skills/pattern-translator/SKILL.md for full specification.
"""

from dataclasses import dataclass, field
from datetime import date, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from fractions import Fraction
from math import gcd, lcm
from typing import Any

from ..ssot import (
    WorkPattern,
    TimeRange,
    DayShifts,
    Duration,
    RestDay,
)
from ..errors import ValidationError


# =============================================================================
# Constants
# =============================================================================

# Week starts on Sunday (0)
SUNDAY = 0
MONDAY = 1
TUESDAY = 2
WEDNESDAY = 3
THURSDAY = 4
FRIDAY = 5
SATURDAY = 6

# Maximum cycle length (weeks)
MAX_CYCLE_LENGTH = 52

# Average weeks per month
WEEKS_PER_MONTH = Decimal("4.33")

# Default shift times
DEFAULT_DAY_START = time(7, 0)
DEFAULT_NIGHT_START = time(22, 0)
DEFAULT_BREAK_START = time(12, 0)
DEFAULT_BREAK_DURATION_MINUTES = 30
MIN_HOURS_FOR_BREAK = 6


# =============================================================================
# Input Types (Level B and C)
# =============================================================================

class PatternType(str, Enum):
    WEEKLY_SIMPLE = "weekly_simple"  # Level A
    CYCLIC = "cyclic"  # Level B
    STATISTICAL = "statistical"  # Level C


class DayType(str, Enum):
    REGULAR = "regular"
    EVE_OF_REST = "eve_of_rest"
    REST_DAY = "rest_day"
    NIGHT = "night"


class NightPlacement(str, Enum):
    EMPLOYER_FAVOR = "employer_favor"
    EMPLOYEE_FAVOR = "employee_favor"
    AVERAGE = "average"


class CountPeriod(str, Enum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class LevelCMode(str, Enum):
    STATISTICAL = "statistical"
    DETAILED = "detailed"


@dataclass
class DayTypeInput:
    """Input for a day type in Level C.

    Statistical mode: hours + break_minutes
    Detailed mode: shifts + breaks (like Level A)
    """
    type_id: DayType
    count: Decimal
    count_period: CountPeriod

    # Statistical mode fields
    hours: Decimal | None = None        # Gross hours (including break)
    break_minutes: int = 0              # Break duration in minutes (0 = no break)
    # Paid hours = hours - (break_minutes / 60)

    # Detailed mode fields
    shifts: list[TimeRange] | None = None
    breaks: list[TimeRange] | None = None
    # Paid hours = total shifts - total breaks


@dataclass
class PatternLevelC:
    """Level C pattern input (averages-based)."""
    id: str
    start: date
    end: date
    day_types: list[DayTypeInput]
    mode: LevelCMode = LevelCMode.STATISTICAL
    night_placement: NightPlacement = NightPlacement.AVERAGE


@dataclass
class PatternLevelB:
    """Cyclic pattern input (Level B)."""
    id: str
    start: date
    end: date
    cycle: list[WorkPattern]  # Each is a Level A pattern for one week
    cycle_length: int = 0

    def __post_init__(self):
        if self.cycle_length == 0:
            self.cycle_length = len(self.cycle)


@dataclass
class PatternSource:
    """Stores original pattern input for editing/display."""
    id: str
    type: PatternType
    start: date
    end: date
    level_a_data: WorkPattern | None = None
    level_b_data: PatternLevelB | None = None
    level_c_data: PatternLevelC | None = None
    translated_pattern: WorkPattern | None = None


@dataclass
class TranslationResult:
    """Result of pattern translation."""
    work_patterns: list[WorkPattern]
    pattern_sources: list[PatternSource]
    errors: list[ValidationError] = field(default_factory=list)


# =============================================================================
# Helper Functions
# =============================================================================

def rest_day_to_int(rest_day: RestDay) -> int:
    """Convert RestDay enum to day of week integer."""
    mapping = {
        RestDay.SUNDAY: SUNDAY,
        RestDay.FRIDAY: FRIDAY,
        RestDay.SATURDAY: SATURDAY,
    }
    return mapping[rest_day]


def eve_of_rest_day(rest_day_int: int) -> int:
    """Get the day before rest day."""
    return (rest_day_int - 1) % 7


def add_time(t: time, hours: Decimal) -> time:
    """Add hours to a time, handling overflow past midnight."""
    total_minutes = t.hour * 60 + t.minute + int(hours * 60)
    total_minutes = total_minutes % (24 * 60)
    return time(total_minutes // 60, total_minutes % 60)


def time_to_decimal_hours(t: time) -> Decimal:
    """Convert time to decimal hours."""
    return Decimal(t.hour) + Decimal(t.minute) / Decimal(60)


def derive_shift_template(type_id: DayType, hours: Decimal, break_minutes: int = 0) -> DayShifts:
    """Derive shift and break times from day type, hours, and break duration.

    Args:
        type_id: Type of day (regular, eve_of_rest, rest_day, night)
        hours: Gross shift duration (including break time)
        break_minutes: Break duration in minutes (0 = no break)

    Returns:
        DayShifts with shift and break templates.
        Paid hours = hours - (break_minutes / 60)
    """
    if type_id == DayType.NIGHT:
        start = DEFAULT_NIGHT_START
    else:
        start = DEFAULT_DAY_START

    # hours is gross (already includes break time)
    end = add_time(start, hours)

    if break_minutes > 0:
        # Place break in the middle of the shift
        break_duration_hours = Decimal(break_minutes) / Decimal(60)
        half_shift = hours / 2
        midpoint = add_time(start, half_shift)

        # Calculate break start (midpoint - half of break)
        half_break_minutes = break_minutes // 2
        break_start_minutes = (midpoint.hour * 60 + midpoint.minute - half_break_minutes) % (24 * 60)
        break_start = time(break_start_minutes // 60, break_start_minutes % 60)
        break_end = add_time(break_start, break_duration_hours)

        return DayShifts(
            shifts=[TimeRange(start_time=start, end_time=end)],
            breaks=[TimeRange(start_time=break_start, end_time=break_end)],
        )
    else:
        return DayShifts(
            shifts=[TimeRange(start_time=start, end_time=end)],
            breaks=[],
        )


def decimal_to_fraction(d: Decimal) -> Fraction:
    """Convert Decimal to Fraction."""
    # Handle simple cases
    if d == d.to_integral_value():
        return Fraction(int(d), 1)

    # Convert to fraction
    sign, digits, exponent = d.as_tuple()
    numerator = int("".join(map(str, digits)))
    if sign:
        numerator = -numerator

    if exponent < 0:
        denominator = 10 ** (-exponent)
    else:
        numerator *= 10 ** exponent
        denominator = 1

    return Fraction(numerator, denominator)


def compute_cycle_length(weekly_counts: dict[DayType, Decimal]) -> int:
    """Compute the shortest cycle length where all fractions become whole numbers."""
    denominators = []

    for count in weekly_counts.values():
        if count > 0:
            frac = decimal_to_fraction(count)
            denominators.append(frac.denominator)

    if not denominators:
        return 1

    # LCM of all denominators
    result = denominators[0]
    for d in denominators[1:]:
        result = lcm(result, d)

    return min(result, MAX_CYCLE_LENGTH)


def distribute_to_weeks(weekly_avg: Decimal, cycle_length: int) -> list[int]:
    """Distribute total count across weeks in the cycle."""
    total = int((weekly_avg * cycle_length).to_integral_value(ROUND_HALF_UP))
    base_per_week = total // cycle_length
    remainder = total - (base_per_week * cycle_length)

    weeks = [base_per_week] * cycle_length

    # Spread remainder evenly
    if remainder > 0:
        step = cycle_length / remainder
        for i in range(remainder):
            idx = int(i * step)
            weeks[idx] += 1

    return weeks


# =============================================================================
# Validation
# =============================================================================

def validate_level_a(pattern: WorkPattern) -> list[ValidationError]:
    """Validate a Level A pattern."""
    errors = []

    if pattern.start > pattern.end:
        errors.append(ValidationError(
            type="invalid_range",
            message="תאריך התחלה חייב להיות לפני תאריך סיום",
            details={"start": str(pattern.start), "end": str(pattern.end)},
        ))

    # Check work_days are valid
    for day in pattern.work_days:
        if day < 0 or day > 6:
            errors.append(ValidationError(
                type="invalid_work_day",
                message=f"יום עבודה לא תקין: {day}",
                details={"day": day},
            ))

    # Check shifts
    for shift in pattern.default_shifts:
        if shift.start_time >= shift.end_time:
            # Allow overnight shifts
            if shift.start_time < time(12, 0):
                errors.append(ValidationError(
                    type="invalid_shift",
                    message="שעת התחלה חייבת להיות לפני שעת סיום",
                    details={"start": str(shift.start_time), "end": str(shift.end_time)},
                ))

    # Check per_day keys are in work_days
    if pattern.per_day:
        for day in pattern.per_day.keys():
            if day not in pattern.work_days:
                errors.append(ValidationError(
                    type="invalid_per_day",
                    message=f"יום {day} מוגדר ב-per_day אבל לא ב-work_days",
                    details={"day": day},
                ))

    return errors


def validate_level_b(pattern: PatternLevelB) -> list[ValidationError]:
    """Validate a Level B pattern."""
    errors = []

    if pattern.cycle_length < 1:
        errors.append(ValidationError(
            type="invalid_cycle_length",
            message="אורך מחזור חייב להיות לפחות 1",
            details={"cycle_length": pattern.cycle_length},
        ))

    if pattern.cycle_length != len(pattern.cycle):
        errors.append(ValidationError(
            type="cycle_length_mismatch",
            message="אורך מחזור לא תואם למספר השבועות",
            details={"cycle_length": pattern.cycle_length, "actual": len(pattern.cycle)},
        ))

    # Validate each week
    for i, week in enumerate(pattern.cycle):
        week_errors = validate_level_a(week)
        for err in week_errors:
            err.details["week_index"] = i
            errors.append(err)

    return errors


def validate_level_c(pattern: PatternLevelC, rest_day: RestDay) -> list[ValidationError]:
    """Validate a Level C pattern."""
    errors = []

    # At least one day type with count > 0
    has_work = any(dt.count > 0 for dt in pattern.day_types)
    if not has_work:
        errors.append(ValidationError(
            type="no_work_days",
            message="חייב להיות לפחות סוג יום אחד עם ספירה > 0",
        ))

    # Calculate weekly totals
    weekly_totals: dict[DayType, Decimal] = {}
    for dt in pattern.day_types:
        if dt.count_period == CountPeriod.MONTHLY:
            weekly = dt.count / WEEKS_PER_MONTH
        else:
            weekly = dt.count
        weekly_totals[dt.type_id] = weekly

    total_days = sum(weekly_totals.values())
    if total_days > 7:
        errors.append(ValidationError(
            type="too_many_days",
            message=f"סה\"כ ימים בשבוע ({total_days}) חורג מ-7",
            details={"total": float(total_days)},
        ))

    # Eve of rest max 1
    eve_count = weekly_totals.get(DayType.EVE_OF_REST, Decimal(0))
    if eve_count > 1:
        errors.append(ValidationError(
            type="too_many_eve_of_rest",
            message="ערב מנוחה יכול להיות לכל היותר פעם אחת בשבוע",
            details={"count": float(eve_count)},
        ))

    # Rest day max 1
    rest_count = weekly_totals.get(DayType.REST_DAY, Decimal(0))
    if rest_count > 1:
        errors.append(ValidationError(
            type="too_many_rest_days",
            message="יום מנוחה יכול להיות לכל היותר פעם אחת בשבוע",
            details={"count": float(rest_count)},
        ))

    # Mode-specific validation
    is_statistical = pattern.mode == LevelCMode.STATISTICAL

    for dt in pattern.day_types:
        if dt.count <= 0:
            continue

        if is_statistical:
            # Statistical mode: validate hours and break_minutes
            if dt.hours is None or dt.hours <= 0:
                errors.append(ValidationError(
                    type="invalid_hours",
                    message=f"שעות חייבות להיות > 0 עבור {dt.type_id.value}",
                    details={"type": dt.type_id.value, "hours": float(dt.hours) if dt.hours else 0},
                ))

            if dt.break_minutes < 0:
                errors.append(ValidationError(
                    type="invalid_break",
                    message=f"אורך הפסקה לא יכול להיות שלילי עבור {dt.type_id.value}",
                    details={"type": dt.type_id.value, "break_minutes": dt.break_minutes},
                ))

            if dt.hours is not None:
                # Hours limit (gross hours)
                if dt.type_id == DayType.NIGHT and dt.hours > 24:
                    errors.append(ValidationError(
                        type="hours_too_high",
                        message="משמרת לילה לא יכולה להיות יותר מ-24 שעות",
                        details={"hours": float(dt.hours)},
                    ))

                if dt.type_id != DayType.NIGHT and dt.hours > 17:
                    errors.append(ValidationError(
                        type="hours_too_high",
                        message="משמרת יום לא יכולה להיות יותר מ-17 שעות",
                        details={"hours": float(dt.hours)},
                    ))

                # Break cannot exceed shift duration
                break_hours = Decimal(dt.break_minutes) / Decimal(60)
                if break_hours >= dt.hours:
                    errors.append(ValidationError(
                        type="break_too_long",
                        message=f"הפסקה ({dt.break_minutes} דקות) לא יכולה להיות ארוכה מהמשמרת ({dt.hours} שעות)",
                        details={"break_minutes": dt.break_minutes, "hours": float(dt.hours)},
                    ))
        else:
            # Detailed mode: validate shifts and breaks
            if not dt.shifts or len(dt.shifts) == 0:
                errors.append(ValidationError(
                    type="no_shifts",
                    message=f"חייב להיות לפחות משמרת אחת עבור {dt.type_id.value}",
                    details={"type": dt.type_id.value},
                ))

            # Calculate net hours
            if dt.shifts:
                total_shift_minutes = sum(
                    (s.end_time.hour * 60 + s.end_time.minute) - (s.start_time.hour * 60 + s.start_time.minute)
                    for s in dt.shifts
                )
                total_break_minutes = sum(
                    (b.end_time.hour * 60 + b.end_time.minute) - (b.start_time.hour * 60 + b.start_time.minute)
                    for b in (dt.breaks or [])
                )
                net_hours = Decimal(total_shift_minutes - total_break_minutes) / Decimal(60)

                if dt.type_id == DayType.NIGHT and net_hours > 24:
                    errors.append(ValidationError(
                        type="hours_too_high",
                        message="משמרת לילה לא יכולה להיות יותר מ-24 שעות נטו",
                        details={"net_hours": float(net_hours)},
                    ))

                if dt.type_id != DayType.NIGHT and net_hours > 17:
                    errors.append(ValidationError(
                        type="hours_too_high",
                        message="משמרת יום לא יכולה להיות יותר מ-17 שעות נטו",
                        details={"net_hours": float(net_hours)},
                    ))

    # Check cycle length
    cycle_len = compute_cycle_length(weekly_totals)
    if cycle_len > MAX_CYCLE_LENGTH:
        errors.append(ValidationError(
            type="cycle_too_long",
            message=f"אורך מחזור ({cycle_len}) חורג מהמקסימום ({MAX_CYCLE_LENGTH})",
            details={"cycle_length": cycle_len, "max": MAX_CYCLE_LENGTH},
        ))

    return errors


# =============================================================================
# Translation Functions
# =============================================================================

def translate_level_a(pattern: WorkPattern, rest_day: RestDay) -> WorkPattern:
    """Translate Level A pattern (identity - just validate and return)."""
    # Level A is already in the target format
    # Just ensure rest_day is not in work_days
    rest_day_int = rest_day_to_int(rest_day)
    work_days = [d for d in pattern.work_days if d != rest_day_int]

    return WorkPattern(
        id=pattern.id,
        start=pattern.start,
        end=pattern.end,
        duration=pattern.duration,
        work_days=work_days,
        default_shifts=pattern.default_shifts,
        default_breaks=pattern.default_breaks,
        per_day=pattern.per_day,
        daily_overrides=pattern.daily_overrides,
    )


def translate_level_b(pattern: PatternLevelB, rest_day: RestDay) -> WorkPattern:
    """Translate Level B (cyclic) pattern to Level A with daily_overrides."""
    rest_day_int = rest_day_to_int(rest_day)

    # Collect all work days across the cycle
    all_work_days = set()
    for week_pattern in pattern.cycle:
        for d in week_pattern.work_days:
            if d != rest_day_int:
                all_work_days.add(d)

    # Use first week's defaults
    first_week = pattern.cycle[0] if pattern.cycle else None
    default_shifts = first_week.default_shifts if first_week else []
    default_breaks = first_week.default_breaks if first_week else []

    # Build daily_overrides for the entire period
    daily_overrides: dict[date, DayShifts] = {}

    current = pattern.start
    weeks_since_start = 0

    # Find the Sunday of the week containing pattern.start
    days_since_sunday = current.weekday()  # Python: Monday=0, Sunday=6
    # Convert to our system: Sunday=0
    days_since_sunday = (current.weekday() + 1) % 7

    while current <= pattern.end:
        # Calculate which week in the cycle
        # Count full weeks since start
        days_from_start = (current - pattern.start).days
        week_number = days_from_start // 7
        cycle_index = week_number % pattern.cycle_length

        week_pattern = pattern.cycle[cycle_index]

        # Get day of week (0=Sunday)
        dow = (current.weekday() + 1) % 7

        if dow != rest_day_int and dow in week_pattern.work_days:
            # Determine shifts for this day
            if week_pattern.daily_overrides and current in week_pattern.daily_overrides:
                shifts_data = week_pattern.daily_overrides[current]
            elif week_pattern.per_day and dow in week_pattern.per_day:
                shifts_data = week_pattern.per_day[dow]
            else:
                shifts_data = DayShifts(
                    shifts=list(week_pattern.default_shifts),
                    breaks=list(week_pattern.default_breaks) if week_pattern.default_breaks else None,
                )

            daily_overrides[current] = shifts_data

        current += timedelta(days=1)

    return WorkPattern(
        id=pattern.id,
        start=pattern.start,
        end=pattern.end,
        duration=Duration(),
        work_days=sorted(all_work_days),
        default_shifts=default_shifts,
        default_breaks=default_breaks,
        per_day=None,
        daily_overrides=daily_overrides if daily_overrides else None,
    )


def translate_level_c(pattern: PatternLevelC, rest_day: RestDay) -> WorkPattern:
    """Translate Level C pattern to Level A.

    Supports both statistical and detailed modes.
    """
    rest_day_int = rest_day_to_int(rest_day)
    eve_day_int = eve_of_rest_day(rest_day_int)
    is_detailed = pattern.mode == LevelCMode.DETAILED

    # Step 1: Normalize to weekly and collect type info
    weekly_counts: dict[DayType, Decimal] = {}
    hours_by_type: dict[DayType, Decimal] = {}
    break_minutes_by_type: dict[DayType, int] = {}
    shifts_by_type: dict[DayType, list[TimeRange]] = {}
    breaks_by_type: dict[DayType, list[TimeRange]] = {}

    for dt in pattern.day_types:
        if dt.count_period == CountPeriod.MONTHLY:
            weekly = dt.count / WEEKS_PER_MONTH
        else:
            weekly = dt.count
        weekly_counts[dt.type_id] = weekly

        if is_detailed:
            # Detailed mode: store shifts and breaks directly
            shifts_by_type[dt.type_id] = dt.shifts or []
            breaks_by_type[dt.type_id] = dt.breaks or []
        else:
            # Statistical mode: store hours and break_minutes
            hours_by_type[dt.type_id] = dt.hours
            break_minutes_by_type[dt.type_id] = dt.break_minutes

    # Helper to get DayShifts for a type (handles both modes)
    def get_day_shifts(day_type: DayType) -> DayShifts:
        if is_detailed:
            # Detailed mode: use shifts/breaks directly
            return DayShifts(
                shifts=shifts_by_type.get(day_type, []),
                breaks=breaks_by_type.get(day_type, []),
            )
        else:
            # Statistical mode: derive from hours + break_minutes
            default_hours = {
                DayType.REGULAR: Decimal(9),
                DayType.EVE_OF_REST: Decimal(6),
                DayType.REST_DAY: Decimal(8),
                DayType.NIGHT: Decimal(7),
            }
            hours = hours_by_type.get(day_type, default_hours[day_type])
            break_mins = break_minutes_by_type.get(day_type, 0)
            return derive_shift_template(day_type, hours, break_mins)

    # Step 2: Compute cycle length
    cycle_length = compute_cycle_length(weekly_counts)

    # Step 3: Distribute to weeks
    distributions: dict[DayType, list[int]] = {}
    for day_type, weekly_avg in weekly_counts.items():
        if weekly_avg > 0:
            distributions[day_type] = distribute_to_weeks(weekly_avg, cycle_length)
        else:
            distributions[day_type] = [0] * cycle_length

    # Step 4 & 5: Build each week in the cycle
    cycle: list[WorkPattern] = []

    for week_idx in range(cycle_length):
        # Get counts for this week
        regular_count = distributions.get(DayType.REGULAR, [0] * cycle_length)[week_idx]
        eve_count = distributions.get(DayType.EVE_OF_REST, [0] * cycle_length)[week_idx]
        rest_count = distributions.get(DayType.REST_DAY, [0] * cycle_length)[week_idx]
        night_count = distributions.get(DayType.NIGHT, [0] * cycle_length)[week_idx]

        work_days: list[int] = []
        per_day: dict[int, DayShifts] = {}

        # Step 4a: Rest day shifts
        if rest_count > 0:
            work_days.append(rest_day_int)
            per_day[rest_day_int] = get_day_shifts(DayType.REST_DAY)

        # Step 4b: Eve of rest shifts
        if eve_count > 0:
            work_days.append(eve_day_int)
            per_day[eve_day_int] = get_day_shifts(DayType.EVE_OF_REST)

        # Step 4c: Regular shifts (Sunday to Thursday, fill from start)
        regular_days = [SUNDAY, MONDAY, TUESDAY, WEDNESDAY, THURSDAY]
        # Remove rest day and eve if they're in this range
        regular_days = [d for d in regular_days if d != rest_day_int and d != eve_day_int]

        placed_regular = 0
        for dow in regular_days:
            if placed_regular >= regular_count:
                break
            work_days.append(dow)
            per_day[dow] = get_day_shifts(DayType.REGULAR)
            placed_regular += 1

        # Step 5: Night shifts
        if night_count > 0:
            night_shifts = get_day_shifts(DayType.NIGHT)

            # Available nights (night before each day)
            # Night shift 22:00-05:00 is assigned to the NEXT day (majority of hours)
            available_nights: list[int] = []

            for dow in range(7):
                next_day = (dow + 1) % 7
                # Check if we can place night here
                # Cannot place if next_day is rest_day and no work on rest_day
                if next_day == rest_day_int and rest_count == 0:
                    continue
                available_nights.append(dow)

            # Place nights based on placement mode
            if pattern.night_placement == NightPlacement.EMPLOYER_FAVOR:
                # Prefer nights before days that already have work
                scored = []
                for night_dow in available_nights:
                    next_day = (night_dow + 1) % 7
                    has_day_shift = next_day in work_days
                    score = 1 if has_day_shift else 0
                    scored.append((night_dow, score))
                scored.sort(key=lambda x: -x[1])
                selected = [n[0] for n in scored[:night_count]]

            elif pattern.night_placement == NightPlacement.EMPLOYEE_FAVOR:
                # Prefer nights before days without work
                scored = []
                for night_dow in available_nights:
                    next_day = (night_dow + 1) % 7
                    has_day_shift = next_day in work_days
                    score = 0 if has_day_shift else 1
                    scored.append((night_dow, score))
                scored.sort(key=lambda x: -x[1])
                selected = [n[0] for n in scored[:night_count]]

            else:  # AVERAGE
                # Half employer, half employee
                employer_count = night_count // 2
                employee_count = night_count - employer_count

                # Employer favor
                scored_emp = []
                for night_dow in available_nights:
                    next_day = (night_dow + 1) % 7
                    has_day_shift = next_day in work_days
                    scored_emp.append((night_dow, 1 if has_day_shift else 0))
                scored_emp.sort(key=lambda x: -x[1])

                selected = [n[0] for n in scored_emp[:employer_count]]

                # Employee favor from remaining
                remaining = [n for n in available_nights if n not in selected]
                scored_ee = []
                for night_dow in remaining:
                    next_day = (night_dow + 1) % 7
                    has_day_shift = next_day in work_days
                    scored_ee.append((night_dow, 0 if has_day_shift else 1))
                scored_ee.sort(key=lambda x: -x[1])

                selected.extend([n[0] for n in scored_ee[:employee_count]])

            # Add night shifts to per_day
            # Night shift on dow means the shift starts on that night (22:00)
            # but is assigned to the NEXT day for work day counting
            for night_dow in selected:
                # The night shift belongs to the night of night_dow
                # Store in per_day for the day the shift STARTS on
                if night_dow not in work_days:
                    work_days.append(night_dow)
                # Merge or replace shift
                if night_dow in per_day:
                    # Day already has a shift, add night shift
                    existing = per_day[night_dow]
                    existing.shifts.extend(night_shifts.shifts)
                else:
                    per_day[night_dow] = night_shifts

        # Create week pattern
        week_pattern = WorkPattern(
            id=f"{pattern.id}_week_{week_idx}",
            start=pattern.start,
            end=pattern.end,
            duration=Duration(),
            work_days=sorted(set(work_days)),
            default_shifts=[],
            default_breaks=[],
            per_day=per_day if per_day else None,
            daily_overrides=None,
        )
        cycle.append(week_pattern)

    # Convert to Level B, then to Level A
    level_b = PatternLevelB(
        id=pattern.id,
        start=pattern.start,
        end=pattern.end,
        cycle=cycle,
        cycle_length=cycle_length,
    )

    return translate_level_b(level_b, rest_day)


# =============================================================================
# Main Translation Function
# =============================================================================

def translate(
    work_patterns: list[WorkPattern],
    rest_day: RestDay,
    pattern_sources: list[PatternSource] | None = None,
) -> TranslationResult:
    """Translate all work patterns to Level A format.

    Args:
        work_patterns: List of work patterns (Level A format in SSOT)
        rest_day: The rest day (Saturday/Friday/Sunday)
        pattern_sources: Optional list of pattern sources for Level B/C patterns

    Returns:
        TranslationResult with translated patterns and any errors
    """
    result_patterns: list[WorkPattern] = []
    result_sources: list[PatternSource] = []
    errors: list[ValidationError] = []

    # Build lookup for pattern sources
    source_lookup: dict[str, PatternSource] = {}
    if pattern_sources:
        for source in pattern_sources:
            source_lookup[source.id] = source

    for pattern in work_patterns:
        source = source_lookup.get(pattern.id)

        if source and source.type == PatternType.STATISTICAL and source.level_c_data:
            # Level C translation
            validation_errors = validate_level_c(source.level_c_data, rest_day)
            if validation_errors:
                errors.extend(validation_errors)
                continue

            translated = translate_level_c(source.level_c_data, rest_day)
            result_patterns.append(translated)

            source.translated_pattern = translated
            result_sources.append(source)

        elif source and source.type == PatternType.CYCLIC and source.level_b_data:
            # Level B translation
            validation_errors = validate_level_b(source.level_b_data)
            if validation_errors:
                errors.extend(validation_errors)
                continue

            translated = translate_level_b(source.level_b_data, rest_day)
            result_patterns.append(translated)

            source.translated_pattern = translated
            result_sources.append(source)

        else:
            # Level A (or no source = treat as Level A)
            validation_errors = validate_level_a(pattern)
            if validation_errors:
                errors.extend(validation_errors)
                continue

            translated = translate_level_a(pattern, rest_day)
            result_patterns.append(translated)

            # Create source record
            new_source = PatternSource(
                id=pattern.id,
                type=PatternType.WEEKLY_SIMPLE,
                start=pattern.start,
                end=pattern.end,
                level_a_data=pattern,
                translated_pattern=translated,
            )
            result_sources.append(new_source)

    return TranslationResult(
        work_patterns=result_patterns,
        pattern_sources=result_sources,
        errors=errors,
    )
