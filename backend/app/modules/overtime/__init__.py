"""Overtime calculation module (Stages 1-7).

This module handles overtime calculation for Israeli labor law.
Stage 8 (Pricing) runs separately after salary conversion.

See docs/skills/overtime-calculation/SKILL.md for full specification.
"""

from .config import OTConfig
from .orchestrator import run_overtime_stages_1_to_7
from .stage1_assembly import assemble_shifts
from .stage2_assignment import assign_shifts
from .stage3_classification import classify_weeks
from .stage4_threshold import resolve_thresholds
from .stage5_daily_ot import detect_daily_ot
from .stage6_weekly_ot import detect_weekly_ot
from .stage7_rest_window import place_rest_windows
from .shabbat_times import get_shabbat_times, get_shabbat_times_range

__all__ = [
    "OTConfig",
    "run_overtime_stages_1_to_7",
    "assemble_shifts",
    "assign_shifts",
    "classify_weeks",
    "resolve_thresholds",
    "detect_daily_ot",
    "detect_weekly_ot",
    "place_rest_windows",
    "get_shabbat_times",
    "get_shabbat_times_range",
]
