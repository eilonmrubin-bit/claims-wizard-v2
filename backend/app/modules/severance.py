"""Severance pay (פיצויי פיטורין) calculation module.

Calculates severance pay entitlement based on Israeli labor law.
Supports three computation paths based on termination reason and Section 14 status.

See docs/skills/severance/SKILL.md for complete documentation.
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
    TerminationReason,
    SeverancePath,
    Section14Status,
    SeveranceLimitationType,
    LastSalaryMethod,
    SeveranceData,
    LastSalaryInfo,
    LastSalaryPMRUsed,
    SeveranceMonthlyDetail,
    SeverancePeriodSummary,
    FullSeveranceData,
    RequiredContributionsData,
    OTAdditionData,
    OTAdditionMonthlyDetail,
    RecreationAdditionData,
    RecreationAdditionMonthlyDetail,
    Section14Comparison,
    SeveranceMonthlyBreakdown,
    PeriodMonthRecord,
    MonthAggregate,
    EffectivePeriod,
    Shift,
    Duration,
)


logger = logging.getLogger(__name__)


@dataclass
class IndustryConfig:
    """Industry configuration for severance calculation."""
    name: str
    severance_rate: Decimal
    contribution_rate: Decimal
    ot_addition: bool
    recreation_addition: bool
    min_months: int
    ot_addition_rate: Decimal | None = None
    recreation_addition_rate: Decimal | None = None


def load_industry_config(settings_path: Path | None = None) -> dict[str, IndustryConfig]:
    """Load industry configurations from settings.json."""
    if settings_path is None:
        settings_path = Path(__file__).parent.parent.parent / "settings.json"

    with open(settings_path, "r", encoding="utf-8") as f:
        settings = json.load(f)

    severance_config = settings.get("severance_config", {})
    industries = severance_config.get("industries", {})

    result = {}
    for industry_id, config in industries.items():
        result[industry_id] = IndustryConfig(
            name=config.get("name", industry_id),
            severance_rate=Decimal(str(config.get("severance_rate", "0.08333"))),
            contribution_rate=Decimal(str(config.get("contribution_rate", "0.06"))),
            ot_addition=config.get("ot_addition", False),
            recreation_addition=config.get("recreation_addition", False),
            min_months=config.get("min_months", 12),
            ot_addition_rate=Decimal(str(config.get("ot_addition_rate", "0.06")))
            if config.get("ot_addition") else None,
            recreation_addition_rate=Decimal(str(config.get("recreation_addition_rate", "0.08333")))
            if config.get("recreation_addition") else None,
        )

    # Add default general config if not present
    if "general" not in result:
        result["general"] = IndustryConfig(
            name="כללי",
            severance_rate=Decimal("0.08333"),
            contribution_rate=Decimal("0.06"),
            ot_addition=False,
            recreation_addition=False,
            min_months=12,
        )

    return result


def _get_calendar_days_in_month(year: int, month: int) -> int:
    """Get the number of days in a month."""
    return calendar.monthrange(year, month)[1]


def _compute_partial_fraction(
    month: tuple[int, int],
    effective_periods: list[EffectivePeriod],
    effective_period_id: str,
) -> tuple[int, int, Decimal]:
    """Compute partial fraction for a month based on employment.

    Returns:
        Tuple of (calendar_days_employed, total_calendar_days, partial_fraction)
    """
    year, mon = month
    total_days = _get_calendar_days_in_month(year, mon)
    month_start = date(year, mon, 1)
    month_end = date(year, mon, total_days)

    # Find the effective period
    ep = None
    for period in effective_periods:
        if period.id == effective_period_id:
            ep = period
            break

    if ep is None:
        return 0, total_days, Decimal("0")

    # Calculate days employed in this month
    employed_start = max(month_start, ep.start)
    employed_end = min(month_end, ep.end)

    if employed_start > employed_end:
        return 0, total_days, Decimal("0")

    days_employed = (employed_end - employed_start).days + 1
    fraction = Decimal(days_employed) / Decimal(total_days)

    return days_employed, total_days, fraction


def _determine_last_salary(
    period_month_records: list[PeriodMonthRecord],
) -> LastSalaryInfo:
    """Determine the last salary based on PMRs.

    Rule:
    - If salary did NOT change in last 12 months: use salary_monthly from last PMR
    - If salary DID change: use simple average of salary_monthly across last 12 months
    """
    if not period_month_records:
        return LastSalaryInfo()

    # Sort PMRs by month descending
    sorted_pmrs = sorted(
        period_month_records,
        key=lambda p: p.month,
        reverse=True,
    )

    last_month = sorted_pmrs[0].month
    last_year, last_mon = last_month

    # Calculate 12 months ago (start of the 12-month window)
    # If last month is Dec 2023, we want Jan 2023 (same year, month 1)
    # If last month is Jun 2024, we want Jul 2023 (prev year, month 7)
    target_mon = last_mon - 11
    if target_mon <= 0:
        target_mon += 12
        twelve_months_ago = (last_year - 1, target_mon)
    else:
        twelve_months_ago = (last_year, target_mon)

    # Filter PMRs to last 12 months
    recent_pmrs = [
        pmr for pmr in sorted_pmrs
        if pmr.month >= twelve_months_ago
    ]

    # Get unique salary values
    salary_values = set(pmr.salary_monthly for pmr in recent_pmrs)

    pmrs_used = [
        LastSalaryPMRUsed(month=pmr.month, salary_monthly=pmr.salary_monthly)
        for pmr in recent_pmrs
    ]

    if len(salary_values) == 1:
        # Salary did not change
        return LastSalaryInfo(
            last_salary=sorted_pmrs[0].salary_monthly,
            method=LastSalaryMethod.LAST_PMR,
            salary_changed_in_last_year=False,
            pmrs_used=pmrs_used,
        )
    else:
        # Salary changed - use average
        total = sum(pmr.salary_monthly for pmr in recent_pmrs)
        avg_salary = total / len(recent_pmrs)
        return LastSalaryInfo(
            last_salary=avg_salary,
            method=LastSalaryMethod.AVG_12_MONTHS,
            salary_changed_in_last_year=True,
            pmrs_used=pmrs_used,
        )


def _compute_full_ot_monthly_pay(
    shifts: list[Shift],
    month: tuple[int, int],
) -> Decimal:
    """Compute full OT monthly pay for cleaning industry.

    This is the sum of hours × rate_multiplier × hourly_wage for all
    pricing_breakdown parts where tier > 0.
    """
    total = Decimal("0")
    year, mon = month

    for shift in shifts:
        if shift.assigned_day is None:
            continue
        if shift.assigned_day.year != year or shift.assigned_day.month != mon:
            continue
        if shift.pricing_breakdown is None:
            continue

        for pb in shift.pricing_breakdown:
            if pb.tier > 0:
                # Full pay = hours × rate_multiplier × hourly_wage
                full_pay = pb.hours * pb.rate_multiplier * pb.hourly_wage
                total += full_pay

    return total


def compute_severance(
    termination_reason: TerminationReason | None,
    industry: str,
    period_month_records: list[PeriodMonthRecord],
    month_aggregates: list[MonthAggregate],
    effective_periods: list[EffectivePeriod],
    total_employment_months: Decimal,
    actual_deposits: Decimal,
    shifts: list[Shift] | None = None,
    recreation_annual_by_month: dict[tuple[int, int], Decimal] | None = None,
    settings_path: Path | None = None,
) -> SeveranceData:
    """Compute severance pay.

    Args:
        termination_reason: The reason for termination
        industry: The industry ID
        period_month_records: List of period-month records
        month_aggregates: List of month aggregates
        effective_periods: List of effective periods
        total_employment_months: Total months of employment (decimal)
        actual_deposits: Actual deposits made by employer (from deductions_input)
        shifts: List of shifts (for OT calculation in cleaning)
        recreation_annual_by_month: Dict mapping (year, month) to annual recreation value for that month
        settings_path: Optional path to settings.json

    Returns:
        SeveranceData with complete calculation
    """
    # Load industry config
    industry_configs = load_industry_config(settings_path)
    config = industry_configs.get(industry, industry_configs["general"])

    # Initialize result
    result = SeveranceData(
        termination_reason=termination_reason,
        industry=industry,
        severance_rate=config.severance_rate,
        contribution_rate=config.contribution_rate,
    )

    # Set industry-specific rates
    if config.ot_addition:
        result.ot_addition_rate = config.ot_addition_rate
    if config.recreation_addition:
        result.recreation_addition_rate = config.recreation_addition_rate

    # Check eligibility
    if termination_reason is None:
        result.eligible = False
        result.ineligible_reason = "לא צוינה סיבת סיום העסקה"
        return result

    if total_employment_months < Decimal(config.min_months):
        result.eligible = False
        result.ineligible_reason = "לא השלים את תקופת העבודה המינימלית"
        return result

    result.eligible = True

    # Determine last salary
    last_salary_info = _determine_last_salary(period_month_records)
    result.last_salary_info = last_salary_info
    last_salary = last_salary_info.last_salary

    # Build month_aggregate lookup
    ma_lookup = {ma.month: ma for ma in month_aggregates}

    # =========================================================================
    # Compute Full Severance
    # =========================================================================

    full_base_total = Decimal("0")
    full_monthly_details = []
    period_subtotals: dict[str, list[SeveranceMonthlyDetail]] = {}

    for pmr in period_month_records:
        month = pmr.month
        ma = ma_lookup.get(month)
        job_scope = ma.job_scope if ma else Decimal("1")

        # Compute partial fraction
        days_employed, total_days, partial_fraction = _compute_partial_fraction(
            month, effective_periods, pmr.effective_period_id
        )

        # month_full_base = last_salary × severance_rate × job_scope × partial_fraction
        amount = last_salary * config.severance_rate * job_scope * partial_fraction
        full_base_total += amount

        detail = SeveranceMonthlyDetail(
            month=month,
            effective_period_id=pmr.effective_period_id,
            calendar_days_employed=days_employed,
            total_calendar_days=total_days,
            partial_fraction=partial_fraction,
            job_scope=job_scope,
            salary_used=last_salary,
            amount=amount,
        )
        full_monthly_details.append(detail)

        # Group by effective period
        if pmr.effective_period_id not in period_subtotals:
            period_subtotals[pmr.effective_period_id] = []
        period_subtotals[pmr.effective_period_id].append(detail)

    # Build period summaries for full severance
    full_period_summaries = []
    for ep in effective_periods:
        details = period_subtotals.get(ep.id, [])
        if not details:
            continue

        subtotal = sum(d.amount for d in details)
        # months_count = sum of partial_fractions (not count of PMRs)
        months_count = sum(d.partial_fraction for d in details)
        # avg_job_scope = weighted average by calendar_days_employed
        total_days = sum(d.calendar_days_employed for d in details)
        if total_days > 0:
            avg_job_scope = sum(d.job_scope * d.calendar_days_employed for d in details) / Decimal(total_days)
        else:
            avg_job_scope = Decimal("0")

        full_period_summaries.append(SeverancePeriodSummary(
            effective_period_id=ep.id,
            start=ep.start,
            end=ep.end,
            months_count=months_count,
            avg_job_scope=avg_job_scope,
            subtotal=subtotal,
        ))

    # =========================================================================
    # Compute Required Contributions
    # =========================================================================

    req_base_total = Decimal("0")
    req_monthly_details = []
    req_period_subtotals: dict[str, list[SeveranceMonthlyDetail]] = {}

    for pmr in period_month_records:
        month = pmr.month
        ma = ma_lookup.get(month)
        job_scope = ma.job_scope if ma else Decimal("1")

        # Compute partial fraction
        days_employed, total_days, partial_fraction = _compute_partial_fraction(
            month, effective_periods, pmr.effective_period_id
        )

        # month_required_base = salary_monthly × contribution_rate × job_scope × partial_fraction
        # Note: uses actual salary_monthly, NOT last_salary
        amount = pmr.salary_monthly * config.contribution_rate * job_scope * partial_fraction
        req_base_total += amount

        detail = SeveranceMonthlyDetail(
            month=month,
            effective_period_id=pmr.effective_period_id,
            calendar_days_employed=days_employed,
            total_calendar_days=total_days,
            partial_fraction=partial_fraction,
            job_scope=job_scope,
            salary_used=pmr.salary_monthly,  # Actual salary
            amount=amount,
        )
        req_monthly_details.append(detail)

        # Group by effective period
        if pmr.effective_period_id not in req_period_subtotals:
            req_period_subtotals[pmr.effective_period_id] = []
        req_period_subtotals[pmr.effective_period_id].append(detail)

    # Build period summaries for required contributions
    req_period_summaries = []
    for ep in effective_periods:
        details = req_period_subtotals.get(ep.id, [])
        if not details:
            continue

        subtotal = sum(d.amount for d in details)
        # months_count = sum of partial_fractions (not count of PMRs)
        months_count = sum(d.partial_fraction for d in details)
        # avg_job_scope = weighted average by calendar_days_employed
        total_days = sum(d.calendar_days_employed for d in details)
        if total_days > 0:
            avg_job_scope = sum(d.job_scope * d.calendar_days_employed for d in details) / Decimal(total_days)
        else:
            avg_job_scope = Decimal("0")
        # avg_salary = weighted average by calendar_days_employed
        if total_days > 0:
            avg_salary = sum(d.salary_used * d.calendar_days_employed for d in details) / Decimal(total_days)
        else:
            avg_salary = Decimal("0")

        req_period_summaries.append(SeverancePeriodSummary(
            effective_period_id=ep.id,
            start=ep.start,
            end=ep.end,
            months_count=months_count,
            avg_job_scope=avg_job_scope,
            avg_salary_monthly=avg_salary,
            subtotal=subtotal,
        ))

    # =========================================================================
    # Cleaning Industry Additions (OT + Recreation)
    # =========================================================================

    ot_total = Decimal("0")
    recreation_total = Decimal("0")
    ot_addition_data = None
    recreation_addition_data = None

    if config.ot_addition and shifts:
        ot_monthly_details = []
        for pmr in period_month_records:
            month = pmr.month
            ma = ma_lookup.get(month)
            job_scope = ma.job_scope if ma else Decimal("1")

            full_ot_pay = _compute_full_ot_monthly_pay(shifts, month)
            amount = full_ot_pay * config.ot_addition_rate * job_scope
            ot_total += amount

            ot_monthly_details.append(OTAdditionMonthlyDetail(
                month=month,
                effective_period_id=pmr.effective_period_id,
                full_ot_monthly_pay=full_ot_pay,
                job_scope=job_scope,
                amount=amount,
            ))

        ot_addition_data = OTAdditionData(
            rate=config.ot_addition_rate,
            total=ot_total,
            monthly_detail=ot_monthly_details,
        )

    if config.recreation_addition:
        rec_monthly_details = []
        recreation_pending = recreation_annual_by_month is None

        for pmr in period_month_records:
            month = pmr.month
            year, mon = month
            total_days = _get_calendar_days_in_month(year, mon)

            # Compute partial fraction
            days_employed, _, partial_fraction = _compute_partial_fraction(
                month, effective_periods, pmr.effective_period_id
            )

            # Look up annual recreation value for this specific month
            annual_value = (recreation_annual_by_month or {}).get(month, Decimal("0"))
            monthly_value = annual_value / Decimal("12")
            amount = monthly_value * config.recreation_addition_rate * partial_fraction

            if not recreation_pending:
                recreation_total += amount

            rec_monthly_details.append(RecreationAdditionMonthlyDetail(
                month=month,
                annual_recreation_value=annual_value,
                monthly_value=monthly_value,
                partial_fraction=partial_fraction,
                amount=amount if not recreation_pending else Decimal("0"),
            ))

        recreation_addition_data = RecreationAdditionData(
            rate=config.recreation_addition_rate,
            total=recreation_total,
            recreation_pending=recreation_pending,
            monthly_detail=rec_monthly_details,
        )

    # =========================================================================
    # Build Full Severance and Required Contributions Results
    # =========================================================================

    full_severance = FullSeveranceData(
        base_total=full_base_total,
        ot_total=ot_total,
        recreation_total=recreation_total,
        recreation_pending=recreation_addition_data.recreation_pending if recreation_addition_data else False,
        grand_total=full_base_total + ot_total + recreation_total,
        base_monthly_detail=full_monthly_details,
        period_summaries=full_period_summaries,
    )

    required_contributions = RequiredContributionsData(
        base_total=req_base_total,
        ot_total=ot_total,  # Same as full severance
        recreation_total=recreation_total,  # Same as full severance
        grand_total=req_base_total + ot_total + recreation_total,
        base_monthly_detail=req_monthly_details,
        period_summaries=req_period_summaries,
    )

    result.full_severance = full_severance
    result.required_contributions = required_contributions
    result.ot_addition = ot_addition_data
    result.recreation_addition = recreation_addition_data

    # =========================================================================
    # Path Determination
    # =========================================================================

    if termination_reason == TerminationReason.RESIGNED:
        # PATH C - Required contributions shortfall
        result.path = SeverancePath.CONTRIBUTIONS
        result.section_14_status = None
        result.limitation_type = SeveranceLimitationType.GENERAL
        result.claim_before_deductions = required_contributions.grand_total
        result.deduction_override = None  # Normal deduction
    else:
        # Fired or resigned_as_fired - check Section 14
        s14_difference = actual_deposits - required_contributions.grand_total

        result.section_14_comparison = Section14Comparison(
            actual_deposits=actual_deposits,
            required_contributions_total=required_contributions.grand_total,
            difference=s14_difference,
            status=Section14Status.HOLDS if s14_difference >= 0 else Section14Status.FALLS,
        )

        if s14_difference >= 0:
            # PATH A - Section 14 holds
            result.path = SeverancePath.SECTION_14_HOLDS
            result.section_14_status = Section14Status.HOLDS
            result.limitation_type = SeveranceLimitationType.NONE
            result.claim_before_deductions = full_severance.grand_total - required_contributions.grand_total
            result.deduction_override = Decimal("0")  # Fund belongs to worker
        else:
            # PATH B - Section 14 falls
            result.path = SeverancePath.SECTION_14_FALLS
            result.section_14_status = Section14Status.FALLS
            result.limitation_type = SeveranceLimitationType.NONE
            result.claim_before_deductions = full_severance.grand_total
            result.deduction_override = None  # Normal deduction

    result.total_claim = result.claim_before_deductions

    # =========================================================================
    # Monthly Breakdown (for limitation module)
    # =========================================================================

    # For PATH A, keep monthly breakdown even if claim is 0
    monthly_breakdown = []
    for pmr in period_month_records:
        month = pmr.month

        # Find the corresponding detail
        full_detail = next(
            (d for d in full_monthly_details if d.month == month and d.effective_period_id == pmr.effective_period_id),
            None
        )
        req_detail = next(
            (d for d in req_monthly_details if d.month == month and d.effective_period_id == pmr.effective_period_id),
            None
        )

        if result.path == SeverancePath.SECTION_14_HOLDS:
            # PATH A: claim = full - required per month
            full_amt = full_detail.amount if full_detail else Decimal("0")
            req_amt = req_detail.amount if req_detail else Decimal("0")
            claim_amount = full_amt - req_amt
        elif result.path == SeverancePath.SECTION_14_FALLS:
            # PATH B: claim = full per month
            claim_amount = full_detail.amount if full_detail else Decimal("0")
        else:
            # PATH C: claim = required per month
            claim_amount = req_detail.amount if req_detail else Decimal("0")

        monthly_breakdown.append(SeveranceMonthlyBreakdown(
            month=month,
            claim_amount=claim_amount,
        ))

    result.monthly_breakdown = monthly_breakdown

    return result
