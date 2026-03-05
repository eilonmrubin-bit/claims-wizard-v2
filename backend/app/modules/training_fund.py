"""Training fund (קרן השתלמות) calculation module.

Calculates training fund contribution claims based on Israeli labor law extension orders.
Industry-specific rates apply for construction and cleaning.
General industry requires custom contract tiers.
Agriculture workers are not eligible.

See docs/skills/training-fund/SKILL.md for complete documentation.
"""

import calendar
import json
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from app.ssot import (
    TrainingFundTier,
    TrainingFundSegment,
    TrainingFundMonthDetail,
    TrainingFundMonthlyBreakdown,
    TrainingFundData,
    PeriodMonthRecord,
    MonthAggregate,
    SeniorityMonthly,
)


logger = logging.getLogger(__name__)


@dataclass
class TrainingFundIndustryConfig:
    """Industry configuration for training fund calculation."""
    name: str
    employer_rate: Decimal | None
    employee_rate: Decimal | None
    min_months: int = 0
    tiers_by_seniority: list[dict[str, Any]] | None = None


def load_training_fund_config(settings_path: Path | None = None) -> dict[str, TrainingFundIndustryConfig]:
    """Load training fund industry configurations from settings.json."""
    if settings_path is None:
        settings_path = Path(__file__).parent.parent.parent / "settings.json"

    with open(settings_path, "r", encoding="utf-8") as f:
        settings = json.load(f)

    training_fund_config = settings.get("training_fund_config", {})
    industries = training_fund_config.get("industries", {})

    result = {}
    for industry_id, config in industries.items():
        result[industry_id] = TrainingFundIndustryConfig(
            name=config.get("name", industry_id),
            employer_rate=Decimal(str(config.get("employer_rate"))) if config.get("employer_rate") is not None else None,
            employee_rate=Decimal(str(config.get("employee_rate"))) if config.get("employee_rate") is not None else None,
            min_months=config.get("min_months", 0),
            tiers_by_seniority=config.get("tiers_by_seniority"),
        )

    return result


def _get_last_day_of_month(year: int, month: int) -> date:
    """Get the last day of a given month."""
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, last_day)


def _get_days_in_month(year: int, month: int) -> int:
    """Get the number of days in a month."""
    return calendar.monthrange(year, month)[1]


def _get_construction_rate_for_seniority(
    seniority_years: Decimal,
    is_foreman: bool,
) -> tuple[Decimal, Decimal, bool]:
    """Get construction industry rates based on seniority.

    Returns:
        Tuple of (employer_rate, employee_rate, eligible)
    """
    if is_foreman:
        # Foreman gets 7.5%/2.5% from day 1
        return Decimal("0.075"), Decimal("0.025"), True

    # Worker rates based on seniority
    if seniority_years < 3:
        return Decimal("0"), Decimal("0"), False
    elif seniority_years < 6:
        return Decimal("0.025"), Decimal("0.01"), True
    else:
        return Decimal("0.05"), Decimal("0.025"), True


def _find_custom_tier_for_date(
    d: date,
    training_fund_tiers: list[TrainingFundTier],
) -> TrainingFundTier | None:
    """Find the custom tier that covers a specific date, if any."""
    for tier in training_fund_tiers:
        if tier.start_date <= d <= tier.end_date:
            return tier
    return None


def _calculate_seniority_at_date(
    target_date: date,
    month_start_seniority: Decimal,
    month_end_seniority: Decimal,
    first_day: date,
    last_day: date,
) -> Decimal:
    """Calculate seniority at a specific date within a month using linear interpolation."""
    days_in_month = (last_day - first_day).days + 1
    days_into_month = (target_date - first_day).days

    if days_in_month <= 0:
        return month_start_seniority

    fraction = Decimal(days_into_month) / Decimal(days_in_month)
    seniority_growth = month_end_seniority - month_start_seniority
    return month_start_seniority + (fraction * seniority_growth)


def _find_threshold_crossing_date(
    threshold: Decimal,
    month_start_seniority: Decimal,
    month_end_seniority: Decimal,
    first_day: date,
    last_day: date,
) -> date | None:
    """Find the date when seniority crosses a threshold within a month.

    Returns None if threshold is not crossed within the month.
    """
    # Check if threshold is crossed during this month
    if month_start_seniority >= threshold or month_end_seniority < threshold:
        return None

    days_in_month = (last_day - first_day).days + 1
    seniority_growth = month_end_seniority - month_start_seniority

    if seniority_growth <= 0:
        return None

    # Linear interpolation: how many days until threshold?
    days_to_threshold = (threshold - month_start_seniority) / seniority_growth * Decimal(days_in_month)
    days_to_threshold_int = int(days_to_threshold.to_integral_value(rounding=ROUND_HALF_UP))

    # Clamp to valid range
    if days_to_threshold_int < 1:
        days_to_threshold_int = 1
    if days_to_threshold_int > days_in_month:
        return None

    return first_day + timedelta(days=days_to_threshold_int)


def _build_month_segments(
    year: int,
    month: int,
    industry: str,
    is_foreman: bool,
    training_fund_tiers: list[TrainingFundTier],
    seniority_at_start: Decimal | None,
    seniority_at_end: Decimal | None,
) -> list[tuple[date, date, Decimal, Decimal, bool, str]]:
    """Build segments for a month based on rate transitions.

    Returns a list of segments, each as:
    (start_date, end_date, employer_rate, employee_rate, eligible, tier_source)
    """
    first_day = date(year, month, 1)
    last_day = _get_last_day_of_month(year, month)

    # Collect all transition points
    transition_points: list[date] = [first_day]

    # Construction seniority thresholds (non-foreman only)
    if industry == "construction" and not is_foreman and seniority_at_start is not None and seniority_at_end is not None:
        for threshold in [Decimal("3"), Decimal("6")]:
            crossing_date = _find_threshold_crossing_date(
                threshold, seniority_at_start, seniority_at_end, first_day, last_day
            )
            if crossing_date and first_day < crossing_date <= last_day:
                transition_points.append(crossing_date)

    # Custom tier boundaries
    for tier in training_fund_tiers:
        # Tier start: if it falls within the month (not on first day)
        if first_day < tier.start_date <= last_day:
            transition_points.append(tier.start_date)
        # Tier end + 1 day: if the tier ends mid-month, the day after is a transition
        tier_end_plus_one = tier.end_date + timedelta(days=1)
        if first_day < tier_end_plus_one <= last_day:
            transition_points.append(tier_end_plus_one)

    # Sort and deduplicate
    transition_points = sorted(set(transition_points))

    # Build segments
    segments: list[tuple[date, date, Decimal, Decimal, bool, str]] = []

    for i, seg_start in enumerate(transition_points):
        if i + 1 < len(transition_points):
            seg_end = transition_points[i + 1] - timedelta(days=1)
        else:
            seg_end = last_day

        # Determine rate for this segment
        # First check custom tier
        tier = _find_custom_tier_for_date(seg_start, training_fund_tiers)
        if tier:
            employer_rate = tier.employer_rate
            employee_rate = tier.employee_rate
            eligible = employer_rate > 0
            tier_source = "custom"
        else:
            # Industry defaults
            if industry == "construction":
                # Calculate seniority at segment start
                if seniority_at_start is not None and seniority_at_end is not None:
                    seg_seniority = _calculate_seniority_at_date(
                        seg_start, seniority_at_start, seniority_at_end, first_day, last_day
                    )
                else:
                    seg_seniority = Decimal("0")

                employer_rate, employee_rate, eligible = _get_construction_rate_for_seniority(
                    seg_seniority, is_foreman
                )
                tier_source = "industry"
            elif industry == "cleaning":
                employer_rate = Decimal("0.075")
                employee_rate = Decimal("0.025")
                eligible = True
                tier_source = "industry"
            else:
                # General without custom tier - not eligible
                employer_rate = Decimal("0")
                employee_rate = Decimal("0")
                eligible = False
                tier_source = "industry"

        segments.append((seg_start, seg_end, employer_rate, employee_rate, eligible, tier_source))

    return segments


def compute_training_fund(
    period_month_records: list[PeriodMonthRecord],
    month_aggregates: list[MonthAggregate],
    seniority_monthly: list[SeniorityMonthly],
    industry: str,
    is_construction_foreman: bool,
    training_fund_tiers: list[TrainingFundTier],
    actual_deposits: Decimal,
    settings_path: Path | None = None,
) -> TrainingFundData:
    """Compute training fund contribution claims.

    Args:
        period_month_records: Monthly work records per effective period
        month_aggregates: Aggregated monthly data with job_scope
        seniority_monthly: Monthly seniority data for construction industry
        industry: Industry identifier
        is_construction_foreman: Whether worker is a certified foreman (construction only)
        training_fund_tiers: Optional custom contract tiers that override industry defaults
        actual_deposits: Actual employer deposits made (for display only)
        settings_path: Optional path to settings.json

    Returns:
        TrainingFundData with eligibility, monthly detail, and claim totals
    """
    # Load industry configuration
    load_training_fund_config(settings_path)

    # Check for agriculture - not eligible
    if industry == "agriculture":
        return TrainingFundData(
            eligible=False,
            ineligible_reason="ענף חקלאות — אין זכות אישית לעובד רגיל",
            industry=industry,
            is_construction_foreman=False,
        )

    # Check for general industry without custom tiers
    if industry == "general" and not training_fund_tiers:
        return TrainingFundData(
            eligible=False,
            ineligible_reason="לא הוזנו מדרגות קרן השתלמות",
            industry=industry,
            is_construction_foreman=False,
        )

    # Build lookup for month_aggregates by month
    ma_lookup = {ma.month: ma for ma in month_aggregates}

    # Build lookup for seniority by month (construction)
    seniority_lookup = {sm.month: sm for sm in seniority_monthly}

    # Determine if custom tiers were used
    used_custom_tiers = bool(training_fund_tiers)

    # Recreation pending flag (cleaning only, until recreation module exists)
    recreation_pending = industry == "cleaning"

    monthly_detail: list[TrainingFundMonthDetail] = []
    monthly_breakdown: list[TrainingFundMonthlyBreakdown] = []
    required_total = Decimal("0")

    # Process each period month record
    for pmr in period_month_records:
        year, month = pmr.month

        # Get month aggregate for job_scope
        ma = ma_lookup.get(pmr.month)
        job_scope = ma.job_scope if ma else Decimal("1")

        # Get salary base
        salary_base = pmr.salary_monthly
        recreation_component = Decimal("0")

        # Get seniority data for this month
        seniority_data = seniority_lookup.get(pmr.month)
        seniority_at_start = seniority_data.total_industry_years_cumulative if seniority_data else None

        # Get next month's seniority for interpolation
        next_month = (year, month + 1) if month < 12 else (year + 1, 1)
        next_seniority_data = seniority_lookup.get(next_month)
        if next_seniority_data:
            seniority_at_end = next_seniority_data.total_industry_years_cumulative
        elif seniority_at_start is not None:
            # Approximate: add 1/12 year
            seniority_at_end = seniority_at_start + Decimal("1") / Decimal("12")
        else:
            seniority_at_end = None

        # Build segments for this month
        raw_segments = _build_month_segments(
            year, month, industry, is_construction_foreman,
            training_fund_tiers, seniority_at_start, seniority_at_end
        )

        days_total = _get_days_in_month(year, month)
        segments: list[TrainingFundSegment] = []
        month_required = Decimal("0")

        for seg_start, seg_end, emp_rate, ee_rate, eligible, tier_source in raw_segments:
            seg_days = (seg_end - seg_start).days + 1

            if eligible:
                segment_required = salary_base * job_scope * (Decimal(seg_days) / Decimal(days_total)) * emp_rate
            else:
                segment_required = Decimal("0")

            month_required += segment_required

            segments.append(TrainingFundSegment(
                days=seg_days,
                days_total=days_total,
                employer_rate=emp_rate,
                employee_rate=ee_rate,
                eligible=eligible,
                tier_source=tier_source,
                segment_required=segment_required,
            ))

        required_total += month_required

        # Determine month-level flags
        is_split_month = len(segments) > 1
        eligible_this_month = any(seg.eligible for seg in segments)

        # Create monthly detail record
        detail = TrainingFundMonthDetail(
            month=pmr.month,
            effective_period_id=pmr.effective_period_id,
            salary_base=salary_base,
            recreation_component=recreation_component,
            job_scope=job_scope,
            eligible_this_month=eligible_this_month,
            seniority_years=seniority_at_start,
            is_split_month=is_split_month,
            month_required=month_required,
            segments=segments,
        )
        monthly_detail.append(detail)

        # Create monthly breakdown record (for limitation module)
        breakdown = TrainingFundMonthlyBreakdown(
            month=pmr.month,
            claim_amount=month_required,
        )
        monthly_breakdown.append(breakdown)

    # Sort monthly detail and breakdown by month
    monthly_detail.sort(key=lambda d: d.month)
    monthly_breakdown.sort(key=lambda b: b.month)

    return TrainingFundData(
        eligible=True,
        ineligible_reason=None,
        industry=industry,
        is_construction_foreman=is_construction_foreman,
        used_custom_tiers=used_custom_tiers,
        recreation_pending=recreation_pending,
        monthly_detail=monthly_detail,
        required_total=required_total,
        actual_deposits=actual_deposits,
        claim_before_deductions=required_total,  # Deduction handled in post-processing
        monthly_breakdown=monthly_breakdown,
    )
