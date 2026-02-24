"""Error handling for the Claims Wizard pipeline."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ValidationError:
    """Single validation error with details."""

    type: str  # e.g., "uncovered_range", "invalid_range", "overlap"
    message: str  # Hebrew message for UI
    details: dict[str, Any] = field(default_factory=dict)  # Technical details


@dataclass
class PipelineError(Exception):
    """Error from a pipeline phase/module."""

    phase: str  # e.g., "weaver", "ot_pipeline", "salary_conversion"
    module: str  # File name
    errors: list[ValidationError] = field(default_factory=list)

    def __str__(self) -> str:
        error_msgs = [e.message for e in self.errors]
        return f"PipelineError in {self.phase}/{self.module}: {error_msgs}"


@dataclass
class PipelineResult:
    """Result of running the full pipeline."""

    success: bool
    ssot: Any | None = None  # Full SSOT if successful
    error: PipelineError | None = None  # Error details if failed
