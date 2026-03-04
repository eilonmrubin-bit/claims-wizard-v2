"""Annual vacation (חופשה שנתית) calculation module.

See docs/skills/vacation/SKILL.md for full specification.

Key concepts:
- Calendar year based (not employment year)
- Seniority basis differs by industry (employer vs industry)
- Week type affects base days (5-day vs 6-day)
- Partial years are prorated by actual work days
- Construction has special age-55 rules
"""

from datetime import date
from decimal import Decimal
from typing import Callable

from ..ssot import (
    VacationResult,
    VacationYearData,
    VacationWeekTypeSegment,
    EmploymentPeriod,
    WorkPattern,
    PeriodMonthRecord,
    SeniorityTotals,
)


# =============================================================================
# Entitlement Tables (from SKILL.md)
# =============================================================================

# Format: (min_seniority_years, max_seniority_years_inclusive, days_6day, days_5day)
VACATION_DAYS_TABLES: dict[str, list[tuple[int, int, int, int]]] = {
    "general": [
        (1, 5, 14, 12), (6, 6, 16, 14), (7, 7, 18, 15),
        (8, 8, 19, 16), (9, 9, 20, 17), (10, 10, 21, 18),
        (11, 11, 22, 19), (12, 12, 23, 20), (13, 999, 24, 20),
    ],
    "construction": [
        (1, 2, 12, 10), (3, 3, 13, 11), (4, 4, 16, 14),
        (5, 5, 18, 15), (6, 7, 19, 17), (8, 8, 19, 17),
        (9, 999, 26, 23),
    ],
    "construction_55plus": [
        # Replaces "construction" rows for seniority >= 11 when worker is age 55+
        (11, 999, 28, 24),
    ],
    "agriculture": [
        (1, 3, 12, 12), (4, 6, 16, 16), (7, 9, 20, 20),
        (10, 10, 24, 24), (11, 999, 26, 26),
    ],
    "cleaning": [
        (1, 2, 12, 10), (3, 4, 13, 11), (5, 5, 15, 13),
        (6, 6, 20, 18), (7, 8, 21, 19), (9, 999, 26, 23),
    ],
}

# Hebrew month names for partial_description
HEBREW_MONTHS = [
    "", "ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני",
    "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר"
]


def _lookup_base_days(
    industry: str,
    seniority_years: int,
    week_type: str,
    is_55_plus: bool = False,
) -> int:
    """Look up base vacation days from the tables.

    Args:
        industry: general | construction | agriculture | cleaning
        seniority_years: Years of seniority (1-based)
        week_type: "five_day" | "six_day"
        is_55_plus: For construction, whether worker is 55+ and seniority >= 11
    """
    # Determine which table to use
    if industry == "construction" and is_55_plus and seniority_years >= 11:
        table = VACATION_DAYS_TABLES.get("construction_55plus", [])
    else:
        table = VACATION_DAYS_TABLES.get(industry, VACATION_DAYS_TABLES["general"])

    for min_y, max_y, days_6, days_5 in table:
        if min_y <= seniority_years <= max_y:
            return days_6 if week_type == "six_day" else days_5

    # Fallback to last row
    if table:
        _, _, days_6, days_5 = table[-1]
        return days_6 if week_type == "six_day" else days_5

    return 12  # Default fallback


def _is_six_day_week(work_days: list[int]) -> bool:
    """Check if work pattern is 6-day (includes Friday, index 5)."""
    return 5 in work_days


def _get_week_type(work_days: list[int]) -> str:
    """Determine week type from work_days list."""
    return "six_day" if _is_six_day_week(work_days) else "five_day"


def _count_iso_weeks_in_range(start: date, end: date) -> int:
    """Count ISO weeks that fall within a date range."""
    if start > end:
        return 0

    # Count unique ISO week numbers
    weeks = set()
    current = start
    while current <= end:
        weeks.add((current.isocalendar()[0], current.isocalendar()[1]))
        current = date(current.year, current.month, current.day + 1) if current.day < 28 else _add_days(current, 1)

    return len(weeks)


def _add_days(d: date, days: int) -> date:
    """Add days to a date, handling month/year boundaries."""
    from datetime import timedelta
    return d + timedelta(days=days)


def _get_pattern_for_date(
    d: date,
    work_patterns: list[WorkPattern],
) -> WorkPattern | None:
    """Find the work pattern active on a given date."""
    for wp in work_patterns:
        if wp.start and wp.end and wp.start <= d <= wp.end:
            return wp
    return None


def _compute_week_type_segments(
    year: int,
    year_start: date,
    year_end: date,
    work_patterns: list[WorkPattern],
    industry: str,
    seniority_years: int,
    is_55_plus: bool,
) -> list[VacationWeekTypeSegment]:
    """Compute week type segments for a calendar year."""
    segments: list[VacationWeekTypeSegment] = []

    if not work_patterns:
        return segments

    # Find all pattern boundaries within the year
    boundaries = [year_start]
    for wp in work_patterns:
        if wp.start and year_start < wp.start <= year_end:
            boundaries.append(wp.start)
        if wp.end and year_start <= wp.end < year_end:
            boundaries.append(_add_days(wp.end, 1))
    boundaries.append(_add_days(year_end, 1))

    # Sort and remove duplicates
    boundaries = sorted(set(boundaries))

    # Build segments
    total_weeks = Decimal("0")
    segment_list = []

    for i in range(len(boundaries) - 1):
        seg_start = boundaries[i]
        seg_end = _add_days(boundaries[i + 1], -1)

        if seg_start > year_end:
            break
        if seg_end > year_end:
            seg_end = year_end
        if seg_start < year_start:
            seg_start = year_start

        pattern = _get_pattern_for_date(seg_start, work_patterns)
        if not pattern:
            continue

        week_type = _get_week_type(pattern.work_days)
        weeks = Decimal(str(_count_iso_weeks_in_range(seg_start, seg_end)))

        segment_list.append({
            "start": seg_start,
            "end": seg_end,
            "week_type": week_type,
            "weeks": weeks,
        })
        total_weeks += weeks

    # Compute weights and build segments
    for seg in segment_list:
        weight = seg["weeks"] / total_weeks if total_weeks > 0 else Decimal("0")
        base_days = _lookup_base_days(industry, seniority_years, seg["week_type"], is_55_plus)

        segments.append(VacationWeekTypeSegment(
            segment_start=seg["start"],
            segment_end=seg["end"],
            week_type=seg["week_type"],
            weeks_count=seg["weeks"],
            weight=weight,
            base_days=base_days,
            weighted_days=weight * Decimal(str(base_days)),
        ))

    return segments


def _compute_partial_description(year: int, year_start: date, year_end: date) -> str:
    """Generate Hebrew description for partial year."""
    jan1 = date(year, 1, 1)
    dec31 = date(year, 12, 31)

    start_month = year_start.month
    end_month = year_end.month

    if year_start == jan1 and year_end == dec31:
        return ""  # Full year

    months_count = end_month - start_month + 1
    start_name = HEBREW_MONTHS[start_month]
    end_name = HEBREW_MONTHS[end_month]

    if start_month == end_month:
        return f"חודש {start_name}"
    else:
        return f"{months_count} חודשים ({start_name}–{end_name})"


def _count_work_days_in_year(
    year: int,
    year_start: date,
    year_end: date,
    work_patterns: list[WorkPattern],
) -> tuple[int, int]:
    """Count actual work days and theoretical full-year work days.

    Returns:
        (actual_work_days, full_year_work_days)
    """
    actual_days = 0
    full_year_days = 0

    jan1 = date(year, 1, 1)
    dec31 = date(year, 12, 31)

    current = jan1
    while current <= dec31:
        pattern = _get_pattern_for_date(current, work_patterns)
        if pattern and current.weekday() in pattern.work_days:
            full_year_days += 1
            if year_start <= current <= year_end:
                actual_days += 1
        current = _add_days(current, 1)

    return actual_days, full_year_days


def _compute_avg_daily_salary(
    year: int,
    year_start: date,
    year_end: date,
    period_month_records: list[PeriodMonthRecord],
) -> Decimal:
    """Compute weighted average daily salary for a calendar year."""
    total_weighted = Decimal("0")
    total_days = Decimal("0")

    for pmr in period_month_records:
        pmr_year, pmr_month = pmr.month
        if pmr_year != year:
            continue

        # Check if this month overlaps with our year range
        month_start = date(pmr_year, pmr_month, 1)
        if pmr_month == 12:
            month_end = date(pmr_year, 12, 31)
        else:
            month_end = date(pmr_year, pmr_month + 1, 1)
            month_end = _add_days(month_end, -1)

        if month_end < year_start or month_start > year_end:
            continue

        # Use work_days_count as the weight
        work_days = Decimal(str(pmr.work_days_count)) if pmr.work_days_count else Decimal("1")
        daily_salary = pmr.salary_daily if pmr.salary_daily else Decimal("0")

        total_weighted += daily_salary * work_days
        total_days += work_days

    if total_days > 0:
        return total_weighted / total_days
    return Decimal("0")


def compute_vacation(
    employment_periods: list[EmploymentPeriod],
    work_patterns: list[WorkPattern],
    period_month_records: list[PeriodMonthRecord],
    industry: str,
    seniority_totals: SeniorityTotals,
    birth_year: int | None = None,
    right_toggles: dict | None = None,
) -> VacationResult:
    """Compute annual vacation entitlement.

    See docs/skills/vacation/SKILL.md for full specification.
    """
    # Check if vacation is enabled
    if right_toggles and right_toggles.get("vacation", {}).get("enabled") is False:
        return VacationResult(entitled=False)

    # Determine seniority basis
    uses_industry_seniority = industry in ("construction", "cleaning")
    seniority_basis = "industry" if uses_industry_seniority else "employer"

    # Find employment date range
    if not employment_periods:
        return VacationResult(entitled=False)

    emp_start = min(ep.start for ep in employment_periods if ep.start)
    emp_end = max(ep.end for ep in employment_periods if ep.end)

    if not emp_start or not emp_end:
        return VacationResult(entitled=False)

    # Get prior seniority for industry-based calculation
    prior_months = seniority_totals.prior_seniority_months if seniority_totals else 0

    # Compute years
    years: list[VacationYearData] = []
    grand_total_days = Decimal("0")
    grand_total_value = Decimal("0")

    # Track months worked at this employer (for employer-based seniority)
    employer_months_before_year = 0

    for year in range(emp_start.year, emp_end.year + 1):
        jan1 = date(year, 1, 1)
        dec31 = date(year, 12, 31)

        # Determine effective year boundaries
        year_start = max(jan1, emp_start)
        year_end = min(dec31, emp_end)

        if year_start > year_end:
            continue

        # Check if partial year
        is_partial = year_start != jan1 or year_end != dec31

        # Compute seniority at start of year
        if uses_industry_seniority:
            # Industry seniority: prior + months worked at defendant before this year
            seniority_months = prior_months + employer_months_before_year
        else:
            # Employer seniority: just months worked at defendant before this year
            seniority_months = employer_months_before_year

        seniority_years = (seniority_months // 12) + 1

        # Construction: check age 55
        age_at_year_start = None
        age_55_split = False
        is_55_plus = False

        if industry == "construction" and birth_year:
            age_at_year_start = year - birth_year
            age_55_date = date(birth_year + 55, 1, 1)

            if age_55_date <= jan1:
                # Already 55+ at start of year
                is_55_plus = True
            elif jan1 < age_55_date <= dec31:
                # Turns 55 during this year
                age_55_split = True
                # For simplicity, if turning 55 on Jan 1, use 55+ for full year
                if age_55_date == jan1:
                    is_55_plus = True
                    age_55_split = False

        # Compute week type segments
        week_type_segments = _compute_week_type_segments(
            year, year_start, year_end, work_patterns,
            industry, seniority_years, is_55_plus,
        )

        # Compute weighted base days
        weighted_base_days = sum(
            seg.weighted_days for seg in week_type_segments
        )

        # Handle age 55 split for construction
        if age_55_split and birth_year:
            age_55_date = date(birth_year + 55, 1, 1)
            days_before = (age_55_date - year_start).days
            days_after = (year_end - age_55_date).days + 1
            total_days = days_before + days_after

            if total_days > 0:
                # Recompute with split
                # Under 55 portion
                segments_under = _compute_week_type_segments(
                    year, year_start, _add_days(age_55_date, -1), work_patterns,
                    industry, seniority_years, False,
                )
                weighted_under = sum(seg.weighted_days for seg in segments_under)

                # 55+ portion
                segments_over = _compute_week_type_segments(
                    year, age_55_date, year_end, work_patterns,
                    industry, seniority_years, True,
                )
                weighted_over = sum(seg.weighted_days for seg in segments_over)

                weight_before = Decimal(str(days_before)) / Decimal(str(total_days))
                weight_after = Decimal(str(days_after)) / Decimal(str(total_days))

                weighted_base_days = weight_before * weighted_under + weight_after * weighted_over

        # Compute partial fraction
        actual_days, full_year_days = _count_work_days_in_year(
            year, year_start, year_end, work_patterns
        )

        if full_year_days > 0:
            partial_fraction = Decimal(str(actual_days)) / Decimal(str(full_year_days))
        else:
            partial_fraction = Decimal("1")

        if not is_partial:
            partial_fraction = None  # None means full year

        # Compute entitled days
        entitled_days = weighted_base_days * (partial_fraction if partial_fraction else Decimal("1"))

        # Compute average daily salary
        avg_daily_salary = _compute_avg_daily_salary(
            year, year_start, year_end, period_month_records
        )

        # Compute year value
        year_value = entitled_days * avg_daily_salary

        # Build year data
        year_data = VacationYearData(
            year=year,
            year_start=year_start,
            year_end=year_end,
            is_partial=is_partial,
            partial_fraction=partial_fraction,
            partial_description=_compute_partial_description(year, year_start, year_end) if is_partial else "",
            seniority_years=seniority_years,
            age_at_year_start=age_at_year_start,
            age_55_split=age_55_split,
            week_type_segments=week_type_segments,
            weighted_base_days=weighted_base_days,
            entitled_days=entitled_days,
            avg_daily_salary=avg_daily_salary,
            year_value=year_value,
        )

        years.append(year_data)
        grand_total_days += entitled_days
        grand_total_value += year_value

        # Update employer months for next year
        # Count months worked in this year at defendant
        months_in_year = 0
        for pmr in period_month_records:
            if pmr.month[0] == year:
                months_in_year += 1
        employer_months_before_year += months_in_year

    return VacationResult(
        entitled=True,
        industry=industry,
        seniority_basis=seniority_basis,
        years=years,
        grand_total_days=grand_total_days,
        grand_total_value=grand_total_value,
    )
