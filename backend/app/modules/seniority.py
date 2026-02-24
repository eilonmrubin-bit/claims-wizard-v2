"""Seniority (ותק ענפי) calculation module.

Computes industry seniority and seniority at defendant from input data.
See docs/skills/seniority/SKILL.md for complete documentation.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Callable

from app.ssot import (
    SeniorityMethod,
    SeniorityMonthly,
    SeniorityTotals,
    MatashRecord,
)


@dataclass
class SeniorityResult:
    """Result of seniority computation."""
    totals: SeniorityTotals
    monthly: list[SeniorityMonthly]


def _months_to_years(months: int) -> Decimal:
    """Convert months to years as decimal."""
    return Decimal(months) / Decimal(12)


def _generate_month_range(start: date, end: date) -> list[tuple[int, int]]:
    """Generate list of (year, month) tuples from start to end inclusive."""
    months = []
    current_year = start.year
    current_month = start.month

    end_year = end.year
    end_month = end.month

    while (current_year, current_month) <= (end_year, end_month):
        months.append((current_year, current_month))
        current_month += 1
        if current_month > 12:
            current_month = 1
            current_year += 1

    return months


def _count_work_months_from_periods(
    periods: list[tuple[date, date]]
) -> set[tuple[int, int]]:
    """Count work months from list of (start, end) date tuples.

    Returns set of (year, month) tuples representing all months
    with at least one day of work.
    """
    month_set: set[tuple[int, int]] = set()

    for start, end in periods:
        for year, month in _generate_month_range(start, end):
            month_set.add((year, month))

    return month_set


def _count_work_months_from_pattern(
    employment_start: date,
    employment_end: date,
    did_work_in_month: Callable[[int, int], bool],
) -> set[tuple[int, int]]:
    """Count work months using a function that checks if work occurred.

    Args:
        employment_start: First day of employment
        employment_end: Last day of employment
        did_work_in_month: Function (year, month) -> bool indicating if any work occurred

    Returns set of (year, month) tuples for months with work.
    """
    month_set: set[tuple[int, int]] = set()

    for year, month in _generate_month_range(employment_start, employment_end):
        if did_work_in_month(year, month):
            month_set.add((year, month))

    return month_set


def _generate_monthly_series(
    employment_start: date,
    employment_end: date,
    work_month_set: set[tuple[int, int]],
    prior_months: int,
) -> list[SeniorityMonthly]:
    """Generate cumulative monthly series for SSOT.

    Args:
        employment_start: First day of employment at defendant
        employment_end: Last day of employment at defendant
        work_month_set: Set of (year, month) tuples representing worked months
        prior_months: Prior industry seniority in months

    Returns list of SeniorityMonthly records covering full employment range.
    """
    series = []
    defendant_cumulative = 0

    for year, month in _generate_month_range(employment_start, employment_end):
        worked = (year, month) in work_month_set

        if worked:
            defendant_cumulative += 1

        industry_cumulative = prior_months + defendant_cumulative

        series.append(SeniorityMonthly(
            month=(year, month),
            worked=worked,
            at_defendant_cumulative=defendant_cumulative,
            at_defendant_years_cumulative=_months_to_years(defendant_cumulative),
            total_industry_cumulative=industry_cumulative,
            total_industry_years_cumulative=_months_to_years(industry_cumulative),
        ))

    return series


def compute_seniority_method_a(
    prior_months: int,
    employment_start: date,
    employment_end: date,
    did_work_in_month: Callable[[int, int], bool],
) -> SeniorityResult:
    """Compute seniority using Method א: prior seniority + work pattern.

    Args:
        prior_months: Prior industry seniority in months
        employment_start: First day of employment at defendant
        employment_end: Last day of employment at defendant
        did_work_in_month: Function (year, month) -> bool indicating if work occurred

    Returns SeniorityResult with totals and monthly series.
    """
    work_month_set = _count_work_months_from_pattern(
        employment_start, employment_end, did_work_in_month
    )

    at_defendant_months = len(work_month_set)
    total_industry_months = prior_months + at_defendant_months

    monthly = _generate_monthly_series(
        employment_start, employment_end, work_month_set, prior_months
    )

    totals = SeniorityTotals(
        input_method=SeniorityMethod.PRIOR_PLUS_PATTERN,
        prior_seniority_months=prior_months,
        at_defendant_months=at_defendant_months,
        at_defendant_years=_months_to_years(at_defendant_months),
        total_industry_months=total_industry_months,
        total_industry_years=_months_to_years(total_industry_months),
    )

    return SeniorityResult(totals=totals, monthly=monthly)


def compute_seniority_method_b(
    total_industry_months: int,
    at_defendant_months: int,
    employment_start: date | None = None,
    employment_end: date | None = None,
) -> SeniorityResult:
    """Compute seniority using Method ב: manual entry.

    Args:
        total_industry_months: Total industry seniority in months
        at_defendant_months: Seniority at defendant in months
        employment_start: Optional start date for series generation
        employment_end: Optional end date for series generation

    Returns SeniorityResult with totals and optional monthly series.
    """
    prior_months = total_industry_months - at_defendant_months

    totals = SeniorityTotals(
        input_method=SeniorityMethod.MANUAL,
        prior_seniority_months=prior_months,
        at_defendant_months=at_defendant_months,
        at_defendant_years=_months_to_years(at_defendant_months),
        total_industry_months=total_industry_months,
        total_industry_years=_months_to_years(total_industry_months),
    )

    monthly = []
    if employment_start and employment_end:
        # Generate series with all months marked as worked
        all_months = set(_generate_month_range(employment_start, employment_end))
        monthly = _generate_monthly_series(
            employment_start, employment_end, all_months, prior_months
        )

    return SeniorityResult(totals=totals, monthly=monthly)


def compute_seniority_method_c(
    matash_records: list[MatashRecord],
    target_industry: str,
    defendant_name: str,
    employment_start: date,
    employment_end: date,
) -> SeniorityResult:
    """Compute seniority using Method ג: מת"ש PDF extraction.

    Args:
        matash_records: Records extracted from מת"ש PDF
        target_industry: Industry to filter by
        defendant_name: Name of defendant employer
        employment_start: Start of defendant employment
        employment_end: End of defendant employment

    Returns SeniorityResult with totals, monthly series, and annotated records.
    """
    # Annotate and filter records
    filtered_records = []
    defendant_records = []

    for record in matash_records:
        # Check if record matches target industry
        is_relevant = record.industry.lower() == target_industry.lower()
        record.is_relevant_industry = is_relevant

        # Check if record is defendant
        is_defendant = defendant_name.lower() in record.employer_name.lower()
        record.is_defendant = is_defendant

        if is_relevant and record.start_date and record.end_date:
            filtered_records.append(record)
            if is_defendant:
                defendant_records.append(record)

    # Count total industry months (union of all filtered records)
    all_industry_periods = [
        (r.start_date, r.end_date)
        for r in filtered_records
        if r.start_date and r.end_date
    ]
    total_industry_month_set = _count_work_months_from_periods(all_industry_periods)
    total_industry_months = len(total_industry_month_set)

    # Count defendant months
    defendant_periods = [
        (r.start_date, r.end_date)
        for r in defendant_records
        if r.start_date and r.end_date
    ]
    defendant_month_set = _count_work_months_from_periods(defendant_periods)
    at_defendant_months = len(defendant_month_set)

    # Update months_counted in records
    for record in matash_records:
        if record.start_date and record.end_date and record.is_relevant_industry:
            record_months = _count_work_months_from_periods(
                [(record.start_date, record.end_date)]
            )
            record.months_counted = len(record_months)

    # Prior seniority = total - defendant
    prior_months = total_industry_months - at_defendant_months

    # Generate monthly series for defendant employment range
    monthly = _generate_monthly_series(
        employment_start, employment_end, defendant_month_set, prior_months
    )

    totals = SeniorityTotals(
        input_method=SeniorityMethod.MATASH_PDF,
        prior_seniority_months=prior_months,
        at_defendant_months=at_defendant_months,
        at_defendant_years=_months_to_years(at_defendant_months),
        total_industry_months=total_industry_months,
        total_industry_years=_months_to_years(total_industry_months),
        matash_records=matash_records,
    )

    return SeniorityResult(totals=totals, monthly=monthly)


def get_seniority_at_date(
    monthly: list[SeniorityMonthly],
    as_of_date: date,
) -> dict:
    """Get seniority values as of a specific date.

    Args:
        monthly: Monthly seniority series
        as_of_date: Date to query

    Returns dict with seniority values at that date.
    """
    as_of_month = (as_of_date.year, as_of_date.month)

    # Find the last entry <= as_of_date
    result_entry = None
    for entry in monthly:
        if entry.month <= as_of_month:
            result_entry = entry
        else:
            break

    if result_entry is None:
        return {
            "total_industry_months": 0,
            "total_industry_years": Decimal("0"),
            "at_defendant_months": 0,
            "at_defendant_years": Decimal("0"),
        }

    return {
        "total_industry_months": result_entry.total_industry_cumulative,
        "total_industry_years": result_entry.total_industry_years_cumulative,
        "at_defendant_months": result_entry.at_defendant_cumulative,
        "at_defendant_years": result_entry.at_defendant_years_cumulative,
    }


def check_no_industry_records(
    matash_records: list[MatashRecord],
    target_industry: str,
) -> bool:
    """Check if there are no records for the specified industry.

    Returns True if no records match the industry (warning case).
    """
    for record in matash_records:
        if record.industry.lower() == target_industry.lower():
            return False
    return True
