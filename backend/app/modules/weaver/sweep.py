"""Stage 2: Sweep Line algorithm to create atomic periods.

Collects all boundaries from all axes, creates atomic periods,
and merges consecutive atoms with the same combination.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from app.ssot import (
    Duration,
    EffectivePeriod,
    TimeRange,
    DayShifts,
)


@dataclass
class Atom:
    """Atomic period with unique (EP, WP, ST) combination."""
    start: date
    end: date
    employment_period_id: str
    work_pattern_id: str
    salary_tier_id: str


def collect_boundaries(
    employment_periods: list[Any],
    work_patterns: list[Any],
    salary_tiers: list[Any]
) -> list[date]:
    """Collect all unique boundary dates from all axes.

    Uses end + 1 day for exclusive end representation.
    """
    boundaries = set()

    for ep in employment_periods:
        boundaries.add(ep.start)
        boundaries.add(ep.end + timedelta(days=1))

    for wp in work_patterns:
        boundaries.add(wp.start)
        boundaries.add(wp.end + timedelta(days=1))

    for st in salary_tiers:
        boundaries.add(st.start)
        boundaries.add(st.end + timedelta(days=1))

    return sorted(boundaries)


def find_active_item(items: list[Any], atom_start: date, atom_end: date) -> Any | None:
    """Find the item that fully covers the given range."""
    for item in items:
        if item.start <= atom_start and item.end >= atom_end:
            return item
    return None


def create_atomic_periods(
    boundaries: list[date],
    employment_periods: list[Any],
    work_patterns: list[Any],
    salary_tiers: list[Any]
) -> list[Atom]:
    """Create atomic periods between consecutive boundaries.

    Only creates atoms for ranges within employment periods.
    """
    atoms = []

    for i in range(len(boundaries) - 1):
        atom_start = boundaries[i]
        atom_end = boundaries[i + 1] - timedelta(days=1)  # Inclusive end

        # Skip invalid ranges (can happen at boundaries)
        if atom_end < atom_start:
            continue

        # Find active employment period
        ep = find_active_item(employment_periods, atom_start, atom_end)
        if ep is None:
            continue  # Not in employment period (gap or outside)

        # Find active work pattern and salary tier
        # Validation ensures these exist
        wp = find_active_item(work_patterns, atom_start, atom_end)
        st = find_active_item(salary_tiers, atom_start, atom_end)

        if wp is None or st is None:
            # Should not happen after validation, but defensive
            continue

        atoms.append(Atom(
            start=atom_start,
            end=atom_end,
            employment_period_id=ep.id,
            work_pattern_id=wp.id,
            salary_tier_id=st.id,
        ))

    return atoms


def merge_consecutive_atoms(atoms: list[Atom]) -> list[Atom]:
    """Merge consecutive atoms with the same (EP, WP, ST) combination.

    Only merges within the same employment_period.
    """
    if not atoms:
        return []

    merged = [Atom(
        start=atoms[0].start,
        end=atoms[0].end,
        employment_period_id=atoms[0].employment_period_id,
        work_pattern_id=atoms[0].work_pattern_id,
        salary_tier_id=atoms[0].salary_tier_id,
    )]

    for i in range(1, len(atoms)):
        current = atoms[i]
        last = merged[-1]

        same_combo = (
            current.employment_period_id == last.employment_period_id and
            current.work_pattern_id == last.work_pattern_id and
            current.salary_tier_id == last.salary_tier_id
        )
        consecutive = (current.start == last.end + timedelta(days=1))

        if same_combo and consecutive:
            # Extend the last atom
            last.end = current.end
        else:
            merged.append(Atom(
                start=current.start,
                end=current.end,
                employment_period_id=current.employment_period_id,
                work_pattern_id=current.work_pattern_id,
                salary_tier_id=current.salary_tier_id,
            ))

    return merged


def compute_duration(start: date, end: date) -> Duration:
    """Compute duration with multiple representations.

    Display string is NOT filled here - that's Phase 4's job.
    """
    days = (end - start).days + 1  # Inclusive

    # Decimal months: days / 30
    months_decimal = Decimal(days) / Decimal("30")

    # Years decimal: days / 365
    years_decimal = Decimal(days) / Decimal("365")

    # Whole months and remainder days
    months_whole = days // 30
    days_remainder = days % 30

    # Whole years, months remainder, and extra days
    years_whole = days // 365
    remaining_after_years = days % 365
    months_remainder = remaining_after_years // 30

    return Duration(
        days=days,
        months_decimal=months_decimal,
        years_decimal=years_decimal,
        months_whole=months_whole,
        days_remainder=days_remainder,
        years_whole=years_whole,
        months_remainder=months_remainder,
        display="",  # Filled by Phase 4
    )


def build_effective_periods(
    merged_atoms: list[Atom],
    work_patterns: list[Any],
    salary_tiers: list[Any]
) -> list[EffectivePeriod]:
    """Build EffectivePeriod objects from merged atoms.

    Denormalizes work pattern and salary tier data into each period.
    """
    # Build lookup maps
    wp_map = {wp.id: wp for wp in work_patterns}
    st_map = {st.id: st for st in salary_tiers}

    result = []

    for i, atom in enumerate(merged_atoms):
        wp = wp_map[atom.work_pattern_id]
        st = st_map[atom.salary_tier_id]

        # Convert TimeRange lists
        default_shifts = []
        if hasattr(wp, 'default_shifts') and wp.default_shifts:
            default_shifts = list(wp.default_shifts)

        default_breaks = []
        if hasattr(wp, 'default_breaks') and wp.default_breaks:
            default_breaks = list(wp.default_breaks)

        # Per-day overrides
        per_day = None
        if hasattr(wp, 'per_day') and wp.per_day:
            per_day = dict(wp.per_day)

        daily_overrides = None
        if hasattr(wp, 'daily_overrides') and wp.daily_overrides:
            daily_overrides = dict(wp.daily_overrides)

        result.append(EffectivePeriod(
            id=f"EP{i + 1}",
            start=atom.start,
            end=atom.end,
            duration=compute_duration(atom.start, atom.end),
            employment_period_id=atom.employment_period_id,
            work_pattern_id=atom.work_pattern_id,
            salary_tier_id=atom.salary_tier_id,
            pattern_work_days=list(wp.work_days) if hasattr(wp, 'work_days') else [],
            pattern_default_shifts=default_shifts,
            pattern_default_breaks=default_breaks,
            pattern_per_day=per_day,
            pattern_daily_overrides=daily_overrides,
            salary_amount=st.amount if hasattr(st, 'amount') else Decimal("0"),
            salary_type=st.type if hasattr(st, 'type') else None,
            salary_net_or_gross=st.net_or_gross if hasattr(st, 'net_or_gross') else None,
        ))

    return result


def sweep(
    employment_periods: list[Any],
    work_patterns: list[Any],
    salary_tiers: list[Any]
) -> list[EffectivePeriod]:
    """Run the complete sweep line algorithm.

    Returns a list of EffectivePeriod objects with all data denormalized.
    """
    # Step 1: Collect boundaries
    boundaries = collect_boundaries(employment_periods, work_patterns, salary_tiers)

    # Step 2: Create atomic periods
    atoms = create_atomic_periods(boundaries, employment_periods, work_patterns, salary_tiers)

    # Step 3: Merge consecutive atoms with same combination
    merged = merge_consecutive_atoms(atoms)

    # Step 4: Build effective periods with denormalized data
    effective_periods = build_effective_periods(merged, work_patterns, salary_tiers)

    return effective_periods
