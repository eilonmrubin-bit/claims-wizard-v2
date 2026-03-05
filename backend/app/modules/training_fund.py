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
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.ssot import (
    TrainingFundTier,
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


def _check_custom_tier_covers_month(
    tier: TrainingFundTier,
    year: int,
    month: int,
) -> bool:
    """Check if a custom tier covers a full month."""
    first_day = date(year, month, 1)
    last_day = _get_last_day_of_month(year, month)
    return tier.start_date <= first_day and tier.end_date >= last_day


def _get_construction_rate(
    seniority_years: Decimal,
    is_foreman: bool,
    tiers_by_seniority: list[dict[str, Any]] | None,
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
    config = load_training_fund_config(settings_path)
    industry_config = config.get(industry)

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

        # For cleaning: would add recreation component here when module exists
        # For now, recreation_pending = True means we don't add it

        # Determine rates for this month
        employer_rate = Decimal("0")
        employee_rate = Decimal("0")
        eligible_this_month = True
        seniority_years: Decimal | None = None
        tier_source = "industry"

        # Check custom tiers first
        custom_tier_found = False
        for tier in training_fund_tiers:
            if _check_custom_tier_covers_month(tier, year, month):
                employer_rate = tier.employer_rate
                employee_rate = tier.employee_rate
                tier_source = "custom"
                custom_tier_found = True
                # Custom tier with 0 rates means not eligible for this period
                eligible_this_month = employer_rate > 0
                break

        # If no custom tier, use industry defaults
        if not custom_tier_found:
            if industry == "construction":
                # Get seniority for this month
                seniority_data = seniority_lookup.get(pmr.month)
                if seniority_data:
                    seniority_years = seniority_data.total_industry_years_cumulative
                else:
                    seniority_years = Decimal("0")

                employer_rate, employee_rate, eligible_this_month = _get_construction_rate(
                    seniority_years,
                    is_construction_foreman,
                    industry_config.tiers_by_seniority if industry_config else None,
                )

            elif industry == "cleaning":
                employer_rate = Decimal("0.075")
                employee_rate = Decimal("0.025")
                eligible_this_month = True

            elif industry == "general":
                # General without custom tiers - should not reach here
                # (already checked above)
                eligible_this_month = False
                employer_rate = Decimal("0")
                employee_rate = Decimal("0")

        # Calculate month_required
        if eligible_this_month:
            month_required = salary_base * employer_rate * job_scope
        else:
            month_required = Decimal("0")

        required_total += month_required

        # Create monthly detail record
        detail = TrainingFundMonthDetail(
            month=pmr.month,
            effective_period_id=pmr.effective_period_id,
            salary_base=salary_base,
            recreation_component=recreation_component,
            employer_rate=employer_rate,
            employee_rate=employee_rate,
            job_scope=job_scope,
            eligible_this_month=eligible_this_month,
            seniority_years=seniority_years,
            tier_source=tier_source,
            month_required=month_required,
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
