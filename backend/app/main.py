"""FastAPI application for Claims Wizard backend.

Provides REST API endpoints for:
- Running the full calculation pipeline
- Getting day/week/month snapshots from a computed SSOT
"""

from dataclasses import asdict
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from .ssot import SSOT, SSOTInput
from .pipeline import run_full_pipeline
from .errors import PipelineError
from .utils.snapshots import (
    get_day_snapshot,
    get_week_snapshot,
    get_month_snapshot,
)
from .cases import (
    save_case,
    load_case,
    list_cases,
    delete_case,
    search_cases,
    CaseMetaInfo,
    SaveResult,
    LoadResult,
)


app = FastAPI(
    title="Claims Wizard API",
    description="Israeli labor law claims calculation API",
    version="0.1.0",
)


# =============================================================================
# Serialization helpers
# =============================================================================


def _serialize_value(val: Any) -> Any:
    """Recursively serialize values for JSON output."""
    if isinstance(val, Decimal):
        return float(val)
    elif isinstance(val, date):
        return val.isoformat()
    elif isinstance(val, tuple):
        return list(val)
    elif isinstance(val, dict):
        return {k: _serialize_value(v) for k, v in val.items()}
    elif isinstance(val, list):
        return [_serialize_value(item) for item in val]
    elif hasattr(val, "__dataclass_fields__"):
        return _serialize_dataclass(val)
    elif hasattr(val, "value"):  # Enum
        return val.value
    else:
        return val


def _serialize_dataclass(obj: Any) -> dict[str, Any]:
    """Serialize a dataclass to a JSON-compatible dict."""
    if obj is None:
        return None
    result = {}
    for field_name in obj.__dataclass_fields__:
        val = getattr(obj, field_name)
        result[field_name] = _serialize_value(val)
    return result


# =============================================================================
# Request/Response models
# =============================================================================


class CalculateResponse(BaseModel):
    """Response for /calculate endpoint."""
    success: bool
    ssot: dict[str, Any] | None = None
    errors: list[dict[str, Any]] | None = None


class DaySnapshotRequest(BaseModel):
    """Request for /snapshot/day endpoint."""
    ssot: dict[str, Any]
    date: str = Field(..., description="Date in ISO format (YYYY-MM-DD)")


class WeekSnapshotRequest(BaseModel):
    """Request for /snapshot/week endpoint."""
    ssot: dict[str, Any]
    week_id: str = Field(..., description="Week ID (e.g., '2023-W20')")


class MonthSnapshotRequest(BaseModel):
    """Request for /snapshot/month endpoint."""
    ssot: dict[str, Any]
    year: int
    month: int = Field(..., ge=1, le=12)


class SnapshotResponse(BaseModel):
    """Response for snapshot endpoints."""
    success: bool
    snapshot: dict[str, Any] | None = None
    error: str | None = None


# =============================================================================
# Case management models
# =============================================================================


class CaseSaveRequest(BaseModel):
    """Request for /cases/save endpoint."""
    case_id: str = Field(..., description="Unique case identifier (UUID)")
    input: dict[str, Any] = Field(..., description="SSOT input data")
    cache: dict[str, Any] | None = Field(None, description="Optional cached computation results")


class CaseSaveResponse(BaseModel):
    """Response for /cases/save endpoint."""
    success: bool
    saved_at: str | None = None
    error: str | None = None


class CaseLoadRequest(BaseModel):
    """Request for /cases/load endpoint."""
    case_id: str = Field(..., description="Case identifier to load")


class CaseLoadResponse(BaseModel):
    """Response for /cases/load endpoint."""
    success: bool
    input: dict[str, Any] | None = None
    cache: dict[str, Any] | None = None
    needs_recalculation: bool = True
    error: str | None = None
    version_warning: str | None = None


class CaseListItem(BaseModel):
    """Single case item in list response."""
    case_id: str
    case_name: str
    worker_name: str | None = None
    defendant_name: str | None = None
    last_modified: str
    created_at: str
    has_results: bool


class CaseListResponse(BaseModel):
    """Response for /cases/list endpoint."""
    cases: list[CaseListItem]


class CaseDeleteResponse(BaseModel):
    """Response for DELETE /cases/{case_id}."""
    success: bool
    error: str | None = None


# =============================================================================
# SSOT reconstruction helpers
# =============================================================================


def _reconstruct_ssot_input(data: dict[str, Any]) -> SSOTInput:
    """Reconstruct SSOTInput from dict.

    Note: This is a minimal reconstruction for snapshot queries.
    For full pipeline execution, the frontend should send properly typed data.
    """
    from datetime import time, datetime as dt
    from .ssot import (
        CaseMetadata,
        PersonalDetails,
        DefendantDetails,
        EmploymentPeriod,
        WorkPattern,
        SalaryTier,
        SeniorityInput,
        TimeRange,
        DayShifts,
        SalaryType,
        NetOrGross,
        RestDay,
        District,
        SeniorityMethod,
        Duration,
        TerminationReason,
        PatternType,
        PatternLevelB,
        WeekPatternB,
    )

    def parse_date(val: Any) -> date | None:
        if val is None:
            return None
        if isinstance(val, date):
            return val
        if isinstance(val, str):
            return date.fromisoformat(val)
        return None

    def parse_time(val: Any) -> time | None:
        if val is None:
            return None
        if isinstance(val, time):
            return val
        if isinstance(val, str):
            return time.fromisoformat(val)
        return None

    def parse_datetime(val: Any) -> dt | None:
        if val is None:
            return None
        if isinstance(val, dt):
            return val
        if isinstance(val, str):
            return dt.fromisoformat(val)
        return None

    def parse_time_range(d: dict) -> TimeRange:
        return TimeRange(
            start_time=parse_time(d.get("start_time")),
            end_time=parse_time(d.get("end_time")),
        )

    def parse_duration(d: dict | None) -> Duration:
        if d is None:
            return Duration()
        return Duration(
            days=d.get("days", 0),
            months_decimal=Decimal(str(d.get("months_decimal", 0))),
            years_decimal=Decimal(str(d.get("years_decimal", 0))),
            months_whole=d.get("months_whole", 0),
            days_remainder=d.get("days_remainder", 0),
            years_whole=d.get("years_whole", 0),
            months_remainder=d.get("months_remainder", 0),
            display=d.get("display", ""),
        )

    def parse_day_shifts(d: dict | None) -> DayShifts | None:
        if d is None:
            return None
        return DayShifts(
            shifts=[parse_time_range(s) for s in d.get("shifts", [])],
            breaks=[parse_time_range(b) for b in d.get("breaks", [])] if d.get("breaks") else None,
        )

    def parse_employment_period(d: dict) -> EmploymentPeriod:
        return EmploymentPeriod(
            id=d.get("id", ""),
            start=parse_date(d.get("start")),
            end=parse_date(d.get("end")),
            duration=parse_duration(d.get("duration")),
        )

    def parse_week_pattern_b(d: dict) -> WeekPatternB:
        """Parse a single week in a cyclic (Level B) pattern."""
        per_day = None
        if d.get("per_day"):
            per_day = {int(k): parse_day_shifts(v) for k, v in d["per_day"].items()}
        return WeekPatternB(
            work_days=d.get("work_days", []),
            per_day=per_day,
            repeats=d.get("repeats", 1),
        )

    def parse_level_b(d: dict | None) -> PatternLevelB | None:
        """Parse Level B (cyclic) pattern configuration."""
        if d is None:
            return None
        return PatternLevelB(
            cycle_length=d.get("cycle_length", 1),
            cycle=[parse_week_pattern_b(w) for w in d.get("cycle", [])],
        )

    def parse_work_pattern(d: dict) -> WorkPattern:
        per_day = None
        if d.get("per_day"):
            per_day = {int(k): parse_day_shifts(v) for k, v in d["per_day"].items()}

        daily_overrides = None
        if d.get("daily_overrides"):
            daily_overrides = {
                parse_date(k): parse_day_shifts(v)
                for k, v in d["daily_overrides"].items()
            }

        # Parse pattern_type
        pattern_type_str = d.get("pattern_type")
        pattern_type = PatternType(pattern_type_str) if pattern_type_str else None

        return WorkPattern(
            id=d.get("id", ""),
            start=parse_date(d.get("start")),
            end=parse_date(d.get("end")),
            duration=parse_duration(d.get("duration")),
            work_days=d.get("work_days", []),
            default_shifts=[parse_time_range(s) for s in d.get("default_shifts", [])],
            default_breaks=[parse_time_range(b) for b in d.get("default_breaks", [])],
            per_day=per_day,
            daily_overrides=daily_overrides,
            pattern_type=pattern_type,
            level_b=parse_level_b(d.get("level_b")),
        )

    def parse_salary_tier(d: dict) -> SalaryTier:
        return SalaryTier(
            id=d.get("id", ""),
            start=parse_date(d.get("start")),
            end=parse_date(d.get("end")),
            duration=parse_duration(d.get("duration")),
            amount=Decimal(str(d.get("amount", 0))),
            type=SalaryType(d.get("type", "hourly")),
            net_or_gross=NetOrGross(d.get("net_or_gross", "gross")),
        )

    def parse_pattern_source(d: dict):
        """Parse pattern source for Level B/C patterns."""
        from app.modules.pattern_translator import (
            PatternSource, PatternType, PatternLevelC,
            DayTypeInput, DayType, CountPeriod,
            NightPlacement, LevelCMode
        )

        level_c_data = None
        lc = d.get("level_c_data") or d.get("level_c")
        if lc:
            day_types = []
            for dt in lc.get("day_types", []):
                day_types.append(DayTypeInput(
                    type_id=DayType(dt["type_id"]),
                    count=Decimal(str(dt.get("count", 0))),
                    count_period=CountPeriod(dt.get("count_period", "weekly")),
                    hours=Decimal(str(dt.get("hours", 0))) if dt.get("hours") is not None else None,
                    break_minutes=int(dt.get("break_minutes", 0)),
                    shifts=[parse_time_range(s) for s in dt.get("shifts", [])] if dt.get("shifts") else None,
                    breaks=[parse_time_range(b) for b in dt.get("breaks", [])] if dt.get("breaks") else None,
                ))
            level_c_data = PatternLevelC(
                id=d.get("id", ""),
                start=parse_date(d.get("start")),
                end=parse_date(d.get("end")),
                day_types=day_types,
                night_placement=NightPlacement(lc.get("night_placement", "average")),
            )

        # Parse level_b_data (cyclic patterns)
        level_b_data = None
        lb = d.get("level_b_data")
        if lb:
            from app.modules.pattern_translator import PatternLevelB
            cycle_patterns = []
            for wp in lb.get("cycle", []):
                cycle_patterns.append(parse_work_pattern(wp))
            level_b_data = PatternLevelB(
                id=d.get("id", ""),
                start=parse_date(d.get("start")),
                end=parse_date(d.get("end")),
                cycle=cycle_patterns,
                cycle_length=int(lb.get("cycle_length", len(cycle_patterns))),
            )

        return PatternSource(
            id=d.get("id", ""),
            type=PatternType(d.get("type", d.get("pattern_type", "weekly_simple"))),
            start=parse_date(d.get("start")),
            end=parse_date(d.get("end")),
            level_c_data=level_c_data,
            level_b_data=level_b_data,
        )

    def parse_lodging_input(d: dict | None):
        """Parse LodgingInput with period-based structure and visit groups."""
        from .ssot import LodgingInput, LodgingPeriod, VisitGroup
        if d is None:
            return None

        periods = []
        for p in d.get("periods", []):
            # Parse visit_groups
            visit_groups = []
            for vg in p.get("visit_groups", []):
                visit_groups.append(VisitGroup(
                    id=vg.get("id", ""),
                    nights_per_visit=int(vg.get("nights_per_visit", 1)),
                    count=int(vg.get("count", 1)),
                ))

            periods.append(LodgingPeriod(
                id=p.get("id", ""),
                start=parse_date(p.get("start")),
                end=parse_date(p.get("end")),
                snap_to=p.get("snap_to"),
                snap_ref_id=p.get("snap_ref_id"),
                pattern_type=p.get("pattern_type", "none"),
                cycle_weeks=int(p.get("cycle_weeks", 1)),
                visit_groups=visit_groups,
            ))

        return LodgingInput(periods=periods)

    # Parse main structure
    case_meta = data.get("case_metadata", {})
    personal = data.get("personal_details", {})
    defendant = data.get("defendant_details", {})
    seniority = data.get("seniority_input", {})

    return SSOTInput(
        case_metadata=CaseMetadata(
            case_name=case_meta.get("case_name", ""),
            created_at=parse_datetime(case_meta.get("created_at")),
            notes=case_meta.get("notes", ""),
        ),
        personal_details=PersonalDetails(
            id_number=personal.get("id_number"),
            first_name=personal.get("first_name"),
            last_name=personal.get("last_name"),
            birth_year=personal.get("birth_year", 0),
        ),
        defendant_details=DefendantDetails(
            name=defendant.get("name"),
            id_number=defendant.get("id_number"),
            address=defendant.get("address"),
            notes=defendant.get("notes"),
        ),
        employment_periods=[
            parse_employment_period(ep)
            for ep in data.get("employment_periods", [])
        ],
        work_patterns=[
            parse_work_pattern(wp)
            for wp in data.get("work_patterns", [])
        ],
        salary_tiers=[
            parse_salary_tier(st)
            for st in data.get("salary_tiers", [])
        ],
        rest_day=RestDay(data.get("rest_day", "saturday")),
        district=District(data.get("district", "tel_aviv")),
        industry=data.get("industry", "general"),
        filing_date=parse_date(data.get("filing_date")),
        termination_reason=TerminationReason(data["termination_reason"]) if data.get("termination_reason") else None,
        seniority_input=SeniorityInput(
            method=SeniorityMethod(seniority.get("method", "prior_plus_pattern")),
            prior_months=seniority.get("prior_months"),
            total_industry_months=seniority.get("total_industry_months"),
        ),
        right_toggles=data.get("right_toggles", {}),
        deductions_input={
            k: Decimal(str(v)) for k, v in data.get("deductions_input", {}).items()
        },
        right_specific_inputs=data.get("right_specific_inputs", {}),
        pattern_sources=[
            parse_pattern_source(ps)
            for ps in data.get("pattern_sources", [])
        ] if data.get("pattern_sources") else None,
        travel_distance_km=Decimal(str(data["travel_distance_km"])) if data.get("travel_distance_km") is not None else None,
        lodging_input=parse_lodging_input(data.get("lodging_input")),
    )


def _reconstruct_ssot(data: dict[str, Any]) -> SSOT:
    """Reconstruct SSOT from dict for snapshot queries.

    This reconstructs just enough for snapshot functions to work.
    """
    from datetime import time, datetime as dt
    from .ssot import (
        EffectivePeriod,
        EmploymentGap,
        TotalEmployment,
        DailyRecord,
        Shift,
        Week,
        PeriodMonthRecord,
        MonthAggregate,
        SeniorityMonthly,
        SeniorityTotals,
        TimeRange,
        DayShifts,
        DaySegment,
        ShiftSegment,
        PricingBreakdown,
        Duration,
        SalaryType,
        NetOrGross,
        DaySegmentType,
        WeekType,
        SeniorityMethod,
    )

    def parse_date(val: Any) -> date | None:
        if val is None:
            return None
        if isinstance(val, date):
            return val
        if isinstance(val, str):
            return date.fromisoformat(val)
        return None

    def parse_time(val: Any) -> time | None:
        if val is None:
            return None
        if isinstance(val, time):
            return val
        if isinstance(val, str):
            return time.fromisoformat(val)
        return None

    def parse_datetime(val: Any) -> dt | None:
        if val is None:
            return None
        if isinstance(val, dt):
            return val
        if isinstance(val, str):
            return dt.fromisoformat(val)
        return None

    def parse_duration(d: dict | None) -> Duration:
        if d is None:
            return Duration()
        return Duration(
            days=d.get("days", 0),
            months_decimal=Decimal(str(d.get("months_decimal", 0))),
            years_decimal=Decimal(str(d.get("years_decimal", 0))),
            months_whole=d.get("months_whole", 0),
            days_remainder=d.get("days_remainder", 0),
            years_whole=d.get("years_whole", 0),
            months_remainder=d.get("months_remainder", 0),
            display=d.get("display", ""),
        )

    def parse_time_range(d: dict) -> TimeRange:
        return TimeRange(
            start_time=parse_time(d.get("start_time")),
            end_time=parse_time(d.get("end_time")),
        )

    def parse_day_shifts(d: dict | None) -> DayShifts | None:
        if d is None:
            return None
        return DayShifts(
            shifts=[parse_time_range(s) for s in d.get("shifts", [])],
            breaks=[parse_time_range(b) for b in d.get("breaks", [])] if d.get("breaks") else None,
        )

    def parse_month_tuple(val: Any) -> tuple[int, int]:
        if isinstance(val, (list, tuple)) and len(val) == 2:
            return (int(val[0]), int(val[1]))
        return (0, 0)

    def parse_effective_period(d: dict) -> EffectivePeriod:
        per_day = None
        if d.get("pattern_per_day"):
            per_day = {int(k): parse_day_shifts(v) for k, v in d["pattern_per_day"].items()}

        daily_overrides = None
        if d.get("pattern_daily_overrides"):
            daily_overrides = {
                parse_date(k): parse_day_shifts(v)
                for k, v in d["pattern_daily_overrides"].items()
            }

        return EffectivePeriod(
            id=d.get("id", ""),
            start=parse_date(d.get("start")),
            end=parse_date(d.get("end")),
            duration=parse_duration(d.get("duration")),
            employment_period_id=d.get("employment_period_id", ""),
            work_pattern_id=d.get("work_pattern_id", ""),
            salary_tier_id=d.get("salary_tier_id", ""),
            pattern_work_days=d.get("pattern_work_days", []),
            pattern_default_shifts=[parse_time_range(s) for s in d.get("pattern_default_shifts", [])],
            pattern_default_breaks=[parse_time_range(b) for b in d.get("pattern_default_breaks", [])],
            pattern_per_day=per_day,
            pattern_daily_overrides=daily_overrides,
            salary_amount=Decimal(str(d.get("salary_amount", 0))),
            salary_type=SalaryType(d.get("salary_type", "hourly")),
            salary_net_or_gross=NetOrGross(d.get("salary_net_or_gross", "gross")),
        )

    def parse_daily_record(d: dict) -> DailyRecord:
        day_segments = None
        if d.get("day_segments"):
            day_segments = [
                DaySegment(
                    start=parse_time(seg.get("start")),
                    end=parse_time(seg.get("end")),
                    type=DaySegmentType(seg.get("type", "regular")),
                )
                for seg in d["day_segments"]
            ]

        return DailyRecord(
            date=parse_date(d.get("date")),
            effective_period_id=d.get("effective_period_id", ""),
            day_of_week=d.get("day_of_week", 0),
            is_work_day=d.get("is_work_day", False),
            is_rest_day=d.get("is_rest_day", False),
            shift_templates=[parse_time_range(s) for s in d.get("shift_templates", [])],
            break_templates=[parse_time_range(b) for b in d.get("break_templates", [])],
            day_segments=day_segments,
        )

    def parse_shift(d: dict) -> Shift:
        segments = [
            ShiftSegment(
                start=parse_datetime(seg.get("start")),
                end=parse_datetime(seg.get("end")),
            )
            for seg in d.get("segments", [])
        ]

        breaks = [
            ShiftSegment(
                start=parse_datetime(b.get("start")),
                end=parse_datetime(b.get("end")),
            )
            for b in d.get("breaks", [])
        ]

        pricing_breakdown = None
        if d.get("pricing_breakdown"):
            pricing_breakdown = [
                PricingBreakdown(
                    hours=Decimal(str(pb.get("hours", 0))),
                    tier=pb.get("tier", 0),
                    in_rest=pb.get("in_rest", False),
                    rate_multiplier=Decimal(str(pb.get("rate_multiplier", 1))),
                    claim_multiplier=Decimal(str(pb.get("claim_multiplier", 0))),
                    hourly_wage=Decimal(str(pb.get("hourly_wage", 0))),
                    claim_amount=Decimal(str(pb.get("claim_amount", 0))),
                )
                for pb in d["pricing_breakdown"]
            ]

        return Shift(
            id=d.get("id", ""),
            date=parse_date(d.get("date")),
            shift_index=d.get("shift_index", 0),
            effective_period_id=d.get("effective_period_id", ""),
            start=parse_datetime(d.get("start")),
            end=parse_datetime(d.get("end")),
            segments=segments,
            breaks=breaks,
            net_hours=Decimal(str(d.get("net_hours", 0))),
            assigned_day=parse_date(d.get("assigned_day")),
            assigned_week=d.get("assigned_week", ""),
            threshold=Decimal(str(d.get("threshold", 0))),
            threshold_reason=d.get("threshold_reason", ""),
            regular_hours=Decimal(str(d.get("regular_hours", 0))),
            ot_tier1_hours=Decimal(str(d.get("ot_tier1_hours", 0))),
            ot_tier2_hours=Decimal(str(d.get("ot_tier2_hours", 0))),
            daily_ot_hours=Decimal(str(d.get("daily_ot_hours", 0))),
            weekly_ot_hours=Decimal(str(d.get("weekly_ot_hours", 0))),
            rest_window_regular_hours=Decimal(str(d.get("rest_window_regular_hours", 0))),
            rest_window_ot_tier1_hours=Decimal(str(d.get("rest_window_ot_tier1_hours", 0))),
            rest_window_ot_tier2_hours=Decimal(str(d.get("rest_window_ot_tier2_hours", 0))),
            non_rest_regular_hours=Decimal(str(d.get("non_rest_regular_hours", 0))),
            non_rest_ot_tier1_hours=Decimal(str(d.get("non_rest_ot_tier1_hours", 0))),
            non_rest_ot_tier2_hours=Decimal(str(d.get("non_rest_ot_tier2_hours", 0))),
            claim_amount=Decimal(str(d.get("claim_amount", 0))) if d.get("claim_amount") is not None else None,
            pricing_breakdown=pricing_breakdown,
        )

    def parse_week(d: dict) -> Week:
        return Week(
            id=d.get("id", ""),
            year=d.get("year", 0),
            week_number=d.get("week_number", 0),
            start_date=parse_date(d.get("start_date")),
            end_date=parse_date(d.get("end_date")),
            distinct_work_days=d.get("distinct_work_days", 0),
            week_type=WeekType(d.get("week_type", 5)),
            total_regular_hours=Decimal(str(d.get("total_regular_hours", 0))),
            weekly_ot_hours=Decimal(str(d.get("weekly_ot_hours", 0))),
            weekly_threshold=Decimal(str(d.get("weekly_threshold", 42))),
            rest_window_start=parse_datetime(d.get("rest_window_start")),
            rest_window_end=parse_datetime(d.get("rest_window_end")),
            rest_window_work_hours=Decimal(str(d.get("rest_window_work_hours", 0))),
            is_partial=d.get("is_partial", False),
            partial_reason=d.get("partial_reason"),
            partial_detail=d.get("partial_detail"),
        )

    def parse_period_month_record(d: dict) -> PeriodMonthRecord:
        return PeriodMonthRecord(
            effective_period_id=d.get("effective_period_id", ""),
            month=parse_month_tuple(d.get("month", [0, 0])),
            work_days_count=d.get("work_days_count", 0),
            shifts_count=d.get("shifts_count", 0),
            total_regular_hours=Decimal(str(d.get("total_regular_hours", 0))),
            total_ot_hours=Decimal(str(d.get("total_ot_hours", 0))),
            avg_regular_hours_per_day=Decimal(str(d.get("avg_regular_hours_per_day", 0))),
            avg_regular_hours_per_shift=Decimal(str(d.get("avg_regular_hours_per_shift", 0))),
            salary_input_amount=Decimal(str(d.get("salary_input_amount", 0))),
            salary_input_type=SalaryType(d.get("salary_input_type", "hourly")),
            salary_input_net_or_gross=NetOrGross(d.get("salary_input_net_or_gross", "gross")),
            salary_gross_amount=Decimal(str(d.get("salary_gross_amount", 0))),
            minimum_wage_value=Decimal(str(d.get("minimum_wage_value", 0))),
            minimum_wage_type=d.get("minimum_wage_type", ""),
            minimum_applied=d.get("minimum_applied", False),
            minimum_gap=Decimal(str(d.get("minimum_gap", 0))),
            effective_amount=Decimal(str(d.get("effective_amount", 0))),
            salary_hourly=Decimal(str(d.get("salary_hourly", 0))),
            salary_daily=Decimal(str(d.get("salary_daily", 0))),
            salary_monthly=Decimal(str(d.get("salary_monthly", 0))),
        )

    def parse_month_aggregate(d: dict) -> MonthAggregate:
        return MonthAggregate(
            month=parse_month_tuple(d.get("month", [0, 0])),
            total_regular_hours=Decimal(str(d.get("total_regular_hours", 0))),
            total_ot_hours=Decimal(str(d.get("total_ot_hours", 0))),
            total_work_days=d.get("total_work_days", 0),
            total_shifts=d.get("total_shifts", 0),
            full_time_hours_base=Decimal(str(d.get("full_time_hours_base", 182))),
            raw_scope=Decimal(str(d.get("raw_scope", 0))),
            job_scope=Decimal(str(d.get("job_scope", 0))),
        )

    def parse_seniority_monthly(d: dict) -> SeniorityMonthly:
        return SeniorityMonthly(
            month=parse_month_tuple(d.get("month", [0, 0])),
            worked=d.get("worked", False),
            at_defendant_cumulative=d.get("at_defendant_cumulative", 0),
            at_defendant_years_cumulative=Decimal(str(d.get("at_defendant_years_cumulative", 0))),
            total_industry_cumulative=d.get("total_industry_cumulative", 0),
            total_industry_years_cumulative=Decimal(str(d.get("total_industry_years_cumulative", 0))),
        )

    def parse_employment_gap(d: dict) -> EmploymentGap:
        return EmploymentGap(
            start=parse_date(d.get("start")),
            end=parse_date(d.get("end")),
            duration=parse_duration(d.get("duration")),
            before_period_id=d.get("before_period_id", ""),
            after_period_id=d.get("after_period_id", ""),
        )

    def parse_total_employment(d: dict | None) -> TotalEmployment:
        if d is None:
            return TotalEmployment()
        return TotalEmployment(
            first_day=parse_date(d.get("first_day")),
            last_day=parse_date(d.get("last_day")),
            total_duration=parse_duration(d.get("total_duration")),
            worked_duration=parse_duration(d.get("worked_duration")),
            gap_duration=parse_duration(d.get("gap_duration")),
            periods_count=d.get("periods_count", 0),
            gaps_count=d.get("gaps_count", 0),
        )

    def parse_seniority_totals(d: dict | None) -> SeniorityTotals:
        if d is None:
            return SeniorityTotals()
        return SeniorityTotals(
            input_method=SeniorityMethod(d.get("input_method", "prior_plus_pattern")),
            prior_seniority_months=d.get("prior_seniority_months", 0),
            at_defendant_months=d.get("at_defendant_months", 0),
            at_defendant_years=Decimal(str(d.get("at_defendant_years", 0))),
            total_industry_months=d.get("total_industry_months", 0),
            total_industry_years=Decimal(str(d.get("total_industry_years", 0))),
        )

    # Build the SSOT
    ssot = SSOT()

    # Layer 0 - Input
    if data.get("input"):
        ssot.input = _reconstruct_ssot_input(data["input"])

    # Layer 1 - Weaver output
    ssot.effective_periods = [
        parse_effective_period(ep) for ep in data.get("effective_periods", [])
    ]
    ssot.employment_gaps = [
        parse_employment_gap(g) for g in data.get("employment_gaps", [])
    ]
    ssot.total_employment = parse_total_employment(data.get("total_employment"))

    # Layer 2 - Daily records and shifts
    ssot.daily_records = [
        parse_daily_record(dr) for dr in data.get("daily_records", [])
    ]
    ssot.shifts = [
        parse_shift(s) for s in data.get("shifts", [])
    ]
    ssot.weeks = [
        parse_week(w) for w in data.get("weeks", [])
    ]

    # Layer 3 - Period×Month records
    ssot.period_month_records = [
        parse_period_month_record(pmr) for pmr in data.get("period_month_records", [])
    ]

    # Layer 4 - Monthly aggregates and seniority
    ssot.month_aggregates = [
        parse_month_aggregate(ma) for ma in data.get("month_aggregates", [])
    ]
    ssot.seniority_monthly = [
        parse_seniority_monthly(sm) for sm in data.get("seniority_monthly", [])
    ]
    ssot.seniority_totals = parse_seniority_totals(data.get("seniority_totals"))

    return ssot


# =============================================================================
# Endpoints
# =============================================================================


@app.post("/calculate", response_model=CalculateResponse)
async def calculate(input_data: dict[str, Any]) -> CalculateResponse:
    """Run the full calculation pipeline.

    Receives SSOT.input as JSON, runs run_full_pipeline, returns full SSOT.

    PipelineError is returned as 400 with Hebrew error messages.
    """
    try:
        # Reconstruct SSOTInput from dict
        ssot_input = _reconstruct_ssot_input(input_data)

        # Run the pipeline
        result = run_full_pipeline(ssot_input)

        if result.success:
            return CalculateResponse(
                success=True,
                ssot=_serialize_dataclass(result.ssot),
            )
        else:
            # Pipeline returned an error
            error = result.error
            errors = [
                {
                    "type": ve.type,
                    "message": ve.message,
                    "details": ve.details,
                }
                for ve in error.errors
            ]
            raise HTTPException(
                status_code=400,
                detail={
                    "phase": error.phase,
                    "module": error.module,
                    "errors": errors,
                },
            )
    except HTTPException:
        raise
    except PipelineError as e:
        errors = [
            {
                "type": ve.type,
                "message": ve.message,
                "details": ve.details,
            }
            for ve in e.errors
        ]
        raise HTTPException(
            status_code=400,
            detail={
                "phase": e.phase,
                "module": e.module,
                "errors": errors,
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={
                "phase": "api",
                "module": "main.py",
                "errors": [
                    {
                        "type": "parse_error",
                        "message": f"שגיאה בפענוח הקלט: {str(e)}",
                        "details": {},
                    }
                ],
            },
        )


@app.post("/snapshot/day", response_model=SnapshotResponse)
async def snapshot_day(request: DaySnapshotRequest) -> SnapshotResponse:
    """Get a day snapshot from a computed SSOT.

    Args:
        request: Contains the SSOT and target date

    Returns:
        SnapshotResponse with the day snapshot
    """
    try:
        ssot = _reconstruct_ssot(request.ssot)
        target_date = date.fromisoformat(request.date)

        snapshot = get_day_snapshot(ssot, target_date)

        return SnapshotResponse(
            success=True,
            snapshot=_serialize_dataclass(snapshot),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "phase": "snapshot",
                "module": "main.py",
                "errors": [
                    {
                        "type": "invalid_date",
                        "message": f"תאריך לא תקין: {str(e)}",
                        "details": {},
                    }
                ],
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={
                "phase": "snapshot",
                "module": "main.py",
                "errors": [
                    {
                        "type": "snapshot_error",
                        "message": f"שגיאה ביצירת snapshot: {str(e)}",
                        "details": {},
                    }
                ],
            },
        )


@app.post("/snapshot/week", response_model=SnapshotResponse)
async def snapshot_week(request: WeekSnapshotRequest) -> SnapshotResponse:
    """Get a week snapshot from a computed SSOT.

    Args:
        request: Contains the SSOT and week ID

    Returns:
        SnapshotResponse with the week snapshot
    """
    try:
        ssot = _reconstruct_ssot(request.ssot)

        snapshot = get_week_snapshot(ssot, request.week_id)

        return SnapshotResponse(
            success=True,
            snapshot=_serialize_dataclass(snapshot),
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={
                "phase": "snapshot",
                "module": "main.py",
                "errors": [
                    {
                        "type": "snapshot_error",
                        "message": f"שגיאה ביצירת snapshot: {str(e)}",
                        "details": {},
                    }
                ],
            },
        )


@app.post("/snapshot/month", response_model=SnapshotResponse)
async def snapshot_month(request: MonthSnapshotRequest) -> SnapshotResponse:
    """Get a month snapshot from a computed SSOT.

    Args:
        request: Contains the SSOT, year and month

    Returns:
        SnapshotResponse with the month snapshot
    """
    try:
        ssot = _reconstruct_ssot(request.ssot)

        snapshot = get_month_snapshot(ssot, request.year, request.month)

        return SnapshotResponse(
            success=True,
            snapshot=_serialize_dataclass(snapshot),
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={
                "phase": "snapshot",
                "module": "main.py",
                "errors": [
                    {
                        "type": "snapshot_error",
                        "message": f"שגיאה ביצירת snapshot: {str(e)}",
                        "details": {},
                    }
                ],
            },
        )


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


# =============================================================================
# Case management endpoints
# =============================================================================


@app.post("/cases/save", response_model=CaseSaveResponse)
async def save_case_endpoint(request: CaseSaveRequest) -> CaseSaveResponse:
    """Save a case to disk.

    Saves the input data and optional cache (computed results).
    If cache is provided with valid input_hash, loading will skip recalculation.
    """
    result = save_case(
        case_id=request.case_id,
        input_data=request.input,
        cache=request.cache,
    )
    return CaseSaveResponse(
        success=result.success,
        saved_at=result.saved_at if result.success else None,
        error=result.error,
    )


@app.post("/cases/load", response_model=CaseLoadResponse)
async def load_case_endpoint(request: CaseLoadRequest) -> CaseLoadResponse:
    """Load a case from disk.

    Returns input data and optionally cached results.
    If needs_recalculation is True, the frontend should trigger /calculate.
    """
    result = load_case(request.case_id)
    return CaseLoadResponse(
        success=result.success,
        input=result.input,
        cache=result.cache,
        needs_recalculation=result.needs_recalculation,
        error=result.error,
        version_warning=result.version_warning,
    )


@app.get("/cases/list", response_model=CaseListResponse)
async def list_cases_endpoint() -> CaseListResponse:
    """List all cases with metadata.

    Returns cases sorted by last_modified (newest first).
    """
    cases = list_cases()
    return CaseListResponse(
        cases=[
            CaseListItem(
                case_id=c.case_id,
                case_name=c.case_name,
                worker_name=c.worker_name,
                defendant_name=c.defendant_name,
                last_modified=c.last_modified,
                created_at=c.created_at,
                has_results=c.has_results,
            )
            for c in cases
        ]
    )


@app.delete("/cases/{case_id}", response_model=CaseDeleteResponse)
async def delete_case_endpoint(case_id: str) -> CaseDeleteResponse:
    """Delete a case.

    Permanently removes the case file from disk.
    """
    success = delete_case(case_id)
    if success:
        return CaseDeleteResponse(success=True)
    else:
        return CaseDeleteResponse(success=False, error=f"Case not found: {case_id}")


@app.get("/cases/search", response_model=CaseListResponse)
async def search_cases_endpoint(
    q: str = Query(..., min_length=1, description="Search query")
) -> CaseListResponse:
    """Search cases by name, worker name, or defendant name.

    Returns matching cases sorted by last_modified.
    """
    cases = search_cases(q)
    return CaseListResponse(
        cases=[
            CaseListItem(
                case_id=c.case_id,
                case_name=c.case_name,
                worker_name=c.worker_name,
                defendant_name=c.defendant_name,
                last_modified=c.last_modified,
                created_at=c.created_at,
                has_results=c.has_results,
            )
            for c in cases
        ]
    )
