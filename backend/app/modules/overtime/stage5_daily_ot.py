"""Stage 5: Daily (Per-Shift) Overtime Detection.

Calculates overtime tiers for each shift based on threshold.
"""

from decimal import Decimal

from ...ssot import Shift
from .config import OTConfig, DEFAULT_CONFIG


def detect_daily_ot(
    shifts: list[Shift],
    config: OTConfig | None = None,
) -> list[Shift]:
    """Detect daily overtime for each shift.

    Rules:
    - If net_hours <= threshold -> all regular (Tier 0)
    - If net_hours > threshold:
        - Hours up to threshold -> Tier 0 (regular)
        - Next 2 hours -> Tier 1
        - Remaining -> Tier 2

    Args:
        shifts: List of shifts with threshold populated
        config: OT configuration (uses default if None)

    Returns:
        Shifts with daily OT fields populated
    """
    if config is None:
        config = DEFAULT_CONFIG

    for shift in shifts:
        net = shift.net_hours
        threshold = shift.threshold

        if net <= threshold:
            # All regular
            shift.regular_hours = net
            shift.ot_tier1_hours = Decimal("0")
            shift.ot_tier2_hours = Decimal("0")
            shift.daily_ot_hours = Decimal("0")
        else:
            # Regular = threshold
            shift.regular_hours = threshold

            # OT = excess
            ot_hours = net - threshold

            # Tier 1 = first N hours (configurable, default 2)
            tier1 = min(ot_hours, config.tier1_max_hours)
            shift.ot_tier1_hours = tier1

            # Tier 2 = remainder
            shift.ot_tier2_hours = ot_hours - tier1

            shift.daily_ot_hours = ot_hours

    return shifts
