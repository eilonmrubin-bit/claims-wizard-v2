"""Claim summary module (סיכום תביעה).

Aggregates all rights after limitation and deductions into final claim summary.
This is a POST-PROCESSING step — all calculations are already done.

Logic: "אגרגציה בלבד. אפס חישובים חדשים."
(Aggregation only. Zero new calculations.)
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.ssot import (
    ClaimSummary,
    ClaimSummaryRight,
    EmploymentSummary,
    DeductionResult,
    LimitationResults,
    TotalEmployment,
    PersonalDetails,
    DefendantDetails,
)


# Right names mapping (right_id -> Hebrew display name)
RIGHT_NAMES = {
    "overtime": "שעות נוספות",
    "holidays": "דמי חגים",
    "vacation": "חופשה",
    "severance": "פיצויי פיטורין",
    "pension": "פנסיה",
    "recreation": "דמי הבראה",
    "salary_completion": "השלמת שכר",
    "travel": "דמי נסיעות",
}


@dataclass
class SummaryInput:
    """Input for summary computation."""
    limitation_results: LimitationResults
    deduction_results: dict[str, DeductionResult]
    total_employment: TotalEmployment
    personal_details: PersonalDetails
    defendant_details: DefendantDetails
    filing_date: date | None


def format_date(d: date | None) -> str:
    """Format date as DD.MM.YYYY."""
    if d is None:
        return ""
    return d.strftime("%d.%m.%Y")


def compute_summary(
    limitation_results: LimitationResults,
    deduction_results: dict[str, DeductionResult],
    total_employment: TotalEmployment,
    personal_details: PersonalDetails,
    defendant_details: DefendantDetails,
    filing_date: date | None,
) -> ClaimSummary:
    """Compute claim summary from limitation and deduction results.

    Args:
        limitation_results: Results from limitation module per right
        deduction_results: Results from deductions module per right
        total_employment: Employment summary from weaver
        personal_details: Worker's personal details
        defendant_details: Defendant's details
        filing_date: Filing date of the claim

    Returns:
        ClaimSummary with totals and per-right breakdown
    """
    per_right: list[ClaimSummaryRight] = []
    total_before_limitation = Decimal("0")
    total_after_limitation = Decimal("0")
    total_after_deductions = Decimal("0")

    # Process each right that has limitation results
    for right_id, limitation_result in limitation_results.per_right.items():
        # Get deduction result if exists
        deduction = deduction_results.get(right_id)

        # Full amount = before limitation
        full_amount = limitation_result.full_amount
        total_before_limitation += full_amount

        # After limitation
        after_limitation = limitation_result.claimable_amount
        total_after_limitation += after_limitation

        # After deductions
        if deduction is not None:
            after_deductions = deduction.net_amount
            deduction_amount = deduction.deduction_amount
            show = deduction.show_right
        else:
            # No deduction for this right
            after_deductions = after_limitation
            deduction_amount = Decimal("0")
            show = after_limitation > Decimal("0")

        total_after_deductions += after_deductions

        # Build per-right summary
        right_summary = ClaimSummaryRight(
            right_id=right_id,
            name=RIGHT_NAMES.get(right_id, right_id),
            full_amount=full_amount,
            after_limitation=after_limitation,
            after_deductions=after_deductions,
            deduction_amount=deduction_amount,
            show=show,
            limitation_type=limitation_result.limitation_type_id,
            limitation_excluded=limitation_result.excluded_amount,
        )
        per_right.append(right_summary)

    # Also process deductions that don't have limitation results
    # (rights that were calculated but not subject to limitation filtering)
    for right_id, deduction in deduction_results.items():
        if right_id not in limitation_results.per_right:
            full_amount = deduction.calculated_amount
            total_before_limitation += full_amount
            total_after_limitation += full_amount  # No limitation
            total_after_deductions += deduction.net_amount

            right_summary = ClaimSummaryRight(
                right_id=right_id,
                name=RIGHT_NAMES.get(right_id, right_id),
                full_amount=full_amount,
                after_limitation=full_amount,
                after_deductions=deduction.net_amount,
                deduction_amount=deduction.deduction_amount,
                show=deduction.show_right,
                limitation_type="",  # No limitation applied
                limitation_excluded=Decimal("0"),
            )
            per_right.append(right_summary)

    # Build employment summary
    worker_name = None
    if personal_details.first_name and personal_details.last_name:
        worker_name = f"{personal_details.first_name} {personal_details.last_name}"
    elif personal_details.first_name:
        worker_name = personal_details.first_name
    elif personal_details.last_name:
        worker_name = personal_details.last_name

    employment_summary = EmploymentSummary(
        worker_name=worker_name,
        defendant_name=defendant_details.name,
        total_duration_display=total_employment.total_duration.display,
        worked_duration_display=total_employment.worked_duration.display,
        filing_date=filing_date,
        filing_date_display=format_date(filing_date),
    )

    return ClaimSummary(
        total_before_limitation=total_before_limitation,
        total_after_limitation=total_after_limitation,
        total_after_deductions=total_after_deductions,
        per_right=per_right,
        employment_summary=employment_summary,
    )


def get_displayable_rights(summary: ClaimSummary) -> list[ClaimSummaryRight]:
    """Get list of rights that should be displayed in the claim.

    Args:
        summary: The claim summary

    Returns:
        List of ClaimSummaryRight where show is True
    """
    return [r for r in summary.per_right if r.show]


def get_hidden_rights(summary: ClaimSummary) -> list[ClaimSummaryRight]:
    """Get list of rights that are hidden (suppressed).

    Args:
        summary: The claim summary

    Returns:
        List of ClaimSummaryRight where show is False
    """
    return [r for r in summary.per_right if not r.show]
