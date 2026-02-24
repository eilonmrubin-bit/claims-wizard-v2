"""Tests for error handling."""

from app.errors import ValidationError, PipelineError, PipelineResult


def test_validation_error():
    """Test ValidationError creation."""
    error = ValidationError(
        type="uncovered_range",
        message="טווח לא מכוסה",
        details={"start": "2023-01-01", "end": "2023-03-31"},
    )

    assert error.type == "uncovered_range"
    assert error.message == "טווח לא מכוסה"
    assert error.details["start"] == "2023-01-01"


def test_pipeline_error():
    """Test PipelineError creation."""
    error = PipelineError(
        phase="weaver",
        module="validator.py",
        errors=[
            ValidationError(
                type="overlap",
                message="חפיפה בין תקופות",
            )
        ],
    )

    assert error.phase == "weaver"
    assert len(error.errors) == 1
    assert "weaver" in str(error)


def test_pipeline_result_success():
    """Test successful PipelineResult."""
    result = PipelineResult(success=True, ssot={"test": "data"})

    assert result.success is True
    assert result.ssot is not None
    assert result.error is None


def test_pipeline_result_failure():
    """Test failed PipelineResult."""
    error = PipelineError(
        phase="ot_pipeline",
        module="stage1.py",
        errors=[],
    )
    result = PipelineResult(success=False, error=error)

    assert result.success is False
    assert result.ssot is None
    assert result.error is not None
