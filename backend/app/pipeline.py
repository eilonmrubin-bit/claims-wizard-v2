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
    SeveranceLimitationType,
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
from .modules.severance import compute_severance
from .modules.limitation import (
    get_limitation_type_for_right,
    filter_with_none_limitation,
)


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
    for window in ssot.limitation_results.timeline_data.limitation_windows:
        window.claimable_duration.display = _format_duration_display(
            window.claimable_duration.days
        )

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
                pattern_sources=ssot.input.pattern_sources,
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
            # Update daily_records with day_segments from stage 3.5
            if ot_result.daily_records:
                ssot.daily_records = ot_result.daily_records

        # Mark partial weeks (employment boundaries + gaps)
        if ssot.weeks and ssot.input.employment_periods:
            sorted_periods = sorted(ssot.input.employment_periods, key=lambda ep: ep.start)
            emp_start = sorted_periods[0].start
            emp_end = sorted_periods[-1].end
            heb_days = ['ב׳', 'ג׳', 'ד׳', 'ה׳', 'ו׳', 'ש׳', 'א׳']  # Mon=0..Sun=6
            sorted_weeks = sorted(ssot.weeks, key=lambda w: w.start_date)

            # Employment start: first week where emp_start > week.start_date
            for week in sorted_weeks:
                if week.start_date and emp_start > week.start_date:
                    week.is_partial = True
                    week.partial_reason = "employment_start"
                    week.partial_detail = f"תחילת העסקה {emp_start.strftime('%d.%m.%Y')} (יום {heb_days[emp_start.weekday()]})"
                    break

            # Employment end: last week where emp_end < week.end_date
            for week in reversed(sorted_weeks):
                if week.end_date and emp_end < week.end_date:
                    week.is_partial = True
                    week.partial_reason = "employment_end"
                    week.partial_detail = f"סיום העסקה {emp_end.strftime('%d.%m.%Y')} (יום {heb_days[emp_end.weekday()]})"
                    break

            # Gaps between employment periods
            if len(sorted_periods) > 1:
                for i in range(len(sorted_periods) - 1):
                    gap_start_date = sorted_periods[i].end  # last day of period i
                    gap_end_date = sorted_periods[i + 1].start  # first day of period i+1
                    for week in sorted_weeks:
                        # Week containing end of period i
                        if week.start_date and week.end_date and week.start_date <= gap_start_date <= week.end_date:
                            if gap_start_date > week.start_date:  # gap starts mid-week
                                if not week.is_partial:  # don't overwrite employment_start/end
                                    week.is_partial = True
                                    week.partial_reason = "gap_start"
                                    week.partial_detail = f"פער החל מ-{gap_start_date.strftime('%d.%m.%Y')}"
                        # Week containing start of next period
                        if week.start_date and week.end_date and week.start_date <= gap_end_date <= week.end_date:
                            if gap_end_date > week.start_date:  # period resumes mid-week
                                if not week.is_partial:
                                    week.is_partial = True
                                    week.partial_reason = "gap_end"
                                    week.partial_detail = f"חזרה לעבודה {gap_end_date.strftime('%d.%m.%Y')}"

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
            # Build lookup for effective_period by id
            ep_lookup = {ep.id: ep for ep in ssot.effective_periods}

            for pmr in ssot.period_month_records:
                ep = ep_lookup.get(pmr.effective_period_id)
                if ep:
                    process_period_month_record(
                        pmr=pmr,
                        ep=ep,
                        input_amount=ep.salary_amount,
                        input_type=ep.salary_type,
                        input_net_or_gross=ep.salary_net_or_gross,
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

            # Compute seniority eligibility date for holidays
            seniority_eligibility_date = None
            if ssot.seniority_monthly:
                for entry in ssot.seniority_monthly:
                    if entry.at_defendant_cumulative >= 3:
                        y, m = entry.month
                        # Eligibility = first day of NEXT month
                        if m == 12:
                            seniority_eligibility_date = date(y + 1, 1, 1)
                        else:
                            seniority_eligibility_date = date(y, m + 1, 1)
                        break

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

            def is_employed_in_year(year: int) -> bool:
                return any(dr.date.year == year for dr in ssot.daily_records)

            holidays_result = calculate_all_years(
                start_year=first_day.year,
                end_year=last_day.year,
                rest_day=ssot.input.rest_day,
                is_employed_on_date=is_employed_on_date,
                get_week_type=get_week_type,
                get_daily_salary=get_daily_salary,
                get_max_daily_salary_in_year=get_max_daily_salary_in_year,
                seniority_eligibility_date=seniority_eligibility_date,
                is_employed_in_year=is_employed_in_year,
            )

            ssot.rights_results.holidays = holidays_result

        # Severance
        if ssot.input.termination_reason and ssot.period_month_records and ssot.effective_periods:
            # Compute total employment months
            total_employment_months = ssot.total_employment.worked_duration.months_decimal

            # Get actual deposits from deductions_input
            actual_deposits = ssot.input.deductions_input.get("severance", Decimal("0"))

            severance_result = compute_severance(
                termination_reason=ssot.input.termination_reason,
                industry=ssot.input.industry,
                period_month_records=ssot.period_month_records,
                month_aggregates=ssot.month_aggregates,
                effective_periods=ssot.effective_periods,
                total_employment_months=total_employment_months,
                actual_deposits=actual_deposits,
                shifts=ssot.shifts,
                recreation_annual_value=None,  # Future: from recreation module
            )

            ssot.rights_results.severance = severance_result

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
            # Compute claimable_duration: effective_window_start → filing_date
            window_claimable_duration = compute_duration(
                general_window.effective_window_start,
                ssot.input.filing_date,
            )

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
                claimable_duration=window_claimable_duration,
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

            # Holidays - filter by checking each holiday's gregorian_date
            if ssot.rights_results.holidays:
                claimable_dur, excluded_dur = compute_right_durations("general")

                # full_amount is ALWAYS grand_total_claim (before limitation)
                full_amount = ssot.rights_results.holidays.grand_total_claim

                # Filter holidays by date - each holiday is either in or out of the window
                claimable_amount = Decimal("0")

                for year_result in ssot.rights_results.holidays.per_year:
                    # Check individual holidays
                    for holiday in year_result.holidays:
                        if holiday.claim_amount and holiday.gregorian_date:
                            # Holiday is claimable if its date is within the limitation window
                            if effective_window_start <= holiday.gregorian_date <= filing_date:
                                claimable_amount += holiday.claim_amount

                    # "Election day" (יום בחירה) has no specific date.
                    # Claimable if any part of the year overlaps with the limitation window.
                    if year_result.election_day_entitled and year_result.election_day_value:
                        # Check if any part of this year is within the limitation window
                        year_start = date(year_result.year, 1, 1)
                        year_end = date(year_result.year, 12, 31)
                        if year_start <= filing_date and year_end >= effective_window_start:
                            # Edge Case 10: If year is split by limitation, recalculate
                            # election_day_value using only salary_daily from claimable months
                            if (effective_window_start.year == year_result.year and
                                    effective_window_start.month > 1):
                                # Year is split - find max salary_daily from claimable months only
                                adjusted_value = Decimal("0")
                                for pmr in ssot.period_month_records:
                                    pmr_year, pmr_month = pmr.month
                                    if pmr_year == year_result.year:
                                        # Month is claimable if it starts on or after effective_window_start
                                        month_start = date(pmr_year, pmr_month, 1)
                                        if month_start >= effective_window_start:
                                            if pmr.salary_daily > adjusted_value:
                                                adjusted_value = pmr.salary_daily
                                # Use adjusted value (may be 0 if no claimable months have records)
                                if adjusted_value > Decimal("0"):
                                    claimable_amount += adjusted_value
                            else:
                                # Year is fully within window - use original value
                                claimable_amount += year_result.election_day_value

                excluded_amount = full_amount - claimable_amount

                per_right_results["holidays"] = RightLimitationResult(
                    limitation_type_id="general",
                    full_amount=full_amount,
                    claimable_amount=claimable_amount,
                    excluded_amount=excluded_amount,
                    claimable_duration=claimable_dur,
                    excluded_duration=excluded_dur,
                )

            # Severance - limitation type depends on the path
            if ssot.rights_results.severance and ssot.rights_results.severance.eligible:
                severance = ssot.rights_results.severance
                full_amount = severance.total_claim

                if severance.limitation_type == SeveranceLimitationType.NONE:
                    # PATH A/B: No limitation - everything is claimable
                    claimable_amount = full_amount
                    excluded_amount = Decimal("0")
                    limitation_type_id = "none"
                else:
                    # PATH C (resigned): General limitation
                    sev_monthly = {
                        mb.month: mb.claim_amount
                        for mb in severance.monthly_breakdown
                    }
                    claimable_amount, excluded_amount, _ = filter_monthly_results(
                        sev_monthly,
                        general_window.effective_window_start,
                        ssot.input.filing_date,
                    )
                    limitation_type_id = "general"

                claimable_dur, excluded_dur = compute_right_durations(limitation_type_id)
                per_right_results["severance"] = RightLimitationResult(
                    limitation_type_id=limitation_type_id,
                    full_amount=full_amount,
                    claimable_amount=claimable_amount,
                    excluded_amount=excluded_amount,
                    claimable_duration=claimable_dur,
                    excluded_duration=excluded_dur,
                )

            ssot.limitation_results.per_right = per_right_results

            # Fill timeline_data
            ssot.limitation_results.timeline_data.employment_start = employment_start
            ssot.limitation_results.timeline_data.employment_end = employment_end
            ssot.limitation_results.timeline_data.filing_date = filing_date

            # Limitation windows for timeline (claimable_duration already computed in ssot_window)
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

        # Build deduction overrides from rights that specify them
        deduction_overrides = {}
        if ssot.rights_results.severance and ssot.rights_results.severance.eligible:
            # Severance may have deduction_override (e.g., 0 for PATH A)
            if ssot.rights_results.severance.deduction_override is not None:
                deduction_overrides["severance"] = ssot.rights_results.severance.deduction_override

        deduction_results = apply_all_deductions(
            rights_amounts=rights_amounts,
            deductions=ssot.input.deductions_input,
            deduction_overrides=deduction_overrides if deduction_overrides else None,
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
