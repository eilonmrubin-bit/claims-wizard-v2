"""Overtime Orchestrator - Stages 1-7.

Entry point for overtime calculation pipeline.
Stage 8 (Pricing) runs separately after salary conversion.
"""

from dataclasses import dataclass

from ...ssot import DailyRecord, Shift, Week, RestDay, District
from .config import OTConfig, DEFAULT_CONFIG
from .stage1_assembly import assemble_shifts
from .stage2_assignment import assign_shifts
from .stage3_classification import classify_weeks
from .stage4_threshold import resolve_thresholds
from .stage5_daily_ot import detect_daily_ot
from .stage6_weekly_ot import detect_weekly_ot
from .stage7_rest_window import place_rest_windows


@dataclass
class OvertimeResult:
    """Result of overtime stages 1-7."""
    shifts: list[Shift]
    weeks: list[Week]
    success: bool = True
    errors: list[str] | None = None


def run_overtime_stages_1_to_7(
    daily_records: list[DailyRecord],
    rest_day: RestDay,
    district: District,
    config: OTConfig | None = None,
) -> OvertimeResult:
    """Run overtime calculation stages 1-7.

    Pipeline:
        1. Shift Assembly: Group raw entries into shifts
        2. Shift Assignment: Assign to day & week
        3. Week Classification: Determine 5/6 day week
        4. Threshold Resolution: Get daily threshold per shift
        5. Daily OT Detection: Per-shift OT tiers
        6. Weekly OT Detection: Weekly cap at 42
        7. Rest Window Placement: 36h window optimization

    Stage 8 (Pricing) runs separately after salary conversion.

    Args:
        daily_records: Daily records from weaver
        rest_day: Employee's rest day
        district: Employee's district
        config: OT configuration (uses default if None)

    Returns:
        OvertimeResult with shifts and weeks
    """
    if config is None:
        config = DEFAULT_CONFIG

    try:
        # Stage 1: Shift Assembly
        shifts = assemble_shifts(daily_records)

        if not shifts:
            return OvertimeResult(shifts=[], weeks=[], success=True)

        # Stage 2: Shift Assignment
        shifts = assign_shifts(shifts)

        # Stage 3: Week Classification
        weeks = classify_weeks(shifts)

        # Stage 4: Threshold Resolution
        shifts = resolve_thresholds(shifts, weeks, rest_day, district, config)

        # Stage 5: Daily OT Detection
        shifts = detect_daily_ot(shifts, config)

        # Stage 6: Weekly OT Detection
        shifts, weeks = detect_weekly_ot(shifts, weeks, config)

        # Stage 7: Rest Window Placement
        shifts, weeks = place_rest_windows(shifts, weeks, rest_day, district)

        return OvertimeResult(shifts=shifts, weeks=weeks, success=True)

    except Exception as e:
        return OvertimeResult(
            shifts=[],
            weeks=[],
            success=False,
            errors=[str(e)],
        )
