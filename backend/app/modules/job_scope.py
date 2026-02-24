"""Job scope (היקף משרה) calculation module.

Calculates job scope percentage per month based on regular hours.

See docs/skills/job-scope/SKILL.md for complete documentation.
"""

from dataclasses import dataclass
from decimal import Decimal

from app.ssot import MonthAggregate


# Default full-time hours base (can be overridden via settings)
DEFAULT_FULL_TIME_HOURS_BASE = Decimal("182")


@dataclass
class JobScopeResult:
    """Result of job scope calculation for a single month."""
    month: tuple[int, int]
    regular_hours: Decimal
    full_time_hours_base: Decimal
    raw_scope: Decimal
    job_scope: Decimal  # effective scope, capped at 1.0


def calculate_job_scope(
    regular_hours: Decimal,
    full_time_hours_base: Decimal = DEFAULT_FULL_TIME_HOURS_BASE,
) -> tuple[Decimal, Decimal]:
    """Calculate job scope from regular hours.

    Args:
        regular_hours: Total regular hours in the month
        full_time_hours_base: Hours considered full-time (default 182)

    Returns:
        Tuple of (raw_scope, effective_scope)
        - raw_scope: regular_hours / full_time_hours_base
        - effective_scope: min(raw_scope, 1.0)
    """
    if full_time_hours_base == 0:
        return Decimal("0"), Decimal("0")

    raw_scope = regular_hours / full_time_hours_base
    effective_scope = min(raw_scope, Decimal("1"))

    return raw_scope, effective_scope


def process_month_aggregate(
    month_aggregate: MonthAggregate,
    full_time_hours_base: Decimal = DEFAULT_FULL_TIME_HOURS_BASE,
) -> MonthAggregate:
    """Process a MonthAggregate and fill in job scope fields.

    Args:
        month_aggregate: The month aggregate with hours data
        full_time_hours_base: Hours considered full-time

    Returns:
        Updated MonthAggregate with job scope fields filled
    """
    raw_scope, effective_scope = calculate_job_scope(
        month_aggregate.total_regular_hours,
        full_time_hours_base,
    )

    month_aggregate.full_time_hours_base = full_time_hours_base
    month_aggregate.raw_scope = raw_scope
    month_aggregate.job_scope = effective_scope

    return month_aggregate


def run_job_scope(
    month_aggregates: list[MonthAggregate],
    full_time_hours_base: Decimal = DEFAULT_FULL_TIME_HOURS_BASE,
) -> list[MonthAggregate]:
    """Process all month aggregates and calculate job scope.

    Args:
        month_aggregates: List of month aggregates from aggregator
        full_time_hours_base: Hours considered full-time

    Returns:
        List of MonthAggregate with job scope fields filled
    """
    for ma in month_aggregates:
        process_month_aggregate(ma, full_time_hours_base)

    return month_aggregates
