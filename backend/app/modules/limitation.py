"""Limitation (התיישנות) calculation module.

Calculates effective limitation windows considering freeze periods.
This is a POST-PROCESSING step — rights are calculated over full employment,
then filtered by limitation windows.

See docs/skills/limitation/SKILL.md for complete documentation.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Callable

from ..ssot import Duration


@dataclass
class FreezePeriod:
    """A period during which limitation clock is frozen."""
    id: str
    name: str
    start_date: date
    end_date: date

    @property
    def days(self) -> int:
        """Number of days in this freeze period (inclusive)."""
        return (self.end_date - self.start_date).days + 1


@dataclass
class LimitationType:
    """A type of limitation with its calculation rule."""
    id: str
    name: str
    compute_base_window_start: Callable[[date], date]


@dataclass
class LimitationWindow:
    """Computed limitation window for a specific type."""
    type_id: str
    type_name: str
    base_window_start: date
    effective_window_start: date
    freeze_periods_applied: list[FreezePeriod] = field(default_factory=list)


@dataclass
class LimitationConfig:
    """Configuration for limitation calculation."""
    filing_date: date
    freeze_periods: list[FreezePeriod] = field(default_factory=list)


# =============================================================================
# Built-in limitation types
# =============================================================================

def compute_general_base_window(filing_date: date) -> date:
    """Compute base window start for general limitation (7 years back)."""
    try:
        return filing_date.replace(year=filing_date.year - 7)
    except ValueError:
        # Handle Feb 29 -> Feb 28
        return date(filing_date.year - 7, filing_date.month, filing_date.day - 1)


def compute_vacation_base_window(filing_date: date) -> date:
    """Compute base window start for vacation limitation (3+שוטף).

    Rule: January 1st of (filing_year - 3)
    """
    return date(filing_date.year - 3, 1, 1)


# Default limitation types
GENERAL_LIMITATION = LimitationType(
    id="general",
    name="התיישנות כללית",
    compute_base_window_start=compute_general_base_window,
)

VACATION_LIMITATION = LimitationType(
    id="vacation",
    name="התיישנות חופשה",
    compute_base_window_start=compute_vacation_base_window,
)

# Default freeze periods
DEFAULT_WAR_FREEZE = FreezePeriod(
    id="war_freeze_2023",
    name="הקפאת מלחמת התקומה",
    start_date=date(2023, 10, 7),
    end_date=date(2024, 4, 6),
)


# =============================================================================
# Core algorithm
# =============================================================================

def days_between(start: date, end: date) -> int:
    """Calculate days between two dates (inclusive of both endpoints)."""
    return (end - start).days + 1


def compute_duration(start: date, end: date) -> Duration:
    """Compute Duration object from start and end dates.

    Fills all numeric fields. Display field is left empty for Phase 4 formatter.
    """
    if start > end:
        return Duration()

    total_days = days_between(start, end)

    # Decimal representations
    months_decimal = Decimal(total_days) / Decimal("30")
    years_decimal = Decimal(total_days) / Decimal("365")

    # Whole/remainder representations
    years_whole = total_days // 365
    remaining_after_years = total_days % 365
    months_whole = remaining_after_years // 30
    days_remainder = remaining_after_years % 30

    # Alternative: total months and remainder
    total_months_whole = total_days // 30
    months_remainder = total_months_whole % 12

    return Duration(
        days=total_days,
        months_decimal=months_decimal,
        years_decimal=years_decimal,
        months_whole=total_months_whole,
        days_remainder=total_days % 30,
        years_whole=years_whole,
        months_remainder=months_remainder,
        display="",  # Filled by Phase 4 formatter
    )


def merge_freeze_periods(freezes: list[FreezePeriod]) -> list[FreezePeriod]:
    """Merge overlapping freeze periods.

    Returns a new list with overlapping periods merged, sorted by start date.
    """
    if not freezes:
        return []

    # Sort by start date
    sorted_freezes = sorted(freezes, key=lambda f: f.start_date)

    merged = []
    current = sorted_freezes[0]

    for freeze in sorted_freezes[1:]:
        # Check if overlapping or adjacent (adjacent = end + 1 day = start)
        if freeze.start_date <= current.end_date + timedelta(days=1):
            # Merge: extend current to cover both
            current = FreezePeriod(
                id=f"{current.id}+{freeze.id}",
                name=f"{current.name} + {freeze.name}",
                start_date=current.start_date,
                end_date=max(current.end_date, freeze.end_date),
            )
        else:
            merged.append(current)
            current = freeze

    merged.append(current)
    return merged


def compute_effective_window(
    filing_date: date,
    base_window_start: date,
    freeze_periods: list[FreezePeriod],
) -> tuple[date, list[FreezePeriod]]:
    """Compute effective limitation window start considering freeze periods.

    Args:
        filing_date: The date the claim was filed
        base_window_start: The base window start (without freezes)
        freeze_periods: List of freeze periods to consider

    Returns:
        Tuple of (effective_window_start, applied_freeze_periods)
    """
    # Merge overlapping freezes and sort ascending by start
    merged = merge_freeze_periods(freeze_periods)

    # Filter to only freezes that end before or at filing date
    relevant = [f for f in merged if f.start_date <= filing_date]

    if not relevant:
        return base_window_start, []

    # Calculate active days needed
    active_needed = days_between(base_window_start, filing_date)

    # Walk backward from filing_date
    cursor = filing_date
    active_accumulated = 0
    applied_freezes = []

    # Process freeze periods from latest to earliest
    for freeze in reversed(relevant):
        if freeze.end_date >= cursor:
            if freeze.start_date < cursor:
                # Cursor is INSIDE this freeze — jump past it
                cursor = freeze.start_date - timedelta(days=1)
                applied_freezes.append(freeze)
            # else: freeze is entirely after cursor, skip
            continue

        # Active gap: from (freeze.end + 1) to cursor
        gap_start = freeze.end_date + timedelta(days=1)
        if gap_start > cursor:
            gap_days = 0
        else:
            gap_days = days_between(gap_start, cursor)

        if active_accumulated + gap_days >= active_needed:
            # Answer is within this gap
            remaining = active_needed - active_accumulated
            effective_start = cursor - timedelta(days=remaining - 1)
            return effective_start, applied_freezes

        active_accumulated += gap_days
        cursor = freeze.start_date - timedelta(days=1)
        applied_freezes.append(freeze)

    # Final gap: from cursor backward
    remaining = active_needed - active_accumulated
    effective_start = cursor - timedelta(days=remaining - 1)
    return effective_start, applied_freezes


def compute_limitation_window(
    limitation_type: LimitationType,
    config: LimitationConfig,
) -> LimitationWindow:
    """Compute limitation window for a specific type.

    Args:
        limitation_type: The type of limitation to compute
        config: Limitation configuration with filing date and freeze periods

    Returns:
        LimitationWindow with base and effective window starts
    """
    base_start = limitation_type.compute_base_window_start(config.filing_date)

    effective_start, applied = compute_effective_window(
        config.filing_date,
        base_start,
        config.freeze_periods,
    )

    return LimitationWindow(
        type_id=limitation_type.id,
        type_name=limitation_type.name,
        base_window_start=base_start,
        effective_window_start=effective_start,
        freeze_periods_applied=applied,
    )


# =============================================================================
# Filtering
# =============================================================================

@dataclass
class FilteredAmount:
    """Result of filtering an amount by limitation window."""
    full_amount: Decimal
    claimable_amount: Decimal
    excluded_amount: Decimal
    fraction: Decimal  # Fraction of period within window


def filter_period_by_window(
    period_start: date,
    period_end: date,
    full_amount: Decimal,
    effective_window_start: date,
    filing_date: date,
) -> FilteredAmount:
    """Filter a period's amount by the limitation window.

    Args:
        period_start: Start of the period (e.g., month start)
        period_end: End of the period (e.g., month end)
        full_amount: Full amount for this period
        effective_window_start: Start of claimable window
        filing_date: End of claimable window

    Returns:
        FilteredAmount with claimable and excluded portions
    """
    # Check if period is entirely outside window
    if period_end < effective_window_start or period_start > filing_date:
        return FilteredAmount(
            full_amount=full_amount,
            claimable_amount=Decimal("0"),
            excluded_amount=full_amount,
            fraction=Decimal("0"),
        )

    # Check if period is entirely inside window
    if period_start >= effective_window_start and period_end <= filing_date:
        return FilteredAmount(
            full_amount=full_amount,
            claimable_amount=full_amount,
            excluded_amount=Decimal("0"),
            fraction=Decimal("1"),
        )

    # Partial overlap — calculate fraction
    period_days = days_between(period_start, period_end)

    # Clamp to window
    claimable_start = max(period_start, effective_window_start)
    claimable_end = min(period_end, filing_date)
    claimable_days = days_between(claimable_start, claimable_end)

    fraction = Decimal(claimable_days) / Decimal(period_days)
    claimable_amount = full_amount * fraction
    excluded_amount = full_amount - claimable_amount

    return FilteredAmount(
        full_amount=full_amount,
        claimable_amount=claimable_amount,
        excluded_amount=excluded_amount,
        fraction=fraction,
    )


def filter_monthly_results(
    monthly_amounts: dict[tuple[int, int], Decimal],
    effective_window_start: date,
    filing_date: date,
) -> tuple[Decimal, Decimal, list[tuple[tuple[int, int], FilteredAmount]]]:
    """Filter monthly results by limitation window.

    Args:
        monthly_amounts: Map of (year, month) -> amount
        effective_window_start: Start of claimable window
        filing_date: End of claimable window

    Returns:
        Tuple of (total_claimable, total_excluded, details)
    """
    import calendar

    total_claimable = Decimal("0")
    total_excluded = Decimal("0")
    details = []

    for (year, month), amount in sorted(monthly_amounts.items()):
        # Get period boundaries
        _, last_day = calendar.monthrange(year, month)
        period_start = date(year, month, 1)
        period_end = date(year, month, last_day)

        filtered = filter_period_by_window(
            period_start, period_end, amount,
            effective_window_start, filing_date,
        )

        total_claimable += filtered.claimable_amount
        total_excluded += filtered.excluded_amount
        details.append(((year, month), filtered))

    return total_claimable, total_excluded, details
