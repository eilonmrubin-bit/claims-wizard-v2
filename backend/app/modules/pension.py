"""Pension (פנסיה) calculation module.

Calculates pension contributions per calendar month.
See docs/skills/pension/SKILL.md for complete documentation.
"""

from datetime import date
from decimal import Decimal

from ..ssot import (
    PensionResult,
    PensionMonthData,
    PeriodMonthRecord,
    MonthAggregate,
)


# =============================================================================
# Pension Rates by Industry (from SKILL.md)
# =============================================================================

PENSION_RATES: dict[str, list[tuple[date, Decimal]]] = {
    "general": [(date(1900, 1, 1), Decimal("0.065"))],
    "agriculture": [(date(1900, 1, 1), Decimal("0.065"))],
    "cleaning": [(date(1900, 1, 1), Decimal("0.075"))],
    "construction": [
        (date(1900, 1, 1), Decimal("0.060")),
        (date(2018, 7, 1), Decimal("0.071")),
    ],
}


def _get_pension_rate(industry: str, month_year: int, month_month: int) -> Decimal:
    """Get pension rate for a specific month and industry.

    Uses the rate with the latest effective_date <= month_start.
    """
    month_start = date(month_year, month_month, 1)
    rates = PENSION_RATES.get(industry, PENSION_RATES["general"])
    rate = rates[0][1]
    for effective_date, r in rates:
        if effective_date <= month_start:
            rate = r
    return rate


def compute_pension(
    period_month_records: list[PeriodMonthRecord],
    month_aggregates: list[MonthAggregate],
    industry: str,
    right_toggles: dict | None = None,
) -> PensionResult:
    """Compute pension entitlement.

    For each calendar month:
        pension_month = salary_monthly × pension_rate × job_scope

    Args:
        period_month_records: Monthly records with salary_monthly
        month_aggregates: Monthly aggregates with job_scope
        industry: Industry identifier
        right_toggles: Toggle settings (check pension.enabled)

    Returns:
        PensionResult with monthly breakdown and grand total
    """
    # Check if pension is enabled
    if right_toggles and right_toggles.get("pension", {}).get("enabled") is False:
        return PensionResult(entitled=False, industry=industry)

    # Build lookup for month_aggregates
    ma_by_month: dict[tuple[int, int], MonthAggregate] = {
        ma.month: ma for ma in month_aggregates
    }

    # Aggregate per month (sum across effective periods)
    months_data: dict[tuple[int, int], Decimal] = {}
    for pmr in period_month_records:
        m = pmr.month
        if m not in months_data:
            months_data[m] = Decimal("0")
        months_data[m] += pmr.salary_monthly or Decimal("0")

    result_months = []
    grand_total = Decimal("0")

    for m in sorted(months_data.keys()):
        year, month = m
        salary = months_data[m]
        ma = ma_by_month.get(m)
        job_scope = ma.job_scope if ma else Decimal("1")
        rate = _get_pension_rate(industry, year, month)
        month_value = salary * rate * job_scope
        grand_total += month_value

        result_months.append(PensionMonthData(
            month=m,
            month_start=date(year, month, 1),
            salary_monthly=salary,
            job_scope=job_scope,
            pension_rate=rate,
            month_value=month_value,
        ))

    return PensionResult(
        entitled=True,
        industry=industry,
        months=result_months,
        grand_total_value=grand_total,
    )
