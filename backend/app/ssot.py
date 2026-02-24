"""SSOT (Single Source of Truth) data structures for Claims Wizard.

This module defines all data structures used throughout the pipeline.
See docs/skills/ssot/SKILL.md for complete documentation.
"""

from dataclasses import dataclass, field
from datetime import date, time, datetime
from decimal import Decimal
from enum import Enum
from typing import Any


# =============================================================================
# Enums
# =============================================================================

class SalaryType(str, Enum):
    HOURLY = "hourly"
    DAILY = "daily"
    MONTHLY = "monthly"
    PER_SHIFT = "per_shift"


class NetOrGross(str, Enum):
    NET = "net"
    GROSS = "gross"


class RestDay(str, Enum):
    SATURDAY = "saturday"
    FRIDAY = "friday"
    SUNDAY = "sunday"


class District(str, Enum):
    JERUSALEM = "jerusalem"
    TEL_AVIV = "tel_aviv"
    HAIFA = "haifa"
    SOUTH = "south"
    GALIL = "galil"


class SeniorityMethod(str, Enum):
    PRIOR_PLUS_PATTERN = "prior_plus_pattern"
    MANUAL = "manual"
    MATASH_PDF = "matash_pdf"


class DaySegmentType(str, Enum):
    REGULAR = "regular"
    EVE_OF_REST = "eve_of_rest"
    REST = "rest"


class WeekType(int, Enum):
    FIVE_DAY = 5
    SIX_DAY = 6


# =============================================================================
# Duration - Common type for all period calculations
# =============================================================================

@dataclass
class Duration:
    """Duration with multiple representations.

    Numeric values are computed by the module creating the period.
    Display string is filled by the Duration formatter in Phase 4.
    """
    days: int = 0
    months_decimal: Decimal = Decimal("0")
    years_decimal: Decimal = Decimal("0")
    months_whole: int = 0
    days_remainder: int = 0
    years_whole: int = 0
    months_remainder: int = 0
    display: str = ""  # Filled by Phase 4 formatter


# =============================================================================
# Layer 0 - Input (saved to .case file)
# =============================================================================

@dataclass
class CaseMetadata:
    case_name: str = ""
    created_at: datetime | None = None
    notes: str = ""


@dataclass
class PersonalDetails:
    id_number: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    birth_year: int = 0  # Required - rights depend on age


@dataclass
class DefendantDetails:
    name: str | None = None
    id_number: str | None = None
    address: str | None = None
    notes: str | None = None


@dataclass
class TimeRange:
    start_time: time
    end_time: time


@dataclass
class EmploymentPeriod:
    id: str
    start: date
    end: date
    duration: Duration = field(default_factory=Duration)


@dataclass
class DayShifts:
    shifts: list[TimeRange] = field(default_factory=list)
    breaks: list[TimeRange] | None = None


@dataclass
class WorkPattern:
    id: str
    start: date
    end: date
    duration: Duration = field(default_factory=Duration)
    work_days: list[int] = field(default_factory=list)  # 0=Sunday..6=Saturday
    default_shifts: list[TimeRange] = field(default_factory=list)
    default_breaks: list[TimeRange] = field(default_factory=list)
    per_day: dict[int, DayShifts] | None = None  # Key: day of week
    daily_overrides: dict[date, DayShifts] | None = None  # Key: specific date


@dataclass
class SalaryTier:
    id: str
    start: date
    end: date
    duration: Duration = field(default_factory=Duration)
    amount: Decimal = Decimal("0")
    type: SalaryType = SalaryType.HOURLY
    net_or_gross: NetOrGross = NetOrGross.GROSS


@dataclass
class SeniorityInput:
    method: SeniorityMethod = SeniorityMethod.PRIOR_PLUS_PATTERN
    prior_months: int | None = None  # Method A
    manual_industry_months: int | None = None  # Method B
    manual_defendant_months: int | None = None  # Method B
    matash_file: bytes | None = None  # Method C


@dataclass
class SSOTInput:
    """Layer 0 - All user input. Saved to .case file."""

    case_metadata: CaseMetadata = field(default_factory=CaseMetadata)
    personal_details: PersonalDetails = field(default_factory=PersonalDetails)
    defendant_details: DefendantDetails = field(default_factory=DefendantDetails)

    # Three input axes
    employment_periods: list[EmploymentPeriod] = field(default_factory=list)
    work_patterns: list[WorkPattern] = field(default_factory=list)
    salary_tiers: list[SalaryTier] = field(default_factory=list)

    # Simple inputs
    rest_day: RestDay = RestDay.SATURDAY
    district: District = District.TEL_AVIV
    industry: str = "general"
    filing_date: date | None = None

    # Seniority
    seniority_input: SeniorityInput = field(default_factory=SeniorityInput)

    # Toggles and deductions
    right_toggles: dict[str, dict[str, bool]] = field(default_factory=dict)
    deductions_input: dict[str, Decimal] = field(default_factory=dict)
    right_specific_inputs: dict[str, dict[str, Any]] = field(default_factory=dict)


# =============================================================================
# Layer 1 - Weaver output
# =============================================================================

@dataclass
class EffectivePeriod:
    """Atomic period with single work pattern and salary tier."""
    id: str
    start: date
    end: date
    duration: Duration = field(default_factory=Duration)
    employment_period_id: str = ""
    work_pattern_id: str = ""
    salary_tier_id: str = ""

    # Denormalized from axes
    pattern_work_days: list[int] = field(default_factory=list)
    pattern_default_shifts: list[TimeRange] = field(default_factory=list)
    pattern_default_breaks: list[TimeRange] = field(default_factory=list)
    pattern_per_day: dict[int, DayShifts] | None = None
    pattern_daily_overrides: dict[date, DayShifts] | None = None
    salary_amount: Decimal = Decimal("0")
    salary_type: SalaryType = SalaryType.HOURLY
    salary_net_or_gross: NetOrGross = NetOrGross.GROSS


@dataclass
class EmploymentGap:
    """Gap between employment periods."""
    start: date
    end: date
    duration: Duration = field(default_factory=Duration)
    before_period_id: str = ""
    after_period_id: str = ""


@dataclass
class TotalEmployment:
    """Summary of entire employment period."""
    first_day: date | None = None
    last_day: date | None = None
    total_duration: Duration = field(default_factory=Duration)
    worked_duration: Duration = field(default_factory=Duration)
    gap_duration: Duration = field(default_factory=Duration)
    periods_count: int = 0
    gaps_count: int = 0


# =============================================================================
# Layer 2 - Daily records and shifts
# =============================================================================

@dataclass
class DaySegment:
    """Segment of a day with specific type (regular/eve_of_rest/rest)."""
    start: time
    end: time
    type: DaySegmentType = DaySegmentType.REGULAR


@dataclass
class DailyRecord:
    """Single day record with templates and segments."""
    date: date
    effective_period_id: str = ""
    day_of_week: int = 0  # 0=Sunday..6=Saturday
    is_work_day: bool = False
    is_rest_day: bool = False

    shift_templates: list[TimeRange] = field(default_factory=list)
    break_templates: list[TimeRange] = field(default_factory=list)
    day_segments: list[DaySegment] | None = None  # Filled by OT stage 3.5


@dataclass
class ShiftSegment:
    """Work segment within a shift."""
    start: datetime
    end: datetime


@dataclass
class PricingBreakdown:
    """Pricing breakdown for a shift segment."""
    hours: Decimal = Decimal("0")
    tier: int = 0  # 0, 1, or 2
    in_rest: bool = False
    rate_multiplier: Decimal = Decimal("1")  # 1.00/1.25/1.50/1.75/2.00
    claim_multiplier: Decimal = Decimal("0")  # 0.00/0.25/0.50/0.75/1.00
    hourly_wage: Decimal = Decimal("0")
    claim_amount: Decimal = Decimal("0")


@dataclass
class Shift:
    """Single shift with all OT calculations."""
    id: str
    date: date
    shift_index: int = 0
    effective_period_id: str = ""
    week_id: str = ""

    # Stage 1 - Assembly
    start: datetime | None = None
    end: datetime | None = None
    segments: list[ShiftSegment] = field(default_factory=list)
    breaks: list[ShiftSegment] = field(default_factory=list)
    net_hours: Decimal = Decimal("0")

    # Stage 2 - Assignment
    assigned_day: date | None = None
    assigned_week: str = ""

    # Stage 4 - Threshold
    threshold: Decimal = Decimal("0")
    threshold_reason: str = ""

    # Stage 5 - Daily OT
    regular_hours: Decimal = Decimal("0")
    ot_tier1_hours: Decimal = Decimal("0")
    ot_tier2_hours: Decimal = Decimal("0")
    daily_ot_hours: Decimal = Decimal("0")
    weekly_ot_hours: Decimal = Decimal("0")

    # Stage 7 - Rest window
    rest_window_regular_hours: Decimal = Decimal("0")
    rest_window_ot_tier1_hours: Decimal = Decimal("0")
    rest_window_ot_tier2_hours: Decimal = Decimal("0")
    non_rest_regular_hours: Decimal = Decimal("0")
    non_rest_ot_tier1_hours: Decimal = Decimal("0")
    non_rest_ot_tier2_hours: Decimal = Decimal("0")

    # Stage 8 - Pricing (filled in Phase 2)
    claim_amount: Decimal | None = None
    pricing_breakdown: list[PricingBreakdown] | None = None


@dataclass
class Week:
    """Week record with classification and OT."""
    id: str  # e.g., "2024-W15"
    year: int = 0
    week_number: int = 0
    start_date: date | None = None
    end_date: date | None = None

    # Stage 3 - Classification
    distinct_work_days: int = 0
    week_type: WeekType = WeekType.FIVE_DAY

    # Stage 6 - Weekly OT
    total_regular_hours: Decimal = Decimal("0")
    weekly_ot_hours: Decimal = Decimal("0")
    weekly_threshold: Decimal = Decimal("42")

    # Stage 7 - Rest window
    rest_window_start: datetime | None = None
    rest_window_end: datetime | None = None
    rest_window_work_hours: Decimal = Decimal("0")

    # Partial week
    is_partial: bool = False
    partial_reason: str | None = None
    partial_detail: str | None = None


# =============================================================================
# Layer 3 - Period×Month records
# =============================================================================

@dataclass
class PeriodMonthRecord:
    """Aggregation for a specific effective_period × calendar month."""
    effective_period_id: str = ""
    month: tuple[int, int] = (0, 0)  # (year, month)

    # Hours - from Aggregator
    work_days_count: int = 0
    shifts_count: int = 0
    total_regular_hours: Decimal = Decimal("0")
    total_ot_hours: Decimal = Decimal("0")
    avg_regular_hours_per_day: Decimal = Decimal("0")
    avg_regular_hours_per_shift: Decimal = Decimal("0")

    # Salary - from Salary Conversion
    salary_input_amount: Decimal = Decimal("0")
    salary_input_type: SalaryType = SalaryType.HOURLY
    salary_input_net_or_gross: NetOrGross = NetOrGross.GROSS
    salary_gross_amount: Decimal = Decimal("0")

    # Minimum wage check
    minimum_wage_value: Decimal = Decimal("0")
    minimum_wage_type: str = ""
    minimum_applied: bool = False
    minimum_gap: Decimal = Decimal("0")
    effective_amount: Decimal = Decimal("0")

    # Processed salary
    salary_hourly: Decimal = Decimal("0")
    salary_daily: Decimal = Decimal("0")
    salary_monthly: Decimal = Decimal("0")


# =============================================================================
# Layer 4 - Monthly aggregates and seniority
# =============================================================================

@dataclass
class MonthAggregate:
    """Monthly aggregation across all periods."""
    month: tuple[int, int] = (0, 0)  # (year, month)

    # Hours - from Aggregator
    total_regular_hours: Decimal = Decimal("0")
    total_ot_hours: Decimal = Decimal("0")
    total_work_days: int = 0
    total_shifts: int = 0

    # Job scope
    full_time_hours_base: Decimal = Decimal("182")
    raw_scope: Decimal = Decimal("0")
    job_scope: Decimal = Decimal("0")  # min(raw_scope, 1.0)


@dataclass
class SeniorityMonthly:
    """Monthly seniority record."""
    month: tuple[int, int] = (0, 0)
    worked: bool = False
    at_defendant_cumulative: int = 0
    at_defendant_years_cumulative: Decimal = Decimal("0")
    total_industry_cumulative: int = 0
    total_industry_years_cumulative: Decimal = Decimal("0")


@dataclass
class MatashRecord:
    """Record extracted from MATASH PDF."""
    employer_name: str = ""
    start_date: date | None = None
    end_date: date | None = None
    duration: Duration = field(default_factory=Duration)
    industry: str = ""
    is_defendant: bool = False
    is_relevant_industry: bool = False
    months_counted: int = 0


@dataclass
class SeniorityTotals:
    """Total seniority summary."""
    input_method: SeniorityMethod = SeniorityMethod.PRIOR_PLUS_PATTERN
    prior_seniority_months: int = 0
    at_defendant_months: int = 0
    at_defendant_years: Decimal = Decimal("0")
    total_industry_months: int = 0
    total_industry_years: Decimal = Decimal("0")
    matash_records: list[MatashRecord] | None = None


# =============================================================================
# Layer 5 - Rights results (Phase 2)
# =============================================================================

@dataclass
class OvertimeMonthlyBreakdown:
    month: tuple[int, int] = (0, 0)
    claim_amount: Decimal = Decimal("0")
    regular_hours: Decimal = Decimal("0")
    ot_hours: Decimal = Decimal("0")
    shifts_count: int = 0


@dataclass
class OvertimeResult:
    total_claim: Decimal = Decimal("0")
    monthly_breakdown: list[OvertimeMonthlyBreakdown] = field(default_factory=list)


@dataclass
class HolidayEntry:
    name: str = ""
    hebrew_date: str = ""
    gregorian_date: date | None = None
    employed_on_date: bool = False
    day_of_week: str = ""
    week_type: WeekType = WeekType.FIVE_DAY
    is_rest_day: bool = False
    is_eve_of_rest: bool = False
    excluded: bool = False
    exclude_reason: str | None = None
    entitled: bool = False
    day_value: Decimal | None = None
    claim_amount: Decimal | None = None


@dataclass
class HolidayYearResult:
    year: int = 0
    met_threshold: bool = False
    employment_days_in_year: int = 0
    holidays: list[HolidayEntry] = field(default_factory=list)
    election_day_entitled: bool = False
    total_entitled_days: int = 0
    total_claim: Decimal = Decimal("0")


@dataclass
class HolidaysResult:
    per_year: list[HolidayYearResult] = field(default_factory=list)
    grand_total_days: int = 0
    grand_total_claim: Decimal = Decimal("0")


@dataclass
class RightsResults:
    """Results for all rights (Phase 2)."""
    overtime: OvertimeResult | None = None
    holidays: HolidaysResult | None = None
    vacation: Any | None = None  # Not yet defined
    severance: Any | None = None  # Not yet defined
    pension: Any | None = None  # Not yet defined
    recreation: Any | None = None  # Not yet defined
    salary_completion: Any | None = None  # Not yet defined
    travel: Any | None = None  # Not yet defined


# =============================================================================
# Layer 6 - Limitation results (Phase 3)
# =============================================================================

@dataclass
class FreezePeriodApplied:
    name: str = ""
    start_date: date | None = None
    end_date: date | None = None
    days: int = 0
    duration: Duration = field(default_factory=Duration)


@dataclass
class LimitationWindow:
    type_id: str = ""
    type_name: str = ""
    base_window_start: date | None = None
    effective_window_start: date | None = None
    freeze_periods_applied: list[FreezePeriodApplied] = field(default_factory=list)


@dataclass
class PartialMonth:
    month: tuple[int, int] = (0, 0)
    full_amount: Decimal = Decimal("0")
    fraction: Decimal = Decimal("0")
    claimable_amount: Decimal = Decimal("0")


@dataclass
class RightLimitationResult:
    limitation_type_id: str = ""
    full_amount: Decimal = Decimal("0")
    claimable_amount: Decimal = Decimal("0")
    excluded_amount: Decimal = Decimal("0")
    claimable_duration: Duration = field(default_factory=Duration)
    excluded_duration: Duration | None = None
    partial_months: list[PartialMonth] | None = None


@dataclass
class TimelineSummary:
    total_employment_days: int = 0
    claimable_days_general: int = 0
    excluded_days_general: int = 0
    total_freeze_days: int = 0


@dataclass
class TimelineWorkPeriod:
    start_date: date | None = None
    end_date: date | None = None
    duration: Duration = field(default_factory=Duration)


@dataclass
class TimelineData:
    employment_start: date | None = None
    employment_end: date | None = None
    filing_date: date | None = None
    limitation_windows: list[LimitationWindow] = field(default_factory=list)
    freeze_periods: list[FreezePeriodApplied] = field(default_factory=list)
    work_periods: list[TimelineWorkPeriod] = field(default_factory=list)
    summary: TimelineSummary = field(default_factory=TimelineSummary)


@dataclass
class LimitationResults:
    windows: list[LimitationWindow] = field(default_factory=list)
    per_right: dict[str, RightLimitationResult] = field(default_factory=dict)
    timeline_data: TimelineData = field(default_factory=TimelineData)


# =============================================================================
# Layer 7 - Deductions and claim summary (Phase 3)
# =============================================================================

@dataclass
class DeductionResult:
    right_id: str = ""
    calculated_amount: Decimal = Decimal("0")
    deduction_amount: Decimal = Decimal("0")
    net_amount: Decimal = Decimal("0")
    show_deduction: bool = False
    show_right: bool = False
    warning: bool = False


@dataclass
class ClaimSummaryRight:
    right_id: str = ""
    name: str = ""
    full_amount: Decimal = Decimal("0")
    after_limitation: Decimal = Decimal("0")
    after_deductions: Decimal = Decimal("0")
    deduction_amount: Decimal = Decimal("0")
    show: bool = False
    limitation_type: str = ""
    limitation_excluded: Decimal = Decimal("0")


@dataclass
class EmploymentSummary:
    worker_name: str | None = None
    defendant_name: str | None = None
    total_duration_display: str = ""
    worked_duration_display: str = ""
    filing_date: date | None = None
    filing_date_display: str = ""


@dataclass
class ClaimSummary:
    total_before_limitation: Decimal = Decimal("0")
    total_after_limitation: Decimal = Decimal("0")
    total_after_deductions: Decimal = Decimal("0")
    per_right: list[ClaimSummaryRight] = field(default_factory=list)
    employment_summary: EmploymentSummary = field(default_factory=EmploymentSummary)


# =============================================================================
# Main SSOT structure
# =============================================================================

@dataclass
class SSOT:
    """Single Source of Truth - Complete state of a claim calculation."""

    # Layer 0 - Input
    input: SSOTInput = field(default_factory=SSOTInput)

    # Layer 1 - Weaver output
    effective_periods: list[EffectivePeriod] = field(default_factory=list)
    employment_gaps: list[EmploymentGap] = field(default_factory=list)
    total_employment: TotalEmployment = field(default_factory=TotalEmployment)

    # Layer 2 - Daily records and shifts
    daily_records: list[DailyRecord] = field(default_factory=list)
    shifts: list[Shift] = field(default_factory=list)
    weeks: list[Week] = field(default_factory=list)

    # Layer 3 - Period×Month records
    period_month_records: list[PeriodMonthRecord] = field(default_factory=list)

    # Layer 4 - Monthly aggregates and seniority
    month_aggregates: list[MonthAggregate] = field(default_factory=list)
    seniority_monthly: list[SeniorityMonthly] = field(default_factory=list)
    seniority_totals: SeniorityTotals = field(default_factory=SeniorityTotals)

    # Layer 5 - Rights results
    rights_results: RightsResults = field(default_factory=RightsResults)

    # Layer 6 - Limitation results
    limitation_results: LimitationResults = field(default_factory=LimitationResults)

    # Layer 7 - Deductions and claim summary
    deduction_results: dict[str, DeductionResult] = field(default_factory=dict)
    claim_summary: ClaimSummary = field(default_factory=ClaimSummary)


# =============================================================================
# Day Snapshot - Helper for querying all data for a specific day
# =============================================================================

@dataclass
class DaySnapshot:
    """All SSOT data for a specific day, consolidated in one place.

    Use get_day_snapshot(ssot, target_date) to create.
    """
    target_date: date

    # From daily_records
    daily_record: DailyRecord | None = None

    # From shifts (may be multiple per day)
    shifts: list[Shift] = field(default_factory=list)

    # From effective_periods
    effective_period: EffectivePeriod | None = None

    # From seniority_monthly (for the month containing target_date)
    seniority: SeniorityMonthly | None = None

    # From period_month_records (for the period×month containing target_date)
    salary: PeriodMonthRecord | None = None

    # From month_aggregates (for the month containing target_date)
    month_aggregate: MonthAggregate | None = None

    # From weeks (the week containing target_date)
    week: Week | None = None

    # Computed summary
    total_hours: Decimal = Decimal("0")
    total_ot_hours: Decimal = Decimal("0")
    total_claim: Decimal = Decimal("0")


def get_day_snapshot(ssot: "SSOT", target_date: date) -> DaySnapshot:
    """Get consolidated snapshot of all SSOT data for a specific day.

    Args:
        ssot: The SSOT to query
        target_date: The date to get data for

    Returns:
        DaySnapshot with all relevant data for that day
    """
    snapshot = DaySnapshot(target_date=target_date)

    # Find daily_record
    for dr in ssot.daily_records:
        if dr.date == target_date:
            snapshot.daily_record = dr
            break

    # Find all shifts for this day
    for shift in ssot.shifts:
        if shift.assigned_day == target_date:
            snapshot.shifts.append(shift)
            snapshot.total_hours += shift.net_hours
            snapshot.total_ot_hours += shift.ot_tier1_hours + shift.ot_tier2_hours
            if shift.claim_amount:
                snapshot.total_claim += shift.claim_amount

    # Find effective_period
    for ep in ssot.effective_periods:
        if ep.start <= target_date <= ep.end:
            snapshot.effective_period = ep
            break

    # Find seniority for this month
    target_month = (target_date.year, target_date.month)
    for sen in ssot.seniority_monthly:
        if sen.month == target_month:
            snapshot.seniority = sen
            break

    # Find salary (period_month_record)
    if snapshot.effective_period:
        for pmr in ssot.period_month_records:
            if (pmr.effective_period_id == snapshot.effective_period.id
                    and pmr.month == target_month):
                snapshot.salary = pmr
                break

    # Find month_aggregate
    for ma in ssot.month_aggregates:
        if ma.month == target_month:
            snapshot.month_aggregate = ma
            break

    # Find week
    for week in ssot.weeks:
        if week.start_date and week.end_date:
            if week.start_date <= target_date <= week.end_date:
                snapshot.week = week
                break

    return snapshot


def format_day_snapshot(snapshot: DaySnapshot) -> str:
    """Format a DaySnapshot as a readable string.

    Args:
        snapshot: The snapshot to format

    Returns:
        Human-readable string representation
    """
    lines = []
    lines.append(f"=== יום {snapshot.target_date} ===")
    lines.append("")

    # Daily record
    if snapshot.daily_record:
        dr = snapshot.daily_record
        work_str = "יום עבודה" if dr.is_work_day else "לא עובד"
        rest_str = " (יום מנוחה)" if dr.is_rest_day else ""
        lines.append(f"[רשומה יומית]")
        lines.append(f"  סטטוס: {work_str}{rest_str}")
        lines.append(f"  יום בשבוע: {dr.day_of_week}")
        lines.append(f"  תקופה: {dr.effective_period_id}")
        if dr.shift_templates:
            for i, st in enumerate(dr.shift_templates):
                lines.append(f"  משמרת {i+1}: {st.start_time} - {st.end_time}")
    else:
        lines.append("[רשומה יומית] לא נמצאה")

    lines.append("")

    # Shifts
    if snapshot.shifts:
        lines.append(f"[משמרות] ({len(snapshot.shifts)})")
        for shift in snapshot.shifts:
            lines.append(f"  {shift.id}:")
            lines.append(f"    שעות נטו: {shift.net_hours:.2f}")
            lines.append(f"    רגילות: {shift.regular_hours:.2f}")
            lines.append(f"    OT tier1: {shift.ot_tier1_hours:.2f}")
            lines.append(f"    OT tier2: {shift.ot_tier2_hours:.2f}")
            if shift.claim_amount:
                lines.append(f"    תביעה: {shift.claim_amount:.2f} ש״ח")
    else:
        lines.append("[משמרות] אין")

    lines.append("")

    # Effective period
    if snapshot.effective_period:
        ep = snapshot.effective_period
        lines.append(f"[תקופה אפקטיבית]")
        lines.append(f"  ID: {ep.id}")
        lines.append(f"  טווח: {ep.start} עד {ep.end}")
        lines.append(f"  שכר: {ep.salary_amount} ({ep.salary_type.value})")
    else:
        lines.append("[תקופה אפקטיבית] לא נמצאה")

    lines.append("")

    # Salary
    if snapshot.salary:
        sal = snapshot.salary
        lines.append(f"[שכר - חודש {sal.month}]")
        lines.append(f"  שעתי: {sal.salary_hourly:.2f} ש״ח")
        lines.append(f"  יומי: {sal.salary_daily:.2f} ש״ח")
        lines.append(f"  חודשי: {sal.salary_monthly:.2f} ש״ח")
        if sal.minimum_applied:
            lines.append(f"  * הופעל שכר מינימום: {sal.minimum_wage_value:.2f}")
    else:
        lines.append("[שכר] לא נמצא")

    lines.append("")

    # Seniority
    if snapshot.seniority:
        sen = snapshot.seniority
        lines.append(f"[ותק - חודש {sen.month}]")
        lines.append(f"  אצל נתבע: {sen.at_defendant_cumulative} חודשים")
        lines.append(f"  ענפי: {sen.total_industry_cumulative} חודשים")
    else:
        lines.append("[ותק] לא נמצא")

    lines.append("")

    # Week
    if snapshot.week:
        w = snapshot.week
        week_type_str = "5 ימים" if w.week_type.value == 5 else "6 ימים"
        lines.append(f"[שבוע {w.id}]")
        lines.append(f"  סוג: {week_type_str}")
        lines.append(f"  ימי עבודה: {w.distinct_work_days}")
        lines.append(f"  שעות רגילות: {w.total_regular_hours:.2f}")
        lines.append(f"  OT שבועי: {w.weekly_ot_hours:.2f}")
    else:
        lines.append("[שבוע] לא נמצא")

    lines.append("")

    # Summary
    lines.append(f"[סיכום יום]")
    lines.append(f"  סה״כ שעות: {snapshot.total_hours:.2f}")
    lines.append(f"  סה״כ OT: {snapshot.total_ot_hours:.2f}")
    lines.append(f"  סה״כ תביעה: {snapshot.total_claim:.2f} ש״ח")

    return "\n".join(lines)
