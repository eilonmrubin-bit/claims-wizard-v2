"""Weaver Orchestrator - Single entry point for the Weaver module.

Coordinates the 4 engines:
1. Validator - validates input axes
2. Sweep - creates effective periods via sweep line algorithm
3. DailyRecords - generates daily records for each day
4. Gaps - detects employment gaps and computes total employment

The orchestrator is a pure function - it receives input and returns output.
Only pipeline.py writes to SSOT.
"""

from dataclasses import dataclass, field
from typing import Any

from app.ssot import (
    EffectivePeriod,
    DailyRecord,
    EmploymentGap,
    TotalEmployment,
)

from .validator import validate, ValidationError
from .sweep import sweep
from .daily_records import generate_daily_records
from .gaps import detect_gaps, compute_total_employment


@dataclass
class WeaverResult:
    """Result of running the weaver."""
    success: bool
    effective_periods: list[EffectivePeriod] = field(default_factory=list)
    daily_records: list[DailyRecord] = field(default_factory=list)
    employment_gaps: list[EmploymentGap] = field(default_factory=list)
    total_employment: TotalEmployment = field(default_factory=TotalEmployment)
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)


def run_weaver(
    employment_periods: list[Any],
    work_patterns: list[Any],
    salary_tiers: list[Any],
    rest_day: str = "saturday"
) -> WeaverResult:
    """Run the complete weaver pipeline.

    Args:
        employment_periods: List of EmploymentPeriod objects
        work_patterns: List of WorkPattern objects
        salary_tiers: List of SalaryTier objects
        rest_day: Rest day ("saturday", "friday", or "sunday")

    Returns:
        WeaverResult with all outputs or errors
    """
    # Stage 1: Validation
    errors, warnings = validate(
        employment_periods,
        work_patterns,
        salary_tiers,
        rest_day
    )

    if errors:
        return WeaverResult(
            success=False,
            errors=errors,
            warnings=warnings,
        )

    # Stage 2: Sweep line - create effective periods
    effective_periods = sweep(
        employment_periods,
        work_patterns,
        salary_tiers
    )

    # Stage 3: Generate daily records
    daily_records = generate_daily_records(effective_periods, rest_day)

    # Stage 4: Detect gaps and compute total employment
    employment_gaps = detect_gaps(employment_periods)
    total_employment = compute_total_employment(employment_periods, employment_gaps)

    return WeaverResult(
        success=True,
        effective_periods=effective_periods,
        daily_records=daily_records,
        employment_gaps=employment_gaps,
        total_employment=total_employment,
        errors=[],
        warnings=warnings,
    )
