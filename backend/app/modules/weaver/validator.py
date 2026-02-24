"""Stage 1: Validation of input axes.

Validates:
1. Each axis internally (valid ranges, no overlaps)
2. Cross-axis coverage (every employment day covered by work_pattern AND salary_tier)
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any


@dataclass
class ValidationError:
    """Single validation error."""
    type: str
    axis: str
    message: str  # Hebrew for UI
    details: dict[str, Any]


def validate_axis_ranges(
    items: list[Any],
    axis_name: str,
    axis_name_hebrew: str
) -> list[ValidationError]:
    """Validate that all items have valid date ranges (start <= end)."""
    errors = []

    for item in items:
        if item.start > item.end:
            errors.append(ValidationError(
                type="invalid_range",
                axis=axis_name,
                message=f"טווח לא תקין ב{axis_name_hebrew}: תאריך התחלה ({item.start}) מאוחר מתאריך סיום ({item.end})",
                details={
                    "item_id": item.id,
                    "start": item.start.isoformat(),
                    "end": item.end.isoformat(),
                }
            ))

    return errors


def validate_axis_no_overlaps(
    items: list[Any],
    axis_name: str,
    axis_name_hebrew: str
) -> list[ValidationError]:
    """Validate that items within an axis do not overlap."""
    errors = []

    if len(items) < 2:
        return errors

    # Sort by start date
    sorted_items = sorted(items, key=lambda x: x.start)

    for i in range(1, len(sorted_items)):
        prev = sorted_items[i - 1]
        curr = sorted_items[i]

        # Overlap if current starts before or on previous end
        if curr.start <= prev.end:
            overlap_start = curr.start
            overlap_end = min(prev.end, curr.end)

            errors.append(ValidationError(
                type="overlap_within_axis",
                axis=axis_name,
                message=f"חפיפה ב{axis_name_hebrew}: {prev.id} ו-{curr.id} חופפים בין {overlap_start} ל-{overlap_end}",
                details={
                    "item_a_id": prev.id,
                    "item_b_id": curr.id,
                    "overlap_start": overlap_start.isoformat(),
                    "overlap_end": overlap_end.isoformat(),
                }
            ))

    return errors


def find_uncovered_ranges(
    ep_start: date,
    ep_end: date,
    covering_items: list[Any]
) -> list[tuple[date, date]]:
    """Find ranges within [ep_start, ep_end] not covered by any item.

    Uses a sweep line algorithm for efficiency - O(n) on number of items.
    """
    if not covering_items:
        return [(ep_start, ep_end)]

    # Filter items that intersect with the EP range
    relevant = [
        item for item in covering_items
        if item.start <= ep_end and item.end >= ep_start
    ]

    if not relevant:
        return [(ep_start, ep_end)]

    # Sort by start date
    sorted_items = sorted(relevant, key=lambda x: x.start)

    uncovered = []
    current_pos = ep_start

    for item in sorted_items:
        # Clamp item to EP bounds
        item_start = max(item.start, ep_start)
        item_end = min(item.end, ep_end)

        # Gap before this item?
        if item_start > current_pos:
            uncovered.append((current_pos, item_start - timedelta(days=1)))

        # Move position forward
        if item_end >= current_pos:
            current_pos = item_end + timedelta(days=1)

    # Gap after last item?
    if current_pos <= ep_end:
        uncovered.append((current_pos, ep_end))

    return uncovered


def validate_coverage(
    employment_periods: list[Any],
    work_patterns: list[Any],
    salary_tiers: list[Any]
) -> list[ValidationError]:
    """Validate that every day in every employment_period is covered
    by both a work_pattern AND a salary_tier.
    """
    errors = []

    for ep in employment_periods:
        # Check work_patterns coverage
        uncovered_wp = find_uncovered_ranges(ep.start, ep.end, work_patterns)
        for gap_start, gap_end in uncovered_wp:
            errors.append(ValidationError(
                type="uncovered_range",
                axis="work_patterns",
                message=f"דפוס עבודה חסר: תקופת העסקה {ep.id} לא מכוסה בין {gap_start} ל-{gap_end}",
                details={
                    "employment_period_id": ep.id,
                    "gap_start": gap_start.isoformat(),
                    "gap_end": gap_end.isoformat(),
                }
            ))

        # Check salary_tiers coverage
        uncovered_st = find_uncovered_ranges(ep.start, ep.end, salary_tiers)
        for gap_start, gap_end in uncovered_st:
            errors.append(ValidationError(
                type="uncovered_range",
                axis="salary_tiers",
                message=f"רמת שכר חסרה: תקופת העסקה {ep.id} לא מכוסה בין {gap_start} ל-{gap_end}",
                details={
                    "employment_period_id": ep.id,
                    "gap_start": gap_start.isoformat(),
                    "gap_end": gap_end.isoformat(),
                }
            ))

    return errors


def validate_rest_day_in_pattern(
    work_patterns: list[Any],
    rest_day: str
) -> list[ValidationError]:
    """Warn (not error) if work_pattern includes the rest day."""
    warnings = []

    rest_day_map = {
        "saturday": 6,
        "friday": 5,
        "sunday": 0,
    }

    rest_day_dow = rest_day_map.get(rest_day)
    if rest_day_dow is None:
        return warnings

    rest_day_hebrew = {
        "saturday": "שבת",
        "friday": "שישי",
        "sunday": "ראשון",
    }

    for wp in work_patterns:
        if rest_day_dow in wp.work_days:
            warnings.append(ValidationError(
                type="pattern_includes_rest_day",
                axis="work_patterns",
                message=f"דפוס עבודה {wp.id} כולל את יום המנוחה ({rest_day_hebrew.get(rest_day, rest_day)})",
                details={
                    "work_pattern_id": wp.id,
                    "rest_day": rest_day,
                    "rest_day_dow": rest_day_dow,
                }
            ))

    return warnings


def validate(
    employment_periods: list[Any],
    work_patterns: list[Any],
    salary_tiers: list[Any],
    rest_day: str = "saturday"
) -> tuple[list[ValidationError], list[ValidationError]]:
    """Run all validation checks.

    Returns:
        Tuple of (errors, warnings).
        If errors is non-empty, stop processing.
        Warnings are informational and don't block processing.
    """
    errors = []
    warnings = []

    # Validate each axis internally
    errors.extend(validate_axis_ranges(
        employment_periods, "employment_periods", "תקופות העסקה"
    ))
    errors.extend(validate_axis_ranges(
        work_patterns, "work_patterns", "דפוסי עבודה"
    ))
    errors.extend(validate_axis_ranges(
        salary_tiers, "salary_tiers", "רמות שכר"
    ))

    errors.extend(validate_axis_no_overlaps(
        employment_periods, "employment_periods", "תקופות העסקה"
    ))
    errors.extend(validate_axis_no_overlaps(
        work_patterns, "work_patterns", "דפוסי עבודה"
    ))
    errors.extend(validate_axis_no_overlaps(
        salary_tiers, "salary_tiers", "רמות שכר"
    ))

    # Cross-axis validation (only if internal validation passed)
    if not errors:
        errors.extend(validate_coverage(
            employment_periods, work_patterns, salary_tiers
        ))

    # Warnings
    warnings.extend(validate_rest_day_in_pattern(work_patterns, rest_day))

    return errors, warnings
