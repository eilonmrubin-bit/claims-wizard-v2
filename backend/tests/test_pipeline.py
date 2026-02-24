"""Tests for pipeline orchestrator."""

from datetime import date

from app.pipeline import run_full_pipeline
from app.ssot import SSOTInput


def test_pipeline_empty_input():
    """Test pipeline with empty input returns success."""
    ssot_input = SSOTInput()
    result = run_full_pipeline(ssot_input)

    # Empty input should succeed (no validation errors)
    assert result.success is True
    assert result.ssot is not None
    assert result.error is None


def test_pipeline_returns_ssot():
    """Test pipeline returns SSOT with input."""
    ssot_input = SSOTInput(
        filing_date=date(2024, 1, 15),
        industry="general",
    )
    result = run_full_pipeline(ssot_input)

    assert result.success is True
    assert result.ssot.input.filing_date == date(2024, 1, 15)
    assert result.ssot.input.industry == "general"
