"""Overtime calculation configuration.

All thresholds are configurable per the skill requirement.
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class OTConfig:
    """Configuration for overtime calculation.

    All thresholds can be overridden by the user from the UI.
    """

    # Weekly threshold (סף שבועי)
    weekly_cap: Decimal = Decimal("42")

    # Daily thresholds by week type
    threshold_5day: Decimal = Decimal("8.4")  # סף יומי בשבוע 5 ימים
    threshold_6day: Decimal = Decimal("8.0")  # סף יומי בשבוע 6 ימים

    # Special thresholds
    threshold_eve_rest: Decimal = Decimal("7.0")  # סף ערב מנוחה
    threshold_night: Decimal = Decimal("7.0")  # סף משמרת לילה

    # Tier configuration
    tier1_max_hours: Decimal = Decimal("2")  # שעות מקסימום ב-Tier 1

    # Night shift definition
    night_start_hour: int = 22  # Start of night band
    night_end_hour: int = 6  # End of night band
    night_min_hours: Decimal = Decimal("2")  # Minimum hours in band to qualify


# Default configuration
DEFAULT_CONFIG = OTConfig()
