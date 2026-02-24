"""Salary conversion module — converts salary input to all types.

Converts user salary input (hourly/daily/monthly/per-shift, net/gross)
to all salary types, enforcing minimum wage.

See docs/skills/salary-conversion/SKILL.md for complete documentation.
"""

import csv
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Literal

from app.ssot import (
    PeriodMonthRecord,
    SalaryType,
    NetOrGross,
    WeekType,
)


# Net to gross multiplier
NET_TO_GROSS_MULTIPLIER = Decimal("1.12")


@dataclass
class MinimumWageEntry:
    """Minimum wage entry from historical table."""
    effective_date: date
    hourly: Decimal
    daily_5day: Decimal
    daily_6day: Decimal
    monthly: Decimal


@dataclass
class SalaryConversionResult:
    """Result of salary conversion for a single period×month."""
    # Minimum wage check
    minimum_wage_value: Decimal
    minimum_wage_type: str
    minimum_applied: bool
    minimum_gap: Decimal
    effective_amount: Decimal

    # Converted values
    salary_hourly: Decimal
    salary_daily: Decimal
    salary_monthly: Decimal


# Module-level cache for minimum wage data
_minimum_wage_cache: list[MinimumWageEntry] | None = None


def _load_minimum_wage_data(data_path: Path | None = None) -> list[MinimumWageEntry]:
    """Load minimum wage data from CSV file."""
    global _minimum_wage_cache

    if _minimum_wage_cache is not None:
        return _minimum_wage_cache

    if data_path is None:
        # Default path relative to backend directory
        data_path = Path(__file__).parent.parent.parent / "data" / "minimum_wage.csv"

    entries = []
    with open(data_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            entries.append(MinimumWageEntry(
                effective_date=date.fromisoformat(row["effective_date"]),
                hourly=Decimal(row["hourly"]),
                daily_5day=Decimal(row["daily_5day"]),
                daily_6day=Decimal(row["daily_6day"]),
                monthly=Decimal(row["monthly"]),
            ))

    # Sort by date descending for efficient lookup
    entries.sort(key=lambda e: e.effective_date, reverse=True)
    _minimum_wage_cache = entries
    return entries


def _clear_minimum_wage_cache():
    """Clear the minimum wage cache (for testing)."""
    global _minimum_wage_cache
    _minimum_wage_cache = None


def get_minimum_wage(
    target_date: date,
    wage_type: Literal["hourly", "daily_5day", "daily_6day", "monthly"],
    data_path: Path | None = None,
) -> Decimal:
    """Get minimum wage for a specific date and type.

    Args:
        target_date: The date to look up
        wage_type: Type of minimum wage to return
        data_path: Optional path to CSV file

    Returns:
        The minimum wage value
    """
    entries = _load_minimum_wage_data(data_path)

    # Find the latest entry with effective_date <= target_date
    for entry in entries:
        if entry.effective_date <= target_date:
            return getattr(entry, wage_type)

    # If no entry found, use the oldest entry (shouldn't happen in practice)
    if entries:
        return getattr(entries[-1], wage_type)

    raise ValueError(f"No minimum wage data found for {target_date}")


def _get_comparison_type(
    input_type: SalaryType,
    week_type: WeekType,
) -> str:
    """Get the minimum wage type to compare against.

    Args:
        input_type: The salary input type
        week_type: 5-day or 6-day work week

    Returns:
        The minimum wage field name for comparison
    """
    if input_type == SalaryType.HOURLY:
        return "hourly"
    elif input_type == SalaryType.DAILY:
        return "daily_5day" if week_type == WeekType.FIVE_DAY else "daily_6day"
    elif input_type == SalaryType.MONTHLY:
        return "monthly"
    elif input_type == SalaryType.PER_SHIFT:
        # Per-shift compares to daily minimum
        return "daily_5day" if week_type == WeekType.FIVE_DAY else "daily_6day"
    else:
        raise ValueError(f"Unknown salary type: {input_type}")


def convert_salary(
    input_amount: Decimal,
    input_type: SalaryType,
    input_net_or_gross: NetOrGross,
    avg_regular_hours_per_day: Decimal,
    avg_regular_hours_per_month: Decimal,
    avg_regular_hours_per_shift: Decimal | None,
    target_date: date,
    week_type: WeekType = WeekType.FIVE_DAY,
    data_path: Path | None = None,
) -> SalaryConversionResult:
    """Convert salary from input type to all types.

    Args:
        input_amount: The raw salary amount
        input_type: Type of input (hourly/daily/monthly/per_shift)
        input_net_or_gross: Whether input is net or gross
        avg_regular_hours_per_day: Average regular hours per work day
        avg_regular_hours_per_month: Total regular hours in the month
        avg_regular_hours_per_shift: Average regular hours per shift (for per_shift only)
        target_date: Date for minimum wage lookup
        week_type: 5-day or 6-day work week
        data_path: Optional path to minimum wage CSV

    Returns:
        SalaryConversionResult with all converted values
    """
    # Step 1: Gross normalization
    if input_net_or_gross == NetOrGross.NET:
        gross_amount = input_amount * NET_TO_GROSS_MULTIPLIER
    else:
        gross_amount = input_amount

    # Step 2: Minimum wage check
    comparison_type = _get_comparison_type(input_type, week_type)
    minimum_wage = get_minimum_wage(target_date, comparison_type, data_path)

    if gross_amount < minimum_wage:
        effective_amount = minimum_wage
        minimum_applied = True
        minimum_gap = minimum_wage - gross_amount
    else:
        effective_amount = gross_amount
        minimum_applied = False
        minimum_gap = Decimal("0")

    # Step 3: Convert to all types (through hourly pivot)
    if input_type == SalaryType.HOURLY:
        hourly = effective_amount
    elif input_type == SalaryType.DAILY:
        if avg_regular_hours_per_day == 0:
            hourly = Decimal("0")
        else:
            hourly = effective_amount / avg_regular_hours_per_day
    elif input_type == SalaryType.MONTHLY:
        if avg_regular_hours_per_month == 0:
            hourly = Decimal("0")
        else:
            hourly = effective_amount / avg_regular_hours_per_month
    elif input_type == SalaryType.PER_SHIFT:
        if avg_regular_hours_per_shift is None or avg_regular_hours_per_shift == 0:
            hourly = Decimal("0")
        else:
            hourly = effective_amount / avg_regular_hours_per_shift
    else:
        raise ValueError(f"Unknown salary type: {input_type}")

    # Convert hourly to other types
    daily = hourly * avg_regular_hours_per_day
    monthly = hourly * avg_regular_hours_per_month

    return SalaryConversionResult(
        minimum_wage_value=minimum_wage,
        minimum_wage_type=comparison_type,
        minimum_applied=minimum_applied,
        minimum_gap=minimum_gap,
        effective_amount=effective_amount,
        salary_hourly=hourly,
        salary_daily=daily,
        salary_monthly=monthly,
    )


def process_period_month_record(
    pmr: PeriodMonthRecord,
    input_amount: Decimal,
    input_type: SalaryType,
    input_net_or_gross: NetOrGross,
    week_type: WeekType = WeekType.FIVE_DAY,
    data_path: Path | None = None,
) -> PeriodMonthRecord:
    """Process a PeriodMonthRecord and fill in salary fields.

    Args:
        pmr: The period month record with hours data filled
        input_amount: Raw salary input amount
        input_type: Type of salary input
        input_net_or_gross: Net or gross
        week_type: 5-day or 6-day work week
        data_path: Optional path to minimum wage CSV

    Returns:
        Updated PeriodMonthRecord with salary fields filled
    """
    # Calculate avg_regular_hours_per_shift if needed
    avg_per_shift = None
    if input_type == SalaryType.PER_SHIFT and pmr.shifts_count > 0:
        avg_per_shift = pmr.total_regular_hours / Decimal(pmr.shifts_count)

    # Use first day of month for minimum wage lookup
    year, month = pmr.month
    target_date = date(year, month, 1)

    # Convert gross amount
    if input_net_or_gross == NetOrGross.NET:
        gross_amount = input_amount * NET_TO_GROSS_MULTIPLIER
    else:
        gross_amount = input_amount

    result = convert_salary(
        input_amount=input_amount,
        input_type=input_type,
        input_net_or_gross=input_net_or_gross,
        avg_regular_hours_per_day=pmr.avg_regular_hours_per_day,
        avg_regular_hours_per_month=pmr.total_regular_hours,
        avg_regular_hours_per_shift=avg_per_shift,
        target_date=target_date,
        week_type=week_type,
        data_path=data_path,
    )

    # Update the record
    pmr.salary_input_amount = input_amount
    pmr.salary_input_type = input_type
    pmr.salary_input_net_or_gross = input_net_or_gross
    pmr.salary_gross_amount = gross_amount

    pmr.minimum_wage_value = result.minimum_wage_value
    pmr.minimum_wage_type = result.minimum_wage_type
    pmr.minimum_applied = result.minimum_applied
    pmr.minimum_gap = result.minimum_gap
    pmr.effective_amount = result.effective_amount

    pmr.salary_hourly = result.salary_hourly
    pmr.salary_daily = result.salary_daily
    pmr.salary_monthly = result.salary_monthly

    return pmr
