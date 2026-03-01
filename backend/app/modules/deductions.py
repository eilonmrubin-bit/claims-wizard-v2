"""Employer deductions (ניכויי הפרשות מעסיק) module.

Applies employer-paid deductions to calculated right amounts.
This is a POST-CALCULATION step — rights are calculated fully first,
then deductions are applied.

See docs/skills/employer-deductions/SKILL.md for complete documentation.
"""

from dataclasses import dataclass
from decimal import Decimal
import logging

from app.ssot import DeductionResult


logger = logging.getLogger(__name__)


@dataclass
class DeductionInput:
    """Input for deduction calculation."""
    right_id: str
    calculated_amount: Decimal
    deduction_amount: Decimal


def apply_deduction(
    right_id: str,
    calculated_amount: Decimal,
    deduction_amount: Decimal,
    deduction_override: Decimal | None = None,
) -> DeductionResult:
    """Apply employer deduction to a calculated right amount.

    Args:
        right_id: The ID of the right (e.g., "pension", "severance")
        calculated_amount: The full calculated amount before deduction
        deduction_amount: The employer-paid amount to deduct (from deductions_input)
        deduction_override: If not None, use this value instead of deduction_amount.
                           This allows rights (like severance PATH A) to override
                           the standard deduction behavior.

    Returns:
        DeductionResult with net amount and display flags
    """
    # Apply override if provided
    effective_deduction = deduction_override if deduction_override is not None else deduction_amount

    # No deduction case
    if effective_deduction == Decimal("0"):
        return DeductionResult(
            right_id=right_id,
            calculated_amount=calculated_amount,
            deduction_amount=Decimal("0"),
            net_amount=calculated_amount,
            show_deduction=False,
            show_right=True,
            warning=False,
        )

    # Calculate net amount
    net_amount = calculated_amount - effective_deduction

    # Deduction exceeds or equals calculated amount
    if net_amount <= Decimal("0"):
        logger.warning(
            f"Deduction for {right_id} (₪{effective_deduction}) "
            f"exceeds calculated amount (₪{calculated_amount})"
        )
        return DeductionResult(
            right_id=right_id,
            calculated_amount=calculated_amount,
            deduction_amount=effective_deduction,
            net_amount=Decimal("0"),
            show_deduction=True,
            show_right=False,
            warning=True,
        )

    # Partial deduction - normal case
    return DeductionResult(
        right_id=right_id,
        calculated_amount=calculated_amount,
        deduction_amount=effective_deduction,
        net_amount=net_amount,
        show_deduction=True,
        show_right=True,
        warning=False,
    )


def apply_all_deductions(
    rights_amounts: dict[str, Decimal],
    deductions: dict[str, Decimal],
    deduction_overrides: dict[str, Decimal | None] | None = None,
) -> dict[str, DeductionResult]:
    """Apply deductions to multiple rights.

    Args:
        rights_amounts: Map of right_id -> calculated amount
        deductions: Map of right_id -> deduction amount
        deduction_overrides: Optional map of right_id -> override value.
                            If a right has an override, that value is used
                            instead of the value from deductions.

    Returns:
        Map of right_id -> DeductionResult
    """
    results = {}
    overrides = deduction_overrides or {}

    for right_id, calculated_amount in rights_amounts.items():
        deduction_amount = deductions.get(right_id, Decimal("0"))
        override = overrides.get(right_id)

        results[right_id] = apply_deduction(
            right_id=right_id,
            calculated_amount=calculated_amount,
            deduction_amount=deduction_amount,
            deduction_override=override,
        )

    return results


def calculate_claim_totals(
    deduction_results: dict[str, DeductionResult],
) -> tuple[Decimal, Decimal, Decimal]:
    """Calculate totals from deduction results.

    Args:
        deduction_results: Map of right_id -> DeductionResult

    Returns:
        Tuple of (total_calculated, total_deductions, total_net)
    """
    total_calculated = Decimal("0")
    total_deductions = Decimal("0")
    total_net = Decimal("0")

    for result in deduction_results.values():
        if result.show_right:
            total_calculated += result.calculated_amount
            total_deductions += result.deduction_amount
            total_net += result.net_amount

    return total_calculated, total_deductions, total_net


def get_displayable_rights(
    deduction_results: dict[str, DeductionResult],
) -> list[DeductionResult]:
    """Get list of rights that should be displayed in the claim.

    Args:
        deduction_results: Map of right_id -> DeductionResult

    Returns:
        List of DeductionResult where show_right is True
    """
    return [r for r in deduction_results.values() if r.show_right]


def get_suppressed_rights(
    deduction_results: dict[str, DeductionResult],
) -> list[DeductionResult]:
    """Get list of rights that were suppressed due to deductions.

    Args:
        deduction_results: Map of right_id -> DeductionResult

    Returns:
        List of DeductionResult where show_right is False and warning is True
    """
    return [r for r in deduction_results.values() if not r.show_right and r.warning]
