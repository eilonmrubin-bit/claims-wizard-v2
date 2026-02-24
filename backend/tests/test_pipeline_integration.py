"""Integration test for the full pipeline.

Tests that the pipeline runs from raw input to full SSOT with results.
"""

from datetime import date, time
from decimal import Decimal

import pytest

from app.pipeline import run_full_pipeline
from app.ssot import (
    SSOTInput,
    PersonalDetails,
    DefendantDetails,
    EmploymentPeriod,
    WorkPattern,
    SalaryTier,
    TimeRange,
    SalaryType,
    NetOrGross,
    RestDay,
    District,
    SeniorityInput,
    SeniorityMethod,
    Duration,
)


class TestFullPipelineIntegration:
    """Integration test: full input through entire pipeline."""

    def test_full_pipeline_from_raw_input_to_claim_summary(self):
        """Run complete input through all phases and verify SSOT is populated.

        Test scenario:
        - Worker: John Doe
        - Defendant: ABC Company
        - Employment: 2023-01-01 to 2023-06-30 (6 months)
        - Work pattern: Sunday-Thursday, 08:00-17:00 with 30min break
        - Salary: 50 NIS/hour gross
        - Filing date: 2024-01-15
        - Rest day: Saturday
        """
        # Build full input
        ssot_input = SSOTInput(
            personal_details=PersonalDetails(
                id_number="123456789",
                first_name="John",
                last_name="Doe",
                birth_year=1980,
            ),
            defendant_details=DefendantDetails(
                name="ABC Company",
                id_number="987654321",
            ),
            employment_periods=[
                EmploymentPeriod(
                    id="ep1",
                    start=date(2023, 1, 1),
                    end=date(2023, 6, 30),
                    duration=Duration(),
                ),
            ],
            work_patterns=[
                WorkPattern(
                    id="wp1",
                    start=date(2023, 1, 1),
                    end=date(2023, 6, 30),
                    duration=Duration(),
                    work_days=[0, 1, 2, 3, 4],  # Sunday-Thursday
                    default_shifts=[
                        TimeRange(start_time=time(8, 0), end_time=time(17, 0)),
                    ],
                    default_breaks=[
                        TimeRange(start_time=time(12, 0), end_time=time(12, 30)),
                    ],
                ),
            ],
            salary_tiers=[
                SalaryTier(
                    id="st1",
                    start=date(2023, 1, 1),
                    end=date(2023, 6, 30),
                    duration=Duration(),
                    amount=Decimal("50"),
                    type=SalaryType.HOURLY,
                    net_or_gross=NetOrGross.GROSS,
                ),
            ],
            rest_day=RestDay.SATURDAY,
            district=District.TEL_AVIV,
            industry="general",
            filing_date=date(2024, 1, 15),
            seniority_input=SeniorityInput(
                method=SeniorityMethod.PRIOR_PLUS_PATTERN,
                prior_months=0,
            ),
            right_toggles={},
            deductions_input={},
        )

        # Run the full pipeline
        result = run_full_pipeline(ssot_input)

        # =====================================================================
        # Verify pipeline success
        # =====================================================================
        assert result.success is True, f"Pipeline failed: {result.error}"
        assert result.ssot is not None
        assert result.error is None

        ssot = result.ssot

        # =====================================================================
        # Phase 1 - Initial Processing
        # =====================================================================

        # Weaver output
        assert len(ssot.effective_periods) > 0, "No effective periods created"
        assert len(ssot.daily_records) > 0, "No daily records created"
        assert ssot.total_employment.first_day == date(2023, 1, 1)
        assert ssot.total_employment.last_day == date(2023, 6, 30)

        # Check daily records span the employment period
        dr_dates = {dr.date for dr in ssot.daily_records}
        assert date(2023, 1, 1) in dr_dates
        assert date(2023, 6, 30) in dr_dates

        # OT stages 1-7 output
        assert len(ssot.shifts) > 0, "No shifts created"
        assert len(ssot.weeks) > 0, "No weeks created"

        # Verify shifts have OT fields populated
        first_shift = ssot.shifts[0]
        assert first_shift.net_hours > 0, "Shift net_hours not calculated"
        assert first_shift.regular_hours >= 0, "Shift regular_hours not set"

        # Seniority output
        assert len(ssot.seniority_monthly) > 0, "No seniority monthly records"
        assert ssot.seniority_totals.at_defendant_months > 0, "No seniority at defendant"

        # Aggregator output
        assert len(ssot.period_month_records) > 0, "No period_month_records"
        assert len(ssot.month_aggregates) > 0, "No month_aggregates"

        # Verify period_month_records have hours
        for pmr in ssot.period_month_records:
            assert pmr.total_regular_hours > 0, f"No regular hours for {pmr.month}"

        # Salary conversion output
        for pmr in ssot.period_month_records:
            assert pmr.salary_hourly > 0, f"No hourly salary for {pmr.month}"
            assert pmr.salary_daily > 0, f"No daily salary for {pmr.month}"

        # Job scope output
        for ma in ssot.month_aggregates:
            assert ma.job_scope > 0, f"No job scope for {ma.month}"
            assert ma.job_scope <= Decimal("1"), f"Job scope > 100% for {ma.month}"

        # =====================================================================
        # Phase 2 - Rights Calculation
        # =====================================================================

        # OT Stage 8 pricing
        assert ssot.rights_results.overtime is not None, "No overtime result"
        assert ssot.rights_results.overtime.total_claim >= 0, "No OT claim calculated"

        # Verify some shifts have pricing
        priced_shifts = [s for s in ssot.shifts if s.claim_amount is not None]
        assert len(priced_shifts) > 0, "No shifts were priced"

        # Holidays
        assert ssot.rights_results.holidays is not None, "No holidays result"
        assert len(ssot.rights_results.holidays.per_year) > 0, "No holiday years"

        # =====================================================================
        # Phase 3 - Post-processing
        # =====================================================================

        # Limitation
        assert len(ssot.limitation_results.windows) > 0, "No limitation windows"
        assert len(ssot.limitation_results.per_right) > 0, "No limitation per_right"

        # Verify limitation was applied to overtime
        assert "overtime" in ssot.limitation_results.per_right
        ot_limitation = ssot.limitation_results.per_right["overtime"]
        assert ot_limitation.full_amount >= 0

        # Deductions
        assert len(ssot.deduction_results) > 0, "No deduction results"

        # Claim summary
        assert ssot.claim_summary is not None
        assert len(ssot.claim_summary.per_right) > 0, "No rights in summary"
        assert ssot.claim_summary.employment_summary.worker_name == "John Doe"
        assert ssot.claim_summary.employment_summary.defendant_name == "ABC Company"

        # =====================================================================
        # Phase 4 - Display formatting
        # =====================================================================

        # Duration displays should be filled
        assert ssot.total_employment.total_duration.display != "", "No duration display"

    def test_pipeline_with_deductions(self):
        """Test pipeline with employer deductions applied."""
        ssot_input = SSOTInput(
            personal_details=PersonalDetails(first_name="Test", last_name="Worker"),
            defendant_details=DefendantDetails(name="Test Corp"),
            employment_periods=[
                EmploymentPeriod(
                    id="ep1",
                    start=date(2023, 1, 1),
                    end=date(2023, 3, 31),
                ),
            ],
            work_patterns=[
                WorkPattern(
                    id="wp1",
                    start=date(2023, 1, 1),
                    end=date(2023, 3, 31),
                    work_days=[0, 1, 2, 3, 4],
                    default_shifts=[
                        TimeRange(start_time=time(8, 0), end_time=time(17, 0)),
                    ],
                    default_breaks=[
                        TimeRange(start_time=time(12, 0), end_time=time(12, 30)),
                    ],
                ),
            ],
            salary_tiers=[
                SalaryTier(
                    id="st1",
                    start=date(2023, 1, 1),
                    end=date(2023, 3, 31),
                    amount=Decimal("60"),
                    type=SalaryType.HOURLY,
                    net_or_gross=NetOrGross.GROSS,
                ),
            ],
            rest_day=RestDay.SATURDAY,
            district=District.TEL_AVIV,
            filing_date=date(2024, 1, 15),
            deductions_input={
                "overtime": Decimal("500"),  # Deduct 500 from overtime
            },
        )

        result = run_full_pipeline(ssot_input)

        assert result.success is True
        ssot = result.ssot

        # Check deduction was applied
        assert "overtime" in ssot.deduction_results
        ot_deduction = ssot.deduction_results["overtime"]
        assert ot_deduction.deduction_amount == Decimal("500")

        # Net amount should be calculated - deduction
        if ot_deduction.calculated_amount > Decimal("500"):
            assert ot_deduction.net_amount == ot_deduction.calculated_amount - Decimal("500")
            assert ot_deduction.show_right is True

    def test_pipeline_with_employer_paid_rest_premium(self):
        """Test pipeline with employer_paid_rest_premium toggle."""
        ssot_input = SSOTInput(
            employment_periods=[
                EmploymentPeriod(
                    id="ep1",
                    start=date(2023, 1, 1),
                    end=date(2023, 2, 28),
                ),
            ],
            work_patterns=[
                WorkPattern(
                    id="wp1",
                    start=date(2023, 1, 1),
                    end=date(2023, 2, 28),
                    work_days=[0, 1, 2, 3, 4, 5, 6],  # Include Saturday work
                    default_shifts=[
                        TimeRange(start_time=time(8, 0), end_time=time(16, 0)),
                    ],
                ),
            ],
            salary_tiers=[
                SalaryTier(
                    id="st1",
                    start=date(2023, 1, 1),
                    end=date(2023, 2, 28),
                    amount=Decimal("40"),
                    type=SalaryType.HOURLY,
                    net_or_gross=NetOrGross.GROSS,
                ),
            ],
            rest_day=RestDay.SATURDAY,
            district=District.TEL_AVIV,
            filing_date=date(2024, 1, 15),
            right_toggles={
                "overtime": {
                    "employer_paid_rest_premium": True,
                },
            },
        )

        result = run_full_pipeline(ssot_input)

        assert result.success is True
        assert result.ssot.rights_results.overtime is not None

    def test_pipeline_short_employment_below_holiday_threshold(self):
        """Test pipeline with employment below 1/10 year threshold for holidays."""
        # 30 days is below threshold (365 * 0.1 = 36.5 days)
        ssot_input = SSOTInput(
            employment_periods=[
                EmploymentPeriod(
                    id="ep1",
                    start=date(2023, 1, 1),
                    end=date(2023, 1, 30),
                ),
            ],
            work_patterns=[
                WorkPattern(
                    id="wp1",
                    start=date(2023, 1, 1),
                    end=date(2023, 1, 30),
                    work_days=[0, 1, 2, 3, 4],
                    default_shifts=[
                        TimeRange(start_time=time(8, 0), end_time=time(17, 0)),
                    ],
                ),
            ],
            salary_tiers=[
                SalaryTier(
                    id="st1",
                    start=date(2023, 1, 1),
                    end=date(2023, 1, 30),
                    amount=Decimal("50"),
                    type=SalaryType.HOURLY,
                    net_or_gross=NetOrGross.GROSS,
                ),
            ],
            rest_day=RestDay.SATURDAY,
            district=District.TEL_AVIV,
            filing_date=date(2024, 1, 15),
        )

        result = run_full_pipeline(ssot_input)

        assert result.success is True
        ssot = result.ssot

        # Holiday threshold should not be met
        if ssot.rights_results.holidays:
            year_result = ssot.rights_results.holidays.per_year[0]
            assert year_result.met_threshold is False

    def test_pipeline_net_salary_converted_to_gross(self):
        """Test pipeline converts net salary to gross."""
        ssot_input = SSOTInput(
            employment_periods=[
                EmploymentPeriod(
                    id="ep1",
                    start=date(2023, 1, 1),
                    end=date(2023, 1, 31),
                ),
            ],
            work_patterns=[
                WorkPattern(
                    id="wp1",
                    start=date(2023, 1, 1),
                    end=date(2023, 1, 31),
                    work_days=[0, 1, 2, 3, 4],
                    default_shifts=[
                        TimeRange(start_time=time(8, 0), end_time=time(17, 0)),
                    ],
                ),
            ],
            salary_tiers=[
                SalaryTier(
                    id="st1",
                    start=date(2023, 1, 1),
                    end=date(2023, 1, 31),
                    amount=Decimal("40"),  # Net
                    type=SalaryType.HOURLY,
                    net_or_gross=NetOrGross.NET,  # Net salary
                ),
            ],
            rest_day=RestDay.SATURDAY,
            district=District.TEL_AVIV,
            filing_date=date(2024, 1, 15),
        )

        result = run_full_pipeline(ssot_input)

        assert result.success is True
        ssot = result.ssot

        # Gross should be 40 * 1.12 = 44.8
        for pmr in ssot.period_month_records:
            assert pmr.salary_gross_amount == Decimal("40") * Decimal("1.12")
