"""Pipeline orchestrator for Claims Wizard.

This module orchestrates all calculation phases. Only this module
reads from and writes to the SSOT. All other modules are pure functions.

See docs/skills/claims-wizard-spec/PIPELINE.md for execution order.
"""

from .ssot import SSOT, SSOTInput
from .errors import PipelineError, PipelineResult, ValidationError


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
        # work_patterns_resolved = pattern_translator.translate(ssot.input.work_patterns)

        # Step 1: Weaver
        # weaver_result = weaver.run(
        #     employment_periods=ssot.input.employment_periods,
        #     work_patterns=work_patterns_resolved,
        #     salary_tiers=ssot.input.salary_tiers,
        #     rest_day=ssot.input.rest_day,
        # )
        # ssot.effective_periods = weaver_result.effective_periods
        # ssot.daily_records = weaver_result.daily_records
        # ssot.employment_gaps = weaver_result.employment_gaps
        # ssot.total_employment = weaver_result.total_employment

        # Step 2: OT stages 1-7
        # ot_result = ot_pipeline.run_stages_1_7(
        #     daily_records=ssot.daily_records,
        #     rest_day=ssot.input.rest_day,
        #     district=ssot.input.district,
        #     shabbat_times=static_data.shabbat_times,
        #     ot_config=settings.ot_config,
        # )
        # ssot.shifts = ot_result.shifts
        # ssot.weeks = ot_result.weeks

        # Step 5a: Seniority (parallel to Step 2)
        # seniority_result = seniority.compute(
        #     daily_records=ssot.daily_records,
        #     seniority_input=ssot.input.seniority_input,
        #     industry=ssot.input.industry,
        # )
        # ssot.seniority_monthly = seniority_result.monthly
        # ssot.seniority_totals = seniority_result.totals

        # Step 3: Aggregator
        # aggregator_result = aggregator.run(
        #     shifts=ssot.shifts,
        #     effective_periods=ssot.effective_periods,
        #     daily_records=ssot.daily_records,
        # )
        # ssot.period_month_records = aggregator_result.period_month_records
        # ssot.month_aggregates = aggregator_result.month_aggregates

        # Step 4: Salary Conversion
        # salary_conversion.run(
        #     period_month_records=ssot.period_month_records,
        #     effective_periods=ssot.effective_periods,
        #     minimum_wage=static_data.minimum_wage,
        # )

        # Step 5b: Job Scope
        # job_scope.run(
        #     month_aggregates=ssot.month_aggregates,
        #     full_time_hours_base=settings.full_time_hours_base,
        # )

        # =====================================================================
        # Phase 2 - Rights Calculation
        # =====================================================================

        # OT Stage 8 - Pricing
        # ot_pipeline.run_stage_8(
        #     shifts=ssot.shifts,
        #     period_month_records=ssot.period_month_records,
        #     right_toggles=ssot.input.right_toggles.get("overtime", {}),
        # )
        # ssot.rights_results.overtime = ...

        # Holidays
        # holidays_result = holidays.compute(
        #     weeks=ssot.weeks,
        #     daily_records=ssot.daily_records,
        #     effective_periods=ssot.effective_periods,
        #     period_month_records=ssot.period_month_records,
        #     holiday_dates=static_data.holiday_dates,
        #     rest_day=ssot.input.rest_day,
        # )
        # ssot.rights_results.holidays = holidays_result

        # Other rights (when defined)...

        # =====================================================================
        # Phase 3 - Post-processing
        # =====================================================================

        # Step 1: Limitation
        # limitation_result = limitation.compute(
        #     rights_results=ssot.rights_results,
        #     limitation_config=settings.limitation_config,
        #     filing_date=ssot.input.filing_date,
        # )
        # ssot.limitation_results = limitation_result

        # Step 2: Deductions
        # deduction_result = deductions.compute(
        #     limitation_results=ssot.limitation_results,
        #     deductions_input=ssot.input.deductions_input,
        # )
        # ssot.deduction_results = deduction_result

        # Step 3: Claim Summary
        # ssot.claim_summary = summary.compute(
        #     limitation_results=ssot.limitation_results,
        #     deduction_results=ssot.deduction_results,
        #     total_employment=ssot.total_employment,
        #     personal_details=ssot.input.personal_details,
        #     defendant_details=ssot.input.defendant_details,
        #     filing_date=ssot.input.filing_date,
        # )

        # =====================================================================
        # Phase 4 - Display formatting
        # =====================================================================

        # Duration Formatter
        # duration_formatter.fill_all(ssot)

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
