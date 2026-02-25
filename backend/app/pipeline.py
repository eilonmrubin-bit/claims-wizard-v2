"""Pipeline orchestrator for Claims Wizard.

This module orchestrates all calculation phases. Only this module
reads from and writes to the SSOT. All other modules are pure functions.

See docs/skills/claims-wizard-spec/PIPELINE.md for execution order.
"""

from datetime import date, timedelta
from decimal import Decimal

from .ssot import (
    SSOT,
    SSOTInput,
    OvertimeResult,
    OvertimeMonthlyBreakdown,
    RightLimitationResult,
    LimitationResults,
    LimitationWindow as SSOTLimitationWindow,
    FreezePeriodApplied,
    TimelineWorkPeriod,
    TimelineSummary,
    WeekType,
)
from .errors import PipelineError, PipelineResult, ValidationError

from .modules.pattern_translator import translate as translate_patterns
from .modules.weaver.orchestrator import run_weaver
from .modules.overtime.orchestrator import run_overtime_stages_1_to_7
from .modules.overtime.stage8_pricing import (
    run_pricing,
    calculate_monthly_totals,
    calculate_grand_total,
)
from .modules.aggregator import run_aggregator
from .modules.salary_conversion import process_period_month_record
from .modules.job_scope import run_job_scope
from .modules.seniority import (
    compute_seniority_method_a,
    compute_seniority_method_b,
    SeniorityMethod,
)
from .modules.holidays import calculate_all_years
from .modules.limitation import (
    compute_limitation_window,
    filter_monthly_results,
    compute_duration,
    LimitationConfig,
    FreezePeriod,
    GENERAL_LIMITATION,
    DEFAULT_WAR_FREEZE,
)
from .modules.deductions import apply_all_deductions
from .modules.summary import compute_summary


def _format_duration_display(days: int) -> str:
    """Format days into Hebrew display string."""
    if days == 0:
        return ""

    years = days // 365
    remaining = days % 365
    months = remaining // 30
    days_left = remaining % 30

    parts = []
    if years > 0:
        parts.append(f"{years} שנים" if years > 1 else "שנה")
    if months > 0:
        parts.append(f"{months} חודשים" if months > 1 else "חודש")
    if days_left > 0:
        parts.append(f"{days_left} ימים" if days_left > 1 else "יום")

    if len(parts) == 0:
        return ""
    elif len(parts) == 1:
        return parts[0]
    elif len(parts) == 2:
        return f"{parts[0]} ו{parts[1]}"
    else:
        return f"{parts[0]}, {parts[1]} ו{parts[2]}"


def _fill_duration_displays(ssot: SSOT) -> None:
    """Fill display field in all Duration objects (Phase 4)."""
    # Effective periods
    for ep in ssot.effective_periods:
        ep.duration.display = _format_duration_display(ep.duration.days)

    # Employment gaps
    for gap in ssot.employment_gaps:
        gap.duration.display = _format_duration_display(gap.duration.days)

    # Total employment
    ssot.total_employment.total_duration.display = _format_duration_display(
        ssot.total_employment.total_duration.days
    )
    ssot.total_employment.worked_duration.display = _format_duration_display(
        ssot.total_employment.worked_duration.days
    )
    ssot.total_employment.gap_duration.display = _format_duration_display(
        ssot.total_employment.gap_duration.days
    )

    # Limitation results - windows freeze periods
    for window in ssot.limitation_results.windows:
        for fp in window.freeze_periods_applied:
            fp.duration.display = _format_duration_display(fp.duration.days)

    # Limitation results - per_right durations
    for right_result in ssot.limitation_results.per_right.values():
        right_result.claimable_duration.display = _format_duration_display(
            right_result.claimable_duration.days
        )
        if right_result.excluded_duration:
            right_result.excluded_duration.display = _format_duration_display(
                right_result.excluded_duration.days
            )

    # Limitation results - timeline_data
    for fp in ssot.limitation_results.timeline_data.freeze_periods:
        fp.duration.display = _format_duration_display(fp.duration.days)

    for wp in ssot.limitation_results.timeline_data.work_periods:
        wp.duration.display = _format_duration_display(wp.duration.days)


def run_full_pipeline(ssot_input: SSOTInput) -> PipelineResult:
    """Run the complete calculation pipeline.

    Args:
        ssot_input: User input (Layer 0)

    Returns:
        PipelineResult with success status and full SSOT or error
    """
    ssot = SSOT(input=ssot_input)

    try:
        # =====================================================================
        # Phase 1 - Initial Processing
        # =====================================================================

        # Step 0: Pattern Translator
        if ssot.input.work_patterns:
            translation_result = translate_patterns(
                work_patterns=ssot.input.work_patterns,
                rest_day=ssot.input.rest_day,
            )
            if translation_result.errors:
                raise PipelineError(
                    phase="pattern_translator",
                    module="pattern_translator.py",
                    errors=translation_result.errors,
                )
            work_patterns_resolved = translation_result.work_patterns
        else:
            work_patterns_resolved = []

        # Step 1: Weaver
        if ssot.input.employment_periods and work_patterns_resolved and ssot.input.salary_tiers:
            weaver_result = run_weaver(
                employment_periods=ssot.input.employment_periods,
                work_patterns=work_patterns_resolved,
                salary_tiers=ssot.input.salary_tiers,
                rest_day=ssot.input.rest_day.value,
            )

            if not weaver_result.success:
                raise PipelineError(
                    phase="weaver",
                    module="weaver/orchestrator.py",
                    errors=weaver_result.errors,
                )

            ssot.effective_periods = weaver_result.effective_periods
            ssot.daily_records = weaver_result.daily_records
            ssot.employment_gaps = weaver_result.employment_gaps
            ssot.total_employment = weaver_result.total_employment

        # Step 2: OT stages 1-7
        if ssot.daily_records:
            ot_result = run_overtime_stages_1_to_7(
                daily_records=ssot.daily_records,
                rest_day=ssot.input.rest_day,
                district=ssot.input.district,
            )

            if not ot_result.success:
                raise PipelineError(
                    phase="overtime",
                    module="overtime/orchestrator.py",
                    errors=[
                        ValidationError(
                            type="ot_error",
                            message=e,
                            details={},
                        )
                        for e in (ot_result.errors or [])
                    ],
                )

            ssot.shifts = ot_result.shifts
            ssot.weeks = ot_result.weeks

        # Step 5a: Seniority (parallel to Step 2)
        if ssot.input.employment_periods:
            first_day = min(ep.start for ep in ssot.input.employment_periods)
            last_day = max(ep.end for ep in ssot.input.employment_periods)

            # Build lookup for work months from daily records
            work_months = set()
            for dr in ssot.daily_records:
                if dr.is_work_day:
                    work_months.add((dr.date.year, dr.date.month))

            def did_work_in_month(year: int, month: int) -> bool:
                return (year, month) in work_months

            seniority_method = ssot.input.seniority_input.method
            if seniority_method == SeniorityMethod.PRIOR_PLUS_PATTERN:
                prior_months = ssot.input.seniority_input.prior_months or 0
                seniority_result = compute_seniority_method_a(
                    prior_months=prior_months,
                    employment_start=first_day,
                    employment_end=last_day,
                    did_work_in_month=did_work_in_month,
                )
            elif seniority_method == SeniorityMethod.TOTAL_PLUS_PATTERN:
                seniority_result = compute_seniority_method_b(
                    total_industry_months=ssot.input.seniority_input.total_industry_months or 0,
                    employment_start=first_day,
                    employment_end=last_day,
                    did_work_in_month=did_work_in_month,
                )
            else:
                # Default to method A with 0 prior
                seniority_result = compute_seniority_method_a(
                    prior_months=0,
                    employment_start=first_day,
                    employment_end=last_day,
                    did_work_in_month=did_work_in_month,
                )

            ssot.seniority_monthly = seniority_result.monthly
            ssot.seniority_totals = seniority_result.totals

        # Step 3: Aggregator
        if ssot.shifts:
            aggregator_result = run_aggregator(ssot.shifts)
            ssot.period_month_records = aggregator_result.period_month_records
            ssot.month_aggregates = aggregator_result.month_aggregates

        # Step 4: Salary Conversion
        if ssot.period_month_records and ssot.effective_periods:
            # Build lookup for salary tier by effective_period_id
            ep_salary_lookup = {
                ep.id: (ep.salary_amount, ep.salary_type, ep.salary_net_or_gross)
                for ep in ssot.effective_periods
            }

            for pmr in ssot.period_month_records:
                salary_info = ep_salary_lookup.get(pmr.effective_period_id)
                if salary_info:
                    amount, stype, net_or_gross = salary_info
                    process_period_month_record(
                        pmr=pmr,
                        input_amount=amount,
                        input_type=stype,
                        input_net_or_gross=net_or_gross,
                        week_type=WeekType.FIVE_DAY,  # Default
                    )

        # Step 5b: Job Scope
        if ssot.month_aggregates:
            run_job_scope(ssot.month_aggregates)

        # =====================================================================
        # Phase 2 - Rights Calculation
        # =====================================================================

        # OT Stage 8 - Pricing
        if ssot.shifts and ssot.period_month_records:
            # Build lookup for period_month_records
            pmr_lookup = {
                (pmr.effective_period_id, pmr.month): pmr
                for pmr in ssot.period_month_records
            }

            employer_paid_rest = ssot.input.right_toggles.get("overtime", {}).get(
                "employer_paid_rest_premium", False
            )

            ssot.shifts = run_pricing(
                shifts=ssot.shifts,
                period_month_records=pmr_lookup,
                employer_paid_rest_premium=employer_paid_rest,
            )

            # Build overtime result
            monthly_totals = calculate_monthly_totals(ssot.shifts)
            grand_total = calculate_grand_total(ssot.shifts)

            monthly_breakdown = []
            for month, claim_amount in sorted(monthly_totals.items()):
                monthly_breakdown.append(OvertimeMonthlyBreakdown(
                    month=month,
                    claim_amount=claim_amount,
                ))

            ssot.rights_results.overtime = OvertimeResult(
                total_claim=grand_total,
                monthly_breakdown=monthly_breakdown,
            )

        # Holidays
        if ssot.daily_records and ssot.period_month_records:
            first_day = min(dr.date for dr in ssot.daily_records)
            last_day = max(dr.date for dr in ssot.daily_records)

            # Build lookups
            daily_lookup = {dr.date: dr for dr in ssot.daily_records}
            pmr_lookup = {
                (pmr.effective_period_id, pmr.month): pmr
                for pmr in ssot.period_month_records
            }

            # Week type lookup from weeks
            week_type_by_week_id = {w.id: w.week_type for w in ssot.weeks}

            def is_employed_on_date(d: date) -> bool:
                return d in daily_lookup

            def get_week_type(d: date) -> WeekType:
                # Find week for this date
                for w in ssot.weeks:
                    if w.start_date and w.end_date:
                        if w.start_date <= d <= w.end_date:
                            return w.week_type
                return WeekType.FIVE_DAY

            def get_daily_salary(d: date) -> Decimal:
                dr = daily_lookup.get(d)
                if dr:
                    key = (dr.effective_period_id, (d.year, d.month))
                    pmr = pmr_lookup.get(key)
                    if pmr:
                        return pmr.salary_daily
                return Decimal("0")

            def get_max_daily_salary_in_year(year: int) -> Decimal:
                max_salary = Decimal("0")
                for pmr in ssot.period_month_records:
                    if pmr.month[0] == year and pmr.salary_daily > max_salary:
                        max_salary = pmr.salary_daily
                return max_salary

            def count_employment_days_in_year(year: int) -> int:
                return sum(
                    1 for dr in ssot.daily_records
                    if dr.date.year == year and dr.is_work_day
                )

            holidays_result = calculate_all_years(
                start_year=first_day.year,
                end_year=last_day.year,
                rest_day=ssot.input.rest_day,
                is_employed_on_date=is_employed_on_date,
                get_week_type=get_week_type,
                get_daily_salary=get_daily_salary,
                get_max_daily_salary_in_year=get_max_daily_salary_in_year,
                count_employment_days_in_year=count_employment_days_in_year,
            )

            ssot.rights_results.holidays = holidays_result

        # =====================================================================
        # Phase 3 - Post-processing
        # =====================================================================

        # Step 1: Limitation
        if ssot.input.filing_date:
            # Build limitation config
            freeze_periods = [DEFAULT_WAR_FREEZE]
            limitation_config = LimitationConfig(
                filing_date=ssot.input.filing_date,
                freeze_periods=freeze_periods,
            )

            # Compute general limitation window
            general_window = compute_limitation_window(
                GENERAL_LIMITATION,
                limitation_config,
            )

            # Convert to SSOT LimitationWindow format with Duration
            ssot_window = SSOTLimitationWindow(
                type_id=general_window.type_id,
                type_name=general_window.type_name,
                base_window_start=general_window.base_window_start,
                effective_window_start=general_window.effective_window_start,
                freeze_periods_applied=[
                    FreezePeriodApplied(
                        name=fp.name,
                        start_date=fp.start_date,
                        end_date=fp.end_date,
                        days=fp.days,
                        duration=compute_duration(fp.start_date, fp.end_date),
                    )
                    for fp in general_window.freeze_periods_applied
                ],
            )

            ssot.limitation_results.windows = [ssot_window]

            # Get employment dates
            employment_start = ssot.total_employment.first_day
            employment_end = ssot.total_employment.last_day
            filing_date = ssot.input.filing_date

            # Compute claimable period boundaries
            effective_window_start = general_window.effective_window_start

            # Filter each right by limitation
            per_right_results = {}

            # Helper to compute durations for a right
            def compute_right_durations(
                limitation_type_id: str,
            ) -> tuple:
                """Compute claimable and excluded durations for a right."""
                # Get the window for this limitation type
                window_start = effective_window_start

                # Claimable period: intersection of [effective_window_start, filing_date]
                # with [employment_start, employment_end]
                if employment_start and employment_end:
                    claimable_start = max(window_start, employment_start)
                    claimable_end = min(filing_date, employment_end)

                    if claimable_start <= claimable_end:
                        claimable_dur = compute_duration(claimable_start, claimable_end)
                    else:
                        claimable_dur = compute_duration(date.today(), date.today())
                        claimable_dur.days = 0

                    # Excluded period: employment before effective_window_start
                    if employment_start < window_start:
                        excluded_end = min(window_start - timedelta(days=1), employment_end)
                        if employment_start <= excluded_end:
                            excluded_dur = compute_duration(employment_start, excluded_end)
                        else:
                            excluded_dur = None
                    else:
                        excluded_dur = None
                else:
                    claimable_dur = compute_duration(date.today(), date.today())
                    claimable_dur.days = 0
                    excluded_dur = None

                return claimable_dur, excluded_dur

            # Overtime
            if ssot.rights_results.overtime:
                ot_monthly = {
                    mb.month: mb.claim_amount
                    for mb in ssot.rights_results.overtime.monthly_breakdown
                }
                total_claimable, total_excluded, _ = filter_monthly_results(
                    ot_monthly,
                    general_window.effective_window_start,
                    ssot.input.filing_date,
                )
                claimable_dur, excluded_dur = compute_right_durations("general")
                per_right_results["overtime"] = RightLimitationResult(
                    limitation_type_id="general",
                    full_amount=ssot.rights_results.overtime.total_claim,
                    claimable_amount=total_claimable,
                    excluded_amount=total_excluded,
                    claimable_duration=claimable_dur,
                    excluded_duration=excluded_dur,
                )

            # Holidays
            if ssot.rights_results.holidays:
                claimable_dur, excluded_dur = compute_right_durations("general")
                per_right_results["holidays"] = RightLimitationResult(
                    limitation_type_id="general",
                    full_amount=ssot.rights_results.holidays.grand_total_claim,
                    claimable_amount=ssot.rights_results.holidays.grand_total_claim,
                    excluded_amount=Decimal("0"),
                    claimable_duration=claimable_dur,
                    excluded_duration=excluded_dur,
                )

            ssot.limitation_results.per_right = per_right_results

            # Fill timeline_data
            ssot.limitation_results.timeline_data.employment_start = employment_start
            ssot.limitation_results.timeline_data.employment_end = employment_end
            ssot.limitation_results.timeline_data.filing_date = filing_date

            # Limitation windows for timeline (with claimable_duration)
            timeline_windows = []
            if effective_window_start and filing_date:
                window_claimable_dur = compute_duration(effective_window_start, filing_date)
            else:
                window_claimable_dur = compute_duration(date.today(), date.today())
                window_claimable_dur.days = 0

            # Note: SSOTLimitationWindow doesn't have claimable_duration field directly
            # The claimable_duration is computed per-right, so we just store the windows
            ssot.limitation_results.timeline_data.limitation_windows = [ssot_window]

            # Freeze periods for timeline
            ssot.limitation_results.timeline_data.freeze_periods = [
                FreezePeriodApplied(
                    name=fp.name,
                    start_date=fp.start_date,
                    end_date=fp.end_date,
                    days=fp.days,
                    duration=compute_duration(fp.start_date, fp.end_date),
                )
                for fp in general_window.freeze_periods_applied
            ]

            # Work periods for timeline (from effective_periods)
            work_periods = []
            for ep in ssot.effective_periods:
                work_periods.append(TimelineWorkPeriod(
                    start_date=ep.start,
                    end_date=ep.end,
                    duration=compute_duration(ep.start, ep.end),
                ))
            ssot.limitation_results.timeline_data.work_periods = work_periods

            # Summary
            total_employment_days = ssot.total_employment.worked_duration.days if ssot.total_employment.worked_duration else 0

            # Claimable days for general limitation
            if employment_start and employment_end and effective_window_start and filing_date:
                claimable_start = max(effective_window_start, employment_start)
                claimable_end = min(filing_date, employment_end)
                if claimable_start <= claimable_end:
                    claimable_days_general = (claimable_end - claimable_start).days + 1
                else:
                    claimable_days_general = 0
                excluded_days_general = max(0, total_employment_days - claimable_days_general)
            else:
                claimable_days_general = 0
                excluded_days_general = 0

            # Total freeze days that affected the window
            total_freeze_days = sum(fp.days for fp in general_window.freeze_periods_applied)

            ssot.limitation_results.timeline_data.summary = TimelineSummary(
                total_employment_days=total_employment_days,
                claimable_days_general=claimable_days_general,
                excluded_days_general=excluded_days_general,
                total_freeze_days=total_freeze_days,
            )

        # Step 2: Deductions
        rights_amounts = {}
        for right_id, limitation_result in ssot.limitation_results.per_right.items():
            rights_amounts[right_id] = limitation_result.claimable_amount

        deduction_results = apply_all_deductions(
            rights_amounts=rights_amounts,
            deductions=ssot.input.deductions_input,
        )
        ssot.deduction_results = deduction_results

        # Step 3: Claim Summary
        if ssot.limitation_results.per_right or ssot.deduction_results:
            ssot.claim_summary = compute_summary(
                limitation_results=ssot.limitation_results,
                deduction_results=ssot.deduction_results,
                total_employment=ssot.total_employment,
                personal_details=ssot.input.personal_details,
                defendant_details=ssot.input.defendant_details,
                filing_date=ssot.input.filing_date,
            )

        # =====================================================================
        # Phase 4 - Display formatting
        # =====================================================================

        _fill_duration_displays(ssot)

        return PipelineResult(success=True, ssot=ssot)

    except PipelineError as e:
        return PipelineResult(success=False, error=e)
    except Exception as e:
        # Wrap unexpected errors
        error = PipelineError(
            phase="unknown",
            module="pipeline",
            errors=[
                ValidationError(
                    type="internal_error",
                    message="שגיאה פנימית בחישוב",
                    details={"exception": str(e)},
                )
            ],
        )
        return PipelineResult(success=False, error=error)
