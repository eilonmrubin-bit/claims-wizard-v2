"""Stage 8: Pricing — calculate claim amounts for overtime.

This stage runs in the RIGHTS CALCULATION phase (after salary conversion),
not with stages 1-7 in the INPUT PROCESSING phase.

See docs/skills/overtime-calculation/SKILL.md for complete documentation.
"""

from dataclasses import dataclass
from decimal import Decimal

from app.ssot import Shift, PricingBreakdown, PeriodMonthRecord


# Rate multipliers by tier and rest status
RATE_MULTIPLIERS = {
    # (tier, in_rest) -> rate_multiplier
    (0, False): Decimal("1.00"),
    (1, False): Decimal("1.25"),
    (2, False): Decimal("1.50"),
    (0, True): Decimal("1.50"),
    (1, True): Decimal("1.75"),
    (2, True): Decimal("2.00"),
}

# Claim multipliers (difference from base pay)
# When employer_paid_rest_premium is False
CLAIM_MULTIPLIERS_FULL = {
    # (tier, in_rest) -> claim_multiplier
    (0, False): Decimal("0.00"),  # Regular hours - no claim
    (1, False): Decimal("0.25"),  # 25% bonus
    (2, False): Decimal("0.50"),  # 50% bonus
    (0, True): Decimal("0.50"),   # Rest premium only
    (1, True): Decimal("0.75"),   # Rest + OT tier 1
    (2, True): Decimal("1.00"),   # Rest + OT tier 2
}

# Claim multipliers when employer_paid_rest_premium is True
# (only OT bonus, not rest premium)
CLAIM_MULTIPLIERS_NO_REST = {
    (0, False): Decimal("0.00"),
    (1, False): Decimal("0.25"),
    (2, False): Decimal("0.50"),
    (0, True): Decimal("0.00"),   # No rest premium claim
    (1, True): Decimal("0.25"),   # Only OT tier 1
    (2, True): Decimal("0.50"),   # Only OT tier 2
}


@dataclass
class PricingResult:
    """Result of pricing calculation for a shift."""
    claim_amount: Decimal
    breakdown: list[PricingBreakdown]


def _get_hourly_wage(
    shift: Shift,
    period_month_records: dict[tuple[str, tuple[int, int]], PeriodMonthRecord],
) -> Decimal:
    """Get hourly wage for a shift from period_month_records.

    Args:
        shift: The shift to price
        period_month_records: Map of (effective_period_id, month) -> record

    Returns:
        The hourly wage for the shift's period and month
    """
    if shift.assigned_day is None:
        return Decimal("0")

    key = (
        shift.effective_period_id,
        (shift.assigned_day.year, shift.assigned_day.month),
    )

    record = period_month_records.get(key)
    if record is None:
        return Decimal("0")

    return record.salary_hourly


def price_shift(
    shift: Shift,
    hourly_wage: Decimal,
    employer_paid_rest_premium: bool = False,
) -> PricingResult:
    """Calculate claim amount for a single shift.

    Uses the hour breakdown from stage 7 (rest_window_* and non_rest_* fields).

    Args:
        shift: The shift with OT tiers and rest window hours filled
        hourly_wage: The hourly wage for this shift
        employer_paid_rest_premium: If True, exclude rest premium from claim

    Returns:
        PricingResult with total claim amount and breakdown
    """
    claim_multipliers = (
        CLAIM_MULTIPLIERS_NO_REST if employer_paid_rest_premium
        else CLAIM_MULTIPLIERS_FULL
    )

    breakdown = []
    total_claim = Decimal("0")

    # Process each combination of (tier, in_rest)
    hour_segments = [
        # (hours, tier, in_rest)
        (shift.non_rest_regular_hours, 0, False),
        (shift.non_rest_ot_tier1_hours, 1, False),
        (shift.non_rest_ot_tier2_hours, 2, False),
        (shift.rest_window_regular_hours, 0, True),
        (shift.rest_window_ot_tier1_hours, 1, True),
        (shift.rest_window_ot_tier2_hours, 2, True),
    ]

    for hours, tier, in_rest in hour_segments:
        if hours <= 0:
            continue

        rate_multiplier = RATE_MULTIPLIERS[(tier, in_rest)]
        claim_multiplier = claim_multipliers[(tier, in_rest)]
        claim_amount = hourly_wage * claim_multiplier * hours

        breakdown.append(PricingBreakdown(
            hours=hours,
            tier=tier,
            in_rest=in_rest,
            rate_multiplier=rate_multiplier,
            claim_multiplier=claim_multiplier,
            hourly_wage=hourly_wage,
            claim_amount=claim_amount,
        ))

        total_claim += claim_amount

    return PricingResult(
        claim_amount=total_claim,
        breakdown=breakdown,
    )


def run_pricing(
    shifts: list[Shift],
    period_month_records: dict[tuple[str, tuple[int, int]], PeriodMonthRecord],
    employer_paid_rest_premium: bool = False,
) -> list[Shift]:
    """Run pricing on all shifts.

    Args:
        shifts: List of shifts with OT tiers and rest window hours filled
        period_month_records: Map of (effective_period_id, month) -> record
        employer_paid_rest_premium: If True, exclude rest premium from claim

    Returns:
        List of shifts with claim_amount and pricing_breakdown filled
    """
    for shift in shifts:
        hourly_wage = _get_hourly_wage(shift, period_month_records)

        result = price_shift(shift, hourly_wage, employer_paid_rest_premium)

        shift.claim_amount = result.claim_amount
        shift.pricing_breakdown = result.breakdown

    return shifts


def calculate_monthly_totals(
    shifts: list[Shift],
) -> dict[tuple[int, int], Decimal]:
    """Calculate total claim amounts per month.

    Args:
        shifts: List of priced shifts

    Returns:
        Map of (year, month) -> total claim amount
    """
    totals: dict[tuple[int, int], Decimal] = {}

    for shift in shifts:
        if shift.assigned_day is None or shift.claim_amount is None:
            continue

        month = (shift.assigned_day.year, shift.assigned_day.month)
        if month not in totals:
            totals[month] = Decimal("0")

        totals[month] += shift.claim_amount

    return totals


def calculate_grand_total(shifts: list[Shift]) -> Decimal:
    """Calculate grand total claim amount across all shifts.

    Args:
        shifts: List of priced shifts

    Returns:
        Total claim amount
    """
    total = Decimal("0")

    for shift in shifts:
        if shift.claim_amount is not None:
            total += shift.claim_amount

    return total
