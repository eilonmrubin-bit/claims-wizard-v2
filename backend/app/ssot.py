"""SSOT (Single Source of Truth) data structures for Claims Wizard.

This module defines all data structures used throughout the pipeline.
See docs/skills/ssot/SKILL.md for complete documentation.
"""

from dataclasses import dataclass, field
from datetime import date, time, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.pattern_translator import PatternSource


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
    TOTAL_PLUS_PATTERN = "total_plus_pattern"
    MATASH_PDF = "matash_pdf"


class TerminationReason(str, Enum):
    FIRED = "fired"  # פוטר
    RESIGNED_AS_FIRED = "resigned_as_fired"  # התפטר בדין מפוטר
    RESIGNED = "resigned"  # התפטר


class SeverancePath(str, Enum):
    SECTION_14_HOLDS = "section_14_holds"  # PATH A
    SECTION_14_FALLS = "section_14_falls"  # PATH B
    CONTRIBUTIONS = "contributions"  # PATH C (resigned)


class Section14Status(str, Enum):
    HOLDS = "holds"
    FALLS = "falls"


class LastSalaryMethod(str, Enum):
    LAST_FULL_PMR = "last_full_pmr"
    AVG_12_MONTHS = "avg_12_months"


class SeveranceLimitationType(str, Enum):
    NONE = "none"
    GENERAL = "general"


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
    prior_months: int | None = None  # Method א - prior seniority before defendant
    total_industry_months: int | None = None  # Method ב - total industry seniority
    matash_file: bytes | None = None  # Method ג


@dataclass
class TrainingFundTier:
    """Custom training fund tier from personal contract.

    Defines employer contribution rate for a seniority range.
    seniority_type: 'industry' (ותק ענפי) | 'employer' (ותק אצל מעסיק)
    from_months: inclusive lower bound in months
    to_months: exclusive upper bound in months. None = no upper limit (open-ended)
    employer_rate: Decimal, e.g. Decimal("0.075") for 7.5%
    """
    seniority_type: str = "employer"       # "employer" | "industry"
    from_months: int = 0
    to_months: int | None = None           # None = ללא הגבלה עליונה
    employer_rate: Decimal = Decimal("0")


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
    termination_reason: TerminationReason | None = None  # Required for severance

    # Training fund
    is_construction_foreman: bool = False
    training_fund_tiers: list[TrainingFundTier] = field(default_factory=list)

    # Travel allowance (construction)
    travel_distance_km: Decimal | None = None  # One-way distance from home to site
    lodging_input: 'LodgingInput | None' = None  # Lodging pattern for construction

    # Seniority
    seniority_input: SeniorityInput = field(default_factory=SeniorityInput)

    # Toggles and deductions
    right_toggles: dict[str, dict[str, bool]] = field(default_factory=dict)
    deductions_input: dict[str, Decimal] = field(default_factory=dict)
    right_specific_inputs: dict[str, dict[str, Any]] = field(default_factory=dict)

    # Pattern sources (Level B/C patterns for translation)
    pattern_sources: list['PatternSource'] | None = None


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
    # Total hours (regular + OT) for salary conversion
    avg_total_hours_per_day: Decimal = Decimal("0")
    avg_total_hours_per_shift: Decimal = Decimal("0")

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

# -----------------------------------------------------------------------------
# Severance Data Structures
# -----------------------------------------------------------------------------

@dataclass
class LastSalaryPMRUsed:
    """PMR entry used in last salary calculation."""
    month: tuple[int, int] = (0, 0)
    salary_monthly: Decimal = Decimal("0")


@dataclass
class LastSalaryInfo:
    """Information about last salary determination."""
    last_salary: Decimal = Decimal("0")
    method: LastSalaryMethod = LastSalaryMethod.LAST_FULL_PMR
    salary_changed_in_last_year: bool = False
    pmrs_used: list[LastSalaryPMRUsed] = field(default_factory=list)


@dataclass
class SeveranceMonthlyDetail:
    """Monthly detail for severance base calculation."""
    month: tuple[int, int] = (0, 0)
    effective_period_id: str = ""
    calendar_days_employed: int = 0
    total_calendar_days: int = 0
    partial_fraction: Decimal = Decimal("0")
    job_scope: Decimal = Decimal("0")
    salary_used: Decimal = Decimal("0")
    amount: Decimal = Decimal("0")


@dataclass
class SeverancePeriodSummary:
    """Period summary for severance calculation."""
    effective_period_id: str = ""
    start: date | None = None
    end: date | None = None
    months_count: int = 0
    avg_job_scope: Decimal = Decimal("0")
    avg_salary_monthly: Decimal | None = None  # Only for required contributions
    subtotal: Decimal = Decimal("0")


@dataclass
class FullSeveranceData:
    """Full severance calculation data."""
    base_total: Decimal = Decimal("0")
    ot_total: Decimal = Decimal("0")  # 0 if not cleaning
    recreation_total: Decimal = Decimal("0")  # 0 if not cleaning or pending
    recreation_pending: bool = False
    grand_total: Decimal = Decimal("0")
    base_monthly_detail: list[SeveranceMonthlyDetail] = field(default_factory=list)
    period_summaries: list[SeverancePeriodSummary] = field(default_factory=list)


@dataclass
class RequiredContributionsData:
    """Required contributions calculation data."""
    base_total: Decimal = Decimal("0")
    ot_total: Decimal = Decimal("0")  # same as full_severance.ot_total
    recreation_total: Decimal = Decimal("0")  # same as full_severance.recreation_total
    grand_total: Decimal = Decimal("0")
    base_monthly_detail: list[SeveranceMonthlyDetail] = field(default_factory=list)
    period_summaries: list[SeverancePeriodSummary] = field(default_factory=list)


@dataclass
class OTAdditionMonthlyDetail:
    """Monthly OT addition detail (cleaning industry)."""
    month: tuple[int, int] = (0, 0)
    effective_period_id: str = ""
    full_ot_monthly_pay: Decimal = Decimal("0")
    job_scope: Decimal = Decimal("0")
    amount: Decimal = Decimal("0")


@dataclass
class OTAdditionData:
    """OT addition data for cleaning industry."""
    rate: Decimal = Decimal("0.06")
    total: Decimal = Decimal("0")
    monthly_detail: list[OTAdditionMonthlyDetail] = field(default_factory=list)


@dataclass
class RecreationAdditionMonthlyDetail:
    """Monthly recreation addition detail (cleaning industry)."""
    month: tuple[int, int] = (0, 0)
    annual_recreation_value: Decimal = Decimal("0")
    monthly_value: Decimal = Decimal("0")
    partial_fraction: Decimal = Decimal("0")
    amount: Decimal = Decimal("0")


@dataclass
class RecreationAdditionData:
    """Recreation addition data for cleaning industry."""
    rate: Decimal = Decimal("0.08333")
    total: Decimal = Decimal("0")
    recreation_pending: bool = True
    monthly_detail: list[RecreationAdditionMonthlyDetail] = field(default_factory=list)


@dataclass
class Section14Comparison:
    """Section 14 comparison data."""
    actual_deposits: Decimal = Decimal("0")
    required_contributions_total: Decimal = Decimal("0")
    difference: Decimal = Decimal("0")  # actual - required
    status: Section14Status | None = None


@dataclass
class SeveranceMonthlyBreakdown:
    """Monthly breakdown for limitation module."""
    month: tuple[int, int] = (0, 0)
    claim_amount: Decimal = Decimal("0")


@dataclass
class SeveranceData:
    """Complete severance calculation result."""
    # Eligibility
    eligible: bool = False
    ineligible_reason: str | None = None

    # Path & Status
    termination_reason: TerminationReason | None = None
    industry: str = ""
    path: SeverancePath | None = None
    section_14_status: Section14Status | None = None
    limitation_type: SeveranceLimitationType = SeveranceLimitationType.NONE

    # Rates
    severance_rate: Decimal = Decimal("0.08333")
    contribution_rate: Decimal = Decimal("0")
    ot_addition_rate: Decimal | None = None  # 0.06 for cleaning
    recreation_addition_rate: Decimal | None = None  # 0.08333 for cleaning

    # Last Salary
    last_salary_info: LastSalaryInfo = field(default_factory=LastSalaryInfo)

    # Full Severance
    full_severance: FullSeveranceData = field(default_factory=FullSeveranceData)

    # Required Contributions
    required_contributions: RequiredContributionsData = field(default_factory=RequiredContributionsData)

    # Cleaning Additions (shared between full and required)
    ot_addition: OTAdditionData | None = None
    recreation_addition: RecreationAdditionData | None = None

    # Section 14 Comparison
    section_14_comparison: Section14Comparison | None = None

    # Final Claim
    claim_before_deductions: Decimal = Decimal("0")
    deduction_override: Decimal | None = None  # 0 for path A, null for B/C
    total_claim: Decimal = Decimal("0")

    # Monthly Breakdown (for limitation module)
    monthly_breakdown: list[SeveranceMonthlyBreakdown] = field(default_factory=list)


# -----------------------------------------------------------------------------
# Other Rights Data Structures
# -----------------------------------------------------------------------------

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
    before_seniority: bool = False
    day_of_week: str = ""
    week_type: WeekType | None = None
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
    holidays: list[HolidayEntry] = field(default_factory=list)
    election_day_entitled: bool = False
    election_day_value: Decimal | None = None
    total_entitled_days: int = 0
    total_claim: Decimal = Decimal("0")


@dataclass
class HolidaysResult:
    seniority_eligibility_date: date | None = None
    per_year: list[HolidayYearResult] = field(default_factory=list)
    grand_total_days: int = 0
    grand_total_claim: Decimal = Decimal("0")


@dataclass
class RecreationDayValueSegment:
    """A segment within an employment year where day_value is constant."""
    segment_start: date | None = None
    segment_end: date | None = None
    day_value: Decimal = Decimal("0")
    day_value_effective_date: date | None = None
    weight: Decimal = Decimal("0")  # days_in_segment / total_year_days
    segment_value: Decimal = Decimal("0")  # weight × entitled_days × day_value


@dataclass
class RecreationYearData:
    """Recreation data for a single employment year."""
    year_number: int = 0  # 1, 2, 3, ...
    year_start: date | None = None
    year_end: date | None = None
    is_partial: bool = False
    partial_fraction: Decimal | None = None  # 0 < x < 1, None if full year
    seniority_years: int = 0  # seniority at start of this year
    base_days: int = 0  # days per year from table
    avg_scope: Decimal = Decimal("0")  # average job scope
    entitled_days: Decimal = Decimal("0")  # base_days × partial_fraction × avg_scope
    segments: list[RecreationDayValueSegment] = field(default_factory=list)
    entitled_value: Decimal = Decimal("0")  # Σ segment_value


@dataclass
class RecreationResult:
    """Recreation pay calculation result."""
    entitled: bool = False  # Whether employee met waiting period (1 year)
    not_entitled_reason: str | None = None  # Reason if entitled=False

    industry: str = ""  # general | construction | agriculture | cleaning
    industry_fallback_used: bool = False  # True if industry not found and fell back to general

    years: list[RecreationYearData] = field(default_factory=list)

    grand_total_days: Decimal = Decimal("0")  # Total days (no rounding)
    grand_total_value: Decimal = Decimal("0")  # Total value in NIS (round only in display)


@dataclass
class VacationWeekTypeSegment:
    """A segment within a calendar year with uniform week type."""
    segment_start: date | None = None
    segment_end: date | None = None
    week_type: str = ""  # "five_day" | "six_day"
    weeks_count: Decimal = Decimal("0")
    weight: Decimal = Decimal("0")  # weeks_count / total_weeks_in_year
    base_days: int = 0  # days per table for this week type
    weighted_days: Decimal = Decimal("0")  # weight × base_days


@dataclass
class VacationYearData:
    """Vacation data for a single calendar year."""
    year: int = 0
    year_start: date | None = None  # Jan 1 or employment start (partial)
    year_end: date | None = None  # Dec 31 or employment end (partial)
    is_partial: bool = False
    partial_fraction: Decimal | None = None  # None if full year
    partial_description: str = ""  # e.g. "9 חודשים (אפריל–דצמבר)" for UI
    seniority_years: int = 0
    age_at_year_start: int | None = None  # construction only
    age_55_split: bool = False  # construction: turned 55 this year
    is_55_plus: bool = False  # construction: entire year computed with 55+ table
    week_type_segments: list[VacationWeekTypeSegment] = field(default_factory=list)
    weighted_base_days: Decimal = Decimal("0")
    entitled_days: Decimal = Decimal("0")
    avg_daily_salary: Decimal = Decimal("0")
    year_value: Decimal = Decimal("0")
    claimable_fraction: Decimal | None = None  # 1.0=full, 0.0=excluded, 0<x<1=partial (split by limitation)


@dataclass
class VacationResult:
    """Annual vacation calculation result."""
    entitled: bool = True

    industry: str = ""
    seniority_basis: str = ""  # "employer" | "industry"

    years: list[VacationYearData] = field(default_factory=list)

    grand_total_days: Decimal = Decimal("0")
    grand_total_value: Decimal = Decimal("0")


@dataclass
class PensionMonthData:
    """Pension data for a single calendar month."""
    month: tuple[int, int] = (0, 0)  # (year, month)
    month_start: date | None = None
    salary_monthly: Decimal = Decimal("0")
    job_scope: Decimal = Decimal("0")
    pension_rate: Decimal = Decimal("0")
    month_value: Decimal = Decimal("0")  # salary_monthly × rate × job_scope


@dataclass
class PensionResult:
    """Pension calculation result."""
    entitled: bool = True
    industry: str = ""
    months: list[PensionMonthData] = field(default_factory=list)
    grand_total_value: Decimal = Decimal("0")


@dataclass
class TrainingFundSegment:
    """A segment within a month for training fund calculation (split month support)."""
    days: int = 0
    days_total: int = 0
    employer_rate: Decimal = Decimal("0")
    eligible: bool = True
    tier_source: str = "industry"  # "industry" | "custom"
    segment_required: Decimal = Decimal("0")


@dataclass
class TrainingFundMonthDetail:
    """Monthly detail for training fund calculation."""
    month: tuple[int, int] = (0, 0)
    effective_period_id: str = ""
    salary_base: Decimal = Decimal("0")
    recreation_component: Decimal = Decimal("0")
    total_regular_hours: Decimal = Decimal("0")        # from PMR
    month_total_regular_hours: Decimal = Decimal("0")  # from MonthAggregate
    hours_weight: Decimal = Decimal("1")               # = total / month_total
    eligible_this_month: bool = True  # False if all segments are ineligible
    seniority_years: Decimal | None = None  # construction — at start of month
    is_split_month: bool = False
    month_required: Decimal = Decimal("0")  # sum of all segments
    segments: list[TrainingFundSegment] = field(default_factory=list)


@dataclass
class TrainingFundMonthlyBreakdown:
    """Monthly breakdown for limitation module."""
    month: tuple[int, int] = (0, 0)
    claim_amount: Decimal = Decimal("0")


@dataclass
class TrainingFundData:
    """Training fund calculation result."""
    eligible: bool = False
    ineligible_reason: str | None = None
    industry: str = ""
    is_construction_foreman: bool = False
    used_custom_tiers: bool = False
    recreation_pending: bool = False
    monthly_detail: list[TrainingFundMonthDetail] = field(default_factory=list)
    required_total: Decimal = Decimal("0")
    actual_deposits: Decimal = Decimal("0")
    claim_before_deductions: Decimal = Decimal("0")
    monthly_breakdown: list[TrainingFundMonthlyBreakdown] = field(default_factory=list)


# -----------------------------------------------------------------------------
# Travel Allowance Data Structures
# -----------------------------------------------------------------------------

@dataclass
class LodgingPeriod:
    """Definition of a lodging period with seniority-based matching.

    Defines lodging pattern for a date range.
    pattern_type: 'none' | 'weekly' | 'monthly'
    nights_per_unit: X nights per week or per month
    visits_per_unit: Y visits per week or per month
    """
    id: str = ""
    start: date | None = None  # inclusive
    end: date | None = None  # inclusive
    snap_to: str | None = None  # "employment_period" | "work_pattern" | None
    snap_ref_id: str | None = None  # id of the snapped EP or WP, if any
    pattern_type: str = "none"  # "none" | "weekly" | "monthly"
    nights_per_unit: int = 0  # X nights per week or per month
    visits_per_unit: int = 0  # Y visits per week or per month


@dataclass
class LodgingInput:
    """Lodging input for construction workers."""
    periods: list[LodgingPeriod] = field(default_factory=list)
    # Empty list = no lodging at all.
    # Periods must not overlap. Gaps between periods = no lodging.


@dataclass
class TravelWeekDetail:
    """Weekly detail for travel allowance calculation."""
    week_start: date | None = None
    week_end: date | None = None
    effective_period_id: str = ""
    work_days: int = 0
    cycle_position: int | None = None  # 1-based position within lodging cycle, null if no lodging
    week_pattern: str = "no_lodging"  # "full_lodging" | "daily_return" | "no_lodging"
    travel_days: int = 0
    daily_rate: Decimal = Decimal("0")
    week_travel_value: Decimal = Decimal("0")


@dataclass
class TravelMonthlyBreakdown:
    """Monthly breakdown for limitation module."""
    month: tuple[int, int] = (0, 0)  # (year, month)
    travel_days: int = 0
    claim_amount: Decimal = Decimal("0")


@dataclass
class TravelData:
    """Travel allowance calculation result."""
    # Configuration
    industry: str = ""
    daily_rate: Decimal = Decimal("0")  # effective rate used (22.6 / 26.4 / 39.6)
    distance_km: Decimal | None = None  # from input, construction only
    distance_tier: str | None = None  # "standard" | "far" | null

    # Lodging Summary
    has_lodging: bool = False
    lodging_periods_count: int = 0  # number of active lodging periods

    # Weekly Detail
    weekly_detail: list[TravelWeekDetail] = field(default_factory=list)

    # Monthly Breakdown (for limitation module)
    monthly_breakdown: list[TravelMonthlyBreakdown] = field(default_factory=list)

    # Totals
    grand_total_travel_days: int = 0
    grand_total_value: Decimal = Decimal("0")
    claim_before_deductions: Decimal = Decimal("0")  # = grand_total_value


# Meal Allowance (אש"ל) Data Structures
# -----------------------------------------------------------------------------

@dataclass
class MealAllowanceMonthlyBreakdown:
    """Monthly breakdown for meal allowance calculation."""
    month: tuple[int, int] = (0, 0)  # (year, month)
    nights: Decimal = Decimal("0")  # pro-rated nights this month
    nightly_rate: Decimal = Decimal("0")
    claim_amount: Decimal = Decimal("0")


@dataclass
class MealAllowanceData:
    """Meal allowance (אש"ל) calculation result."""
    # Eligibility
    entitled: bool = False
    not_entitled_reason: str | None = None  # "not_construction" | "no_lodging_input" | "disabled"

    # Configuration
    industry: str = ""

    # Monthly Breakdown
    monthly_breakdown: list[MealAllowanceMonthlyBreakdown] = field(default_factory=list)

    # Totals
    grand_total_nights: Decimal = Decimal("0")
    grand_total_value: Decimal = Decimal("0")
    claim_before_deductions: Decimal = Decimal("0")  # = grand_total_value


@dataclass
class RightsResults:
    """Results for all rights (Phase 2)."""
    overtime: OvertimeResult | None = None
    holidays: HolidaysResult | None = None
    vacation: VacationResult | None = None
    severance: SeveranceData | None = None
    pension: PensionResult | None = None
    recreation: RecreationResult | None = None
    training_fund: TrainingFundData | None = None
    salary_completion: Any | None = None  # Not yet defined
    travel: 'TravelData | None' = None
    meal_allowance: 'MealAllowanceData | None' = None


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
    claimable_duration: Duration = field(default_factory=Duration)  # effective_window_start → filing_date


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
    claimable_days_vacation: int = 0
    excluded_days_vacation: int = 0
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
