"""Tests for claim summary module."""

import pytest
from datetime import date
from decimal import Decimal

from app.modules.summary import (
    compute_summary,
    get_displayable_rights,
    get_hidden_rights,
    RIGHT_NAMES,
)
from app.ssot import (
    LimitationResults,
    RightLimitationResult,
    DeductionResult,
    TotalEmployment,
    PersonalDetails,
    DefendantDetails,
    Duration,
)


class TestComputeSummary:
    """Test compute_summary function."""

    def test_single_right_no_limitation_no_deduction(self):
        """Single right with no limitation and no deduction."""
        limitation_results = LimitationResults(
            per_right={
                "overtime": RightLimitationResult(
                    limitation_type_id="general",
                    full_amount=Decimal("10000"),
                    claimable_amount=Decimal("10000"),
                    excluded_amount=Decimal("0"),
                )
            }
        )
        deduction_results = {}
        total_employment = TotalEmployment(
            total_duration=Duration(display="3 שנים"),
            worked_duration=Duration(display="3 שנים"),
        )
        personal_details = PersonalDetails(first_name="ישראל", last_name="ישראלי")
        defendant_details = DefendantDetails(name="חברה בע\"מ")
        filing_date = date(2024, 6, 15)

        summary = compute_summary(
            limitation_results,
            deduction_results,
            total_employment,
            personal_details,
            defendant_details,
            filing_date,
        )

        assert summary.total_before_limitation == Decimal("10000")
        assert summary.total_after_limitation == Decimal("10000")
        assert summary.total_after_deductions == Decimal("10000")
        assert len(summary.per_right) == 1
        assert summary.per_right[0].right_id == "overtime"
        assert summary.per_right[0].show is True

    def test_single_right_with_limitation(self):
        """Single right with limitation excluding some amount."""
        limitation_results = LimitationResults(
            per_right={
                "overtime": RightLimitationResult(
                    limitation_type_id="general",
                    full_amount=Decimal("50000"),
                    claimable_amount=Decimal("35000"),
                    excluded_amount=Decimal("15000"),
                )
            }
        )
        deduction_results = {}
        total_employment = TotalEmployment()
        personal_details = PersonalDetails()
        defendant_details = DefendantDetails()
        filing_date = date(2024, 6, 15)

        summary = compute_summary(
            limitation_results,
            deduction_results,
            total_employment,
            personal_details,
            defendant_details,
            filing_date,
        )

        assert summary.total_before_limitation == Decimal("50000")
        assert summary.total_after_limitation == Decimal("35000")
        assert summary.total_after_deductions == Decimal("35000")
        assert summary.per_right[0].limitation_excluded == Decimal("15000")

    def test_single_right_with_deduction(self):
        """Single right with deduction applied."""
        limitation_results = LimitationResults(
            per_right={
                "severance": RightLimitationResult(
                    limitation_type_id="general",
                    full_amount=Decimal("45000"),
                    claimable_amount=Decimal("45000"),
                    excluded_amount=Decimal("0"),
                )
            }
        )
        deduction_results = {
            "severance": DeductionResult(
                right_id="severance",
                calculated_amount=Decimal("45000"),
                deduction_amount=Decimal("22000"),
                net_amount=Decimal("23000"),
                show_deduction=True,
                show_right=True,
                warning=False,
            )
        }
        total_employment = TotalEmployment()
        personal_details = PersonalDetails()
        defendant_details = DefendantDetails()
        filing_date = date(2024, 6, 15)

        summary = compute_summary(
            limitation_results,
            deduction_results,
            total_employment,
            personal_details,
            defendant_details,
            filing_date,
        )

        assert summary.total_before_limitation == Decimal("45000")
        assert summary.total_after_limitation == Decimal("45000")
        assert summary.total_after_deductions == Decimal("23000")
        assert summary.per_right[0].deduction_amount == Decimal("22000")

    def test_single_right_with_limitation_and_deduction(self):
        """Single right with both limitation and deduction."""
        limitation_results = LimitationResults(
            per_right={
                "pension": RightLimitationResult(
                    limitation_type_id="general",
                    full_amount=Decimal("100000"),
                    claimable_amount=Decimal("80000"),
                    excluded_amount=Decimal("20000"),
                )
            }
        )
        deduction_results = {
            "pension": DeductionResult(
                right_id="pension",
                calculated_amount=Decimal("80000"),  # After limitation
                deduction_amount=Decimal("30000"),
                net_amount=Decimal("50000"),
                show_deduction=True,
                show_right=True,
                warning=False,
            )
        }
        total_employment = TotalEmployment()
        personal_details = PersonalDetails()
        defendant_details = DefendantDetails()
        filing_date = date(2024, 6, 15)

        summary = compute_summary(
            limitation_results,
            deduction_results,
            total_employment,
            personal_details,
            defendant_details,
            filing_date,
        )

        assert summary.total_before_limitation == Decimal("100000")
        assert summary.total_after_limitation == Decimal("80000")
        assert summary.total_after_deductions == Decimal("50000")

    def test_multiple_rights_mixed_scenarios(self):
        """Multiple rights with different limitation/deduction scenarios."""
        limitation_results = LimitationResults(
            per_right={
                "overtime": RightLimitationResult(
                    limitation_type_id="general",
                    full_amount=Decimal("30000"),
                    claimable_amount=Decimal("25000"),
                    excluded_amount=Decimal("5000"),
                ),
                "holidays": RightLimitationResult(
                    limitation_type_id="general",
                    full_amount=Decimal("5000"),
                    claimable_amount=Decimal("5000"),
                    excluded_amount=Decimal("0"),
                ),
                "vacation": RightLimitationResult(
                    limitation_type_id="vacation",
                    full_amount=Decimal("8000"),
                    claimable_amount=Decimal("6000"),
                    excluded_amount=Decimal("2000"),
                ),
            }
        )
        deduction_results = {
            "overtime": DeductionResult(
                right_id="overtime",
                calculated_amount=Decimal("25000"),
                deduction_amount=Decimal("0"),
                net_amount=Decimal("25000"),
                show_deduction=False,
                show_right=True,
                warning=False,
            ),
            "holidays": DeductionResult(
                right_id="holidays",
                calculated_amount=Decimal("5000"),
                deduction_amount=Decimal("5000"),  # Equals amount
                net_amount=Decimal("0"),
                show_deduction=True,
                show_right=False,  # Suppressed
                warning=True,
            ),
        }
        total_employment = TotalEmployment()
        personal_details = PersonalDetails()
        defendant_details = DefendantDetails()
        filing_date = date(2024, 6, 15)

        summary = compute_summary(
            limitation_results,
            deduction_results,
            total_employment,
            personal_details,
            defendant_details,
            filing_date,
        )

        # Before limitation: 30000 + 5000 + 8000 = 43000
        assert summary.total_before_limitation == Decimal("43000")
        # After limitation: 25000 + 5000 + 6000 = 36000
        assert summary.total_after_limitation == Decimal("36000")
        # After deductions: 25000 + 0 + 6000 = 31000
        assert summary.total_after_deductions == Decimal("31000")
        assert len(summary.per_right) == 3

    def test_deduction_without_limitation(self):
        """Right that has deduction but no limitation entry."""
        limitation_results = LimitationResults(per_right={})
        deduction_results = {
            "recreation": DeductionResult(
                right_id="recreation",
                calculated_amount=Decimal("3000"),
                deduction_amount=Decimal("1000"),
                net_amount=Decimal("2000"),
                show_deduction=True,
                show_right=True,
                warning=False,
            )
        }
        total_employment = TotalEmployment()
        personal_details = PersonalDetails()
        defendant_details = DefendantDetails()
        filing_date = date(2024, 6, 15)

        summary = compute_summary(
            limitation_results,
            deduction_results,
            total_employment,
            personal_details,
            defendant_details,
            filing_date,
        )

        # Recreation has no limitation, so full_amount = after_limitation
        assert summary.total_before_limitation == Decimal("3000")
        assert summary.total_after_limitation == Decimal("3000")
        assert summary.total_after_deductions == Decimal("2000")
        assert len(summary.per_right) == 1
        assert summary.per_right[0].limitation_type == ""
        assert summary.per_right[0].limitation_excluded == Decimal("0")


class TestEmploymentSummary:
    """Test employment summary in claim summary."""

    def test_full_names(self):
        """Worker with both first and last name."""
        limitation_results = LimitationResults()
        deduction_results = {}
        total_employment = TotalEmployment(
            total_duration=Duration(display="5 שנים ו-3 חודשים"),
            worked_duration=Duration(display="5 שנים"),
        )
        personal_details = PersonalDetails(first_name="משה", last_name="כהן")
        defendant_details = DefendantDetails(name="מפעל תעשיות בע\"מ")
        filing_date = date(2024, 12, 25)

        summary = compute_summary(
            limitation_results,
            deduction_results,
            total_employment,
            personal_details,
            defendant_details,
            filing_date,
        )

        assert summary.employment_summary.worker_name == "משה כהן"
        assert summary.employment_summary.defendant_name == "מפעל תעשיות בע\"מ"
        assert summary.employment_summary.total_duration_display == "5 שנים ו-3 חודשים"
        assert summary.employment_summary.worked_duration_display == "5 שנים"
        assert summary.employment_summary.filing_date == date(2024, 12, 25)
        assert summary.employment_summary.filing_date_display == "25.12.2024"

    def test_first_name_only(self):
        """Worker with only first name."""
        limitation_results = LimitationResults()
        deduction_results = {}
        total_employment = TotalEmployment()
        personal_details = PersonalDetails(first_name="דוד")
        defendant_details = DefendantDetails()
        filing_date = None

        summary = compute_summary(
            limitation_results,
            deduction_results,
            total_employment,
            personal_details,
            defendant_details,
            filing_date,
        )

        assert summary.employment_summary.worker_name == "דוד"

    def test_last_name_only(self):
        """Worker with only last name."""
        limitation_results = LimitationResults()
        deduction_results = {}
        total_employment = TotalEmployment()
        personal_details = PersonalDetails(last_name="לוי")
        defendant_details = DefendantDetails()
        filing_date = None

        summary = compute_summary(
            limitation_results,
            deduction_results,
            total_employment,
            personal_details,
            defendant_details,
            filing_date,
        )

        assert summary.employment_summary.worker_name == "לוי"

    def test_no_names(self):
        """Worker with no names provided."""
        limitation_results = LimitationResults()
        deduction_results = {}
        total_employment = TotalEmployment()
        personal_details = PersonalDetails()
        defendant_details = DefendantDetails()
        filing_date = None

        summary = compute_summary(
            limitation_results,
            deduction_results,
            total_employment,
            personal_details,
            defendant_details,
            filing_date,
        )

        assert summary.employment_summary.worker_name is None

    def test_no_filing_date(self):
        """Claim with no filing date."""
        limitation_results = LimitationResults()
        deduction_results = {}
        total_employment = TotalEmployment()
        personal_details = PersonalDetails()
        defendant_details = DefendantDetails()
        filing_date = None

        summary = compute_summary(
            limitation_results,
            deduction_results,
            total_employment,
            personal_details,
            defendant_details,
            filing_date,
        )

        assert summary.employment_summary.filing_date is None
        assert summary.employment_summary.filing_date_display == ""


class TestRightNames:
    """Test right names mapping."""

    def test_known_right_names(self):
        """Known rights get Hebrew display names."""
        limitation_results = LimitationResults(
            per_right={
                "overtime": RightLimitationResult(
                    full_amount=Decimal("1000"),
                    claimable_amount=Decimal("1000"),
                ),
                "holidays": RightLimitationResult(
                    full_amount=Decimal("500"),
                    claimable_amount=Decimal("500"),
                ),
            }
        )
        deduction_results = {}
        total_employment = TotalEmployment()
        personal_details = PersonalDetails()
        defendant_details = DefendantDetails()
        filing_date = None

        summary = compute_summary(
            limitation_results,
            deduction_results,
            total_employment,
            personal_details,
            defendant_details,
            filing_date,
        )

        rights_by_id = {r.right_id: r for r in summary.per_right}
        assert rights_by_id["overtime"].name == "שעות נוספות"
        assert rights_by_id["holidays"].name == "דמי חגים"

    def test_unknown_right_name(self):
        """Unknown rights use right_id as name."""
        limitation_results = LimitationResults(
            per_right={
                "custom_right": RightLimitationResult(
                    full_amount=Decimal("1000"),
                    claimable_amount=Decimal("1000"),
                ),
            }
        )
        deduction_results = {}
        total_employment = TotalEmployment()
        personal_details = PersonalDetails()
        defendant_details = DefendantDetails()
        filing_date = None

        summary = compute_summary(
            limitation_results,
            deduction_results,
            total_employment,
            personal_details,
            defendant_details,
            filing_date,
        )

        assert summary.per_right[0].name == "custom_right"


class TestDisplayableRights:
    """Test get_displayable_rights and get_hidden_rights."""

    def test_displayable_and_hidden(self):
        """Test separation of displayable and hidden rights."""
        limitation_results = LimitationResults(
            per_right={
                "overtime": RightLimitationResult(
                    full_amount=Decimal("10000"),
                    claimable_amount=Decimal("10000"),
                ),
                "holidays": RightLimitationResult(
                    full_amount=Decimal("5000"),
                    claimable_amount=Decimal("5000"),
                ),
                "recreation": RightLimitationResult(
                    full_amount=Decimal("3000"),
                    claimable_amount=Decimal("3000"),
                ),
            }
        )
        deduction_results = {
            "overtime": DeductionResult(
                right_id="overtime",
                calculated_amount=Decimal("10000"),
                deduction_amount=Decimal("0"),
                net_amount=Decimal("10000"),
                show_right=True,
            ),
            "holidays": DeductionResult(
                right_id="holidays",
                calculated_amount=Decimal("5000"),
                deduction_amount=Decimal("5000"),
                net_amount=Decimal("0"),
                show_right=False,  # Suppressed
            ),
            "recreation": DeductionResult(
                right_id="recreation",
                calculated_amount=Decimal("3000"),
                deduction_amount=Decimal("4000"),
                net_amount=Decimal("0"),
                show_right=False,  # Suppressed
            ),
        }
        total_employment = TotalEmployment()
        personal_details = PersonalDetails()
        defendant_details = DefendantDetails()
        filing_date = None

        summary = compute_summary(
            limitation_results,
            deduction_results,
            total_employment,
            personal_details,
            defendant_details,
            filing_date,
        )

        displayable = get_displayable_rights(summary)
        hidden = get_hidden_rights(summary)

        assert len(displayable) == 1
        assert displayable[0].right_id == "overtime"

        assert len(hidden) == 2
        hidden_ids = {r.right_id for r in hidden}
        assert hidden_ids == {"holidays", "recreation"}


class TestEdgeCases:
    """Test edge cases."""

    def test_empty_inputs(self):
        """Empty limitation and deduction results."""
        limitation_results = LimitationResults()
        deduction_results = {}
        total_employment = TotalEmployment()
        personal_details = PersonalDetails()
        defendant_details = DefendantDetails()
        filing_date = None

        summary = compute_summary(
            limitation_results,
            deduction_results,
            total_employment,
            personal_details,
            defendant_details,
            filing_date,
        )

        assert summary.total_before_limitation == Decimal("0")
        assert summary.total_after_limitation == Decimal("0")
        assert summary.total_after_deductions == Decimal("0")
        assert len(summary.per_right) == 0

    def test_zero_amounts(self):
        """Rights with zero amounts."""
        limitation_results = LimitationResults(
            per_right={
                "overtime": RightLimitationResult(
                    full_amount=Decimal("0"),
                    claimable_amount=Decimal("0"),
                    excluded_amount=Decimal("0"),
                ),
            }
        )
        deduction_results = {}
        total_employment = TotalEmployment()
        personal_details = PersonalDetails()
        defendant_details = DefendantDetails()
        filing_date = None

        summary = compute_summary(
            limitation_results,
            deduction_results,
            total_employment,
            personal_details,
            defendant_details,
            filing_date,
        )

        assert summary.total_before_limitation == Decimal("0")
        assert summary.total_after_limitation == Decimal("0")
        assert len(summary.per_right) == 1
        # Zero amount right should not be shown
        assert summary.per_right[0].show is False

    def test_large_amounts(self):
        """Large monetary amounts are handled correctly."""
        limitation_results = LimitationResults(
            per_right={
                "severance": RightLimitationResult(
                    full_amount=Decimal("1500000"),
                    claimable_amount=Decimal("1200000"),
                    excluded_amount=Decimal("300000"),
                ),
            }
        )
        deduction_results = {
            "severance": DeductionResult(
                right_id="severance",
                calculated_amount=Decimal("1200000"),
                deduction_amount=Decimal("500000"),
                net_amount=Decimal("700000"),
                show_right=True,
            )
        }
        total_employment = TotalEmployment()
        personal_details = PersonalDetails()
        defendant_details = DefendantDetails()
        filing_date = None

        summary = compute_summary(
            limitation_results,
            deduction_results,
            total_employment,
            personal_details,
            defendant_details,
            filing_date,
        )

        assert summary.total_before_limitation == Decimal("1500000")
        assert summary.total_after_limitation == Decimal("1200000")
        assert summary.total_after_deductions == Decimal("700000")

    def test_decimal_precision(self):
        """Decimal precision is maintained."""
        limitation_results = LimitationResults(
            per_right={
                "overtime": RightLimitationResult(
                    full_amount=Decimal("12345.67"),
                    claimable_amount=Decimal("10234.56"),
                    excluded_amount=Decimal("2111.11"),
                ),
            }
        )
        deduction_results = {
            "overtime": DeductionResult(
                right_id="overtime",
                calculated_amount=Decimal("10234.56"),
                deduction_amount=Decimal("1234.56"),
                net_amount=Decimal("9000.00"),
                show_right=True,
            )
        }
        total_employment = TotalEmployment()
        personal_details = PersonalDetails()
        defendant_details = DefendantDetails()
        filing_date = None

        summary = compute_summary(
            limitation_results,
            deduction_results,
            total_employment,
            personal_details,
            defendant_details,
            filing_date,
        )

        assert summary.total_before_limitation == Decimal("12345.67")
        assert summary.total_after_limitation == Decimal("10234.56")
        assert summary.total_after_deductions == Decimal("9000.00")
