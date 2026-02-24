"""Tests for employer deductions module.

Test fixtures from docs/skills/employer-deductions/EMPLOYER_DEDUCTIONS_TEST_FIXTURES.md
"""

import pytest
import logging
from decimal import Decimal

from app.modules.deductions import (
    apply_deduction,
    apply_all_deductions,
    calculate_claim_totals,
    get_displayable_rights,
    get_suppressed_rights,
)


class TestFixture1NoDeduction:
    """Test 1: No deduction."""

    def test_no_deduction(self):
        """Zero deduction = right displayed normally."""
        result = apply_deduction(
            right_id="pension",
            calculated_amount=Decimal("30000"),
            deduction_amount=Decimal("0"),
        )

        assert result.net_amount == Decimal("30000")
        assert result.show_deduction is False
        assert result.show_right is True
        assert result.warning is False


class TestFixture2PartialDeduction:
    """Test 2: Partial deduction."""

    def test_partial_deduction(self):
        """Partial deduction = show calculated, deduction row, and net."""
        result = apply_deduction(
            right_id="severance",
            calculated_amount=Decimal("45000"),
            deduction_amount=Decimal("22000"),
        )

        assert result.calculated_amount == Decimal("45000")
        assert result.deduction_amount == Decimal("22000")
        assert result.net_amount == Decimal("23000")
        assert result.show_deduction is True
        assert result.show_right is True
        assert result.warning is False


class TestFixture3DeductionEqualsAmount:
    """Test 3: Deduction equals calculated amount."""

    def test_deduction_equals_amount(self, caplog):
        """Deduction = calculated → suppress right, show warning."""
        with caplog.at_level(logging.WARNING):
            result = apply_deduction(
                right_id="pension",
                calculated_amount=Decimal("15000"),
                deduction_amount=Decimal("15000"),
            )

        assert result.net_amount == Decimal("0")
        assert result.show_right is False
        assert result.warning is True
        assert "exceeds calculated amount" in caplog.text


class TestFixture4DeductionExceedsAmount:
    """Test 4: Deduction exceeds calculated amount."""

    def test_deduction_exceeds_amount(self, caplog):
        """Deduction > calculated → suppress right, show warning."""
        with caplog.at_level(logging.WARNING):
            result = apply_deduction(
                right_id="severance",
                calculated_amount=Decimal("20000"),
                deduction_amount=Decimal("25000"),
            )

        assert result.net_amount == Decimal("0")
        assert result.show_right is False
        assert result.warning is True
        # Check warning message contains the amounts
        assert "25000" in caplog.text
        assert "20000" in caplog.text


class TestFixture5MultipleRightsMixedDeductions:
    """Test 5: Multiple rights, mixed deductions."""

    def test_multiple_rights(self, caplog):
        """Multiple rights with different deduction scenarios."""
        rights_amounts = {
            "pension": Decimal("30000"),
            "severance": Decimal("45000"),
            "recreation": Decimal("5000"),
        }

        deductions = {
            "pension": Decimal("10000"),
            "severance": Decimal("0"),
            "recreation": Decimal("5000"),
        }

        with caplog.at_level(logging.WARNING):
            results = apply_all_deductions(rights_amounts, deductions)

        # Pension: partial deduction
        assert results["pension"].net_amount == Decimal("20000")
        assert results["pension"].show_deduction is True
        assert results["pension"].show_right is True

        # Severance: no deduction
        assert results["severance"].net_amount == Decimal("45000")
        assert results["severance"].show_deduction is False
        assert results["severance"].show_right is True

        # Recreation: suppressed (deduction = amount)
        assert results["recreation"].net_amount == Decimal("0")
        assert results["recreation"].show_right is False
        assert results["recreation"].warning is True

        # Warning in console for recreation
        assert "recreation" in caplog.text


class TestApplyAllDeductions:
    """Test apply_all_deductions helper."""

    def test_missing_deduction_defaults_to_zero(self):
        """Rights without explicit deduction default to 0."""
        rights_amounts = {
            "pension": Decimal("30000"),
            "severance": Decimal("45000"),
        }

        # Only pension has a deduction
        deductions = {
            "pension": Decimal("5000"),
        }

        results = apply_all_deductions(rights_amounts, deductions)

        # Pension has deduction
        assert results["pension"].deduction_amount == Decimal("5000")
        assert results["pension"].net_amount == Decimal("25000")

        # Severance defaults to 0 deduction
        assert results["severance"].deduction_amount == Decimal("0")
        assert results["severance"].net_amount == Decimal("45000")


class TestCalculateClaimTotals:
    """Test calculate_claim_totals helper."""

    def test_totals_only_include_displayed_rights(self):
        """Totals only count rights where show_right is True."""
        rights_amounts = {
            "pension": Decimal("30000"),
            "severance": Decimal("45000"),
            "recreation": Decimal("5000"),  # Will be suppressed
        }

        deductions = {
            "pension": Decimal("10000"),
            "severance": Decimal("0"),
            "recreation": Decimal("5000"),  # Equals amount
        }

        results = apply_all_deductions(rights_amounts, deductions)
        total_calc, total_ded, total_net = calculate_claim_totals(results)

        # Recreation is suppressed, so only pension + severance count
        assert total_calc == Decimal("75000")  # 30000 + 45000
        assert total_ded == Decimal("10000")   # Only pension deduction
        assert total_net == Decimal("65000")   # 20000 + 45000


class TestGetDisplayableRights:
    """Test get_displayable_rights helper."""

    def test_displayable_rights(self):
        """Only rights with show_right=True are returned."""
        rights_amounts = {
            "pension": Decimal("30000"),
            "severance": Decimal("20000"),
        }

        deductions = {
            "pension": Decimal("0"),
            "severance": Decimal("25000"),  # Exceeds
        }

        results = apply_all_deductions(rights_amounts, deductions)
        displayable = get_displayable_rights(results)

        assert len(displayable) == 1
        assert displayable[0].right_id == "pension"


class TestGetSuppressedRights:
    """Test get_suppressed_rights helper."""

    def test_suppressed_rights(self):
        """Only rights that were suppressed with warning are returned."""
        rights_amounts = {
            "pension": Decimal("30000"),
            "severance": Decimal("20000"),
        }

        deductions = {
            "pension": Decimal("0"),
            "severance": Decimal("25000"),  # Exceeds
        }

        results = apply_all_deductions(rights_amounts, deductions)
        suppressed = get_suppressed_rights(results)

        assert len(suppressed) == 1
        assert suppressed[0].right_id == "severance"
        assert suppressed[0].warning is True


class TestAntiPatterns:
    """Test anti-patterns from skill doc."""

    def test_deduction_is_flat_amount(self):
        """Deductions are flat ₪ amounts, not percentages."""
        # If it were percentage, 50% of 30000 = 15000
        # But it's flat, so deduction of 50 means ₪50
        result = apply_deduction(
            right_id="pension",
            calculated_amount=Decimal("30000"),
            deduction_amount=Decimal("50"),  # ₪50, not 50%
        )

        assert result.net_amount == Decimal("29950")  # Not 15000

    def test_zero_deduction_no_row(self):
        """Zero deduction means no deduction row displayed."""
        result = apply_deduction(
            right_id="severance",
            calculated_amount=Decimal("45000"),
            deduction_amount=Decimal("0"),
        )

        assert result.show_deduction is False

    def test_no_negative_amounts(self):
        """Net amount is never negative."""
        result = apply_deduction(
            right_id="pension",
            calculated_amount=Decimal("10000"),
            deduction_amount=Decimal("50000"),
        )

        assert result.net_amount == Decimal("0")
        assert result.net_amount >= Decimal("0")


class TestEdgeCases:
    """Additional edge cases."""

    def test_very_small_deduction(self):
        """Very small deduction is applied correctly."""
        result = apply_deduction(
            right_id="pension",
            calculated_amount=Decimal("30000"),
            deduction_amount=Decimal("0.01"),
        )

        assert result.net_amount == Decimal("29999.99")
        assert result.show_deduction is True

    def test_deduction_one_agora_less_than_amount(self):
        """Deduction just under calculated amount still shows right."""
        result = apply_deduction(
            right_id="pension",
            calculated_amount=Decimal("30000"),
            deduction_amount=Decimal("29999.99"),
        )

        assert result.net_amount == Decimal("0.01")
        assert result.show_right is True

    def test_deduction_one_agora_over_amount(self):
        """Deduction just over calculated amount suppresses right."""
        result = apply_deduction(
            right_id="pension",
            calculated_amount=Decimal("30000"),
            deduction_amount=Decimal("30000.01"),
        )

        assert result.net_amount == Decimal("0")
        assert result.show_right is False
        assert result.warning is True

    def test_zero_calculated_amount_no_deduction(self):
        """Zero calculated amount with zero deduction."""
        result = apply_deduction(
            right_id="pension",
            calculated_amount=Decimal("0"),
            deduction_amount=Decimal("0"),
        )

        assert result.net_amount == Decimal("0")
        assert result.show_right is True
        assert result.show_deduction is False

    def test_zero_calculated_amount_with_deduction(self):
        """Zero calculated amount with non-zero deduction."""
        result = apply_deduction(
            right_id="pension",
            calculated_amount=Decimal("0"),
            deduction_amount=Decimal("1000"),
        )

        assert result.net_amount == Decimal("0")
        assert result.show_right is False
        assert result.warning is True
