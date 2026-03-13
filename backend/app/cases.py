"""Case management module.

Handles saving, loading, listing, and deleting case files (.case).

Each case file contains:
- version: Schema version
- last_modified_by: Who last modified (user/system)
- last_modified_at: When last modified (ISO 8601)
- input: SSOT.input (source of truth)
- cache: Optional computed results for quick loading
"""

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

# Version for case file format
CASE_VERSION = "1.0"

# Directory for case files
CASES_DIR = Path(__file__).parent.parent / "data" / "cases"


def ensure_cases_dir() -> None:
    """Ensure the cases directory exists."""
    CASES_DIR.mkdir(parents=True, exist_ok=True)


def _serialize_for_json(obj: Any) -> Any:
    """Recursively serialize objects for JSON."""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif hasattr(obj, "isoformat"):  # date, time
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: _serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_serialize_for_json(item) for item in obj]
    elif hasattr(obj, "__dataclass_fields__"):
        return {k: _serialize_for_json(getattr(obj, k)) for k in obj.__dataclass_fields__}
    elif hasattr(obj, "value"):  # Enum
        return obj.value
    return obj


def compute_input_hash(input_data: dict[str, Any]) -> str:
    """Compute SHA256 hash of input data for cache validation."""
    # Serialize to canonical JSON
    serialized = json.dumps(
        _serialize_for_json(input_data),
        sort_keys=True,
        ensure_ascii=False
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


@dataclass
class CaseMetaInfo:
    """Metadata about a case for listing."""
    case_id: str
    case_name: str
    worker_name: str | None
    defendant_name: str | None
    last_modified: str  # ISO datetime
    created_at: str  # ISO datetime
    has_results: bool


@dataclass
class SaveResult:
    """Result of saving a case."""
    success: bool
    saved_at: str  # ISO datetime
    error: str | None = None


@dataclass
class LoadResult:
    """Result of loading a case."""
    success: bool
    input: dict[str, Any] | None = None
    cache: dict[str, Any] | None = None
    needs_recalculation: bool = True
    error: str | None = None
    version_warning: str | None = None


def save_case(
    case_id: str,
    input_data: dict[str, Any],
    cache: dict[str, Any] | None = None,
) -> SaveResult:
    """Save a case to disk.

    Args:
        case_id: Unique case identifier (UUID)
        input_data: SSOT input data
        cache: Optional cached computation results (ssot + input_hash)

    Returns:
        SaveResult with success status and saved timestamp
    """
    ensure_cases_dir()

    now = datetime.now()

    case_data = {
        "version": CASE_VERSION,
        "last_modified_by": "user",
        "last_modified_at": now.isoformat(),
        "created_at": now.isoformat(),  # Will be preserved on update
        "input": _serialize_for_json(input_data),
    }

    # If cache is provided, include it
    if cache:
        case_data["cache"] = {
            "input_hash": cache.get("input_hash") or compute_input_hash(input_data),
            "computed_at": cache.get("computed_at", now.isoformat()),
            "ssot": _serialize_for_json(cache.get("ssot", {})),
        }

    # Check if file exists to preserve created_at
    case_file = CASES_DIR / f"{case_id}.case"
    if case_file.exists():
        try:
            with open(case_file, "r", encoding="utf-8") as f:
                existing = json.load(f)
                case_data["created_at"] = existing.get("created_at", now.isoformat())
        except (json.JSONDecodeError, IOError):
            pass  # Keep new created_at

    try:
        with open(case_file, "w", encoding="utf-8") as f:
            json.dump(case_data, f, ensure_ascii=False, indent=2)
        return SaveResult(success=True, saved_at=now.isoformat())
    except IOError as e:
        return SaveResult(success=False, saved_at="", error=str(e))


def load_case(case_id: str) -> LoadResult:
    """Load a case from disk.

    Args:
        case_id: Case identifier

    Returns:
        LoadResult with input, optional cache, and recalculation status
    """
    case_file = CASES_DIR / f"{case_id}.case"

    if not case_file.exists():
        return LoadResult(success=False, error=f"Case not found: {case_id}")

    try:
        with open(case_file, "r", encoding="utf-8") as f:
            case_data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        return LoadResult(success=False, error=f"Error reading case: {e}")

    # Version check
    file_version = case_data.get("version", "0.0")
    major_version = file_version.split(".")[0]
    current_major = CASE_VERSION.split(".")[0]

    version_warning = None
    if major_version != current_major:
        version_warning = f"Case file version {file_version} may not be compatible with current version {CASE_VERSION}"

    input_data = case_data.get("input")
    if not input_data:
        return LoadResult(success=False, error="Case file has no input data")

    cache = case_data.get("cache")
    needs_recalculation = True

    if cache:
        # Check if cache is still valid
        stored_hash = cache.get("input_hash")
        current_hash = compute_input_hash(input_data)

        if stored_hash == current_hash:
            needs_recalculation = False

    return LoadResult(
        success=True,
        input=input_data,
        cache=cache if not needs_recalculation else None,
        needs_recalculation=needs_recalculation,
        version_warning=version_warning,
    )


def list_cases() -> list[CaseMetaInfo]:
    """List all cases with metadata.

    Returns:
        List of CaseMetaInfo objects sorted by last_modified (newest first)
    """
    ensure_cases_dir()
    cases = []

    for case_file in CASES_DIR.glob("*.case"):
        case_id = case_file.stem

        try:
            with open(case_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            continue

        input_data = data.get("input", {})
        metadata = input_data.get("case_metadata", {})
        personal = input_data.get("personal", {})
        defendant = input_data.get("defendant", {})

        cases.append(CaseMetaInfo(
            case_id=case_id,
            case_name=metadata.get("case_name", case_id),
            worker_name=personal.get("name"),
            defendant_name=defendant.get("name"),
            last_modified=data.get("last_modified_at", ""),
            created_at=data.get("created_at", ""),
            has_results=bool(data.get("cache", {}).get("ssot")),
        ))

    # Sort by last_modified descending
    cases.sort(key=lambda c: c.last_modified, reverse=True)
    return cases


def delete_case(case_id: str) -> bool:
    """Delete a case file.

    Args:
        case_id: Case identifier

    Returns:
        True if deleted, False if not found
    """
    case_file = CASES_DIR / f"{case_id}.case"

    if not case_file.exists():
        return False

    try:
        case_file.unlink()
        return True
    except IOError:
        return False


def search_cases(query: str) -> list[CaseMetaInfo]:
    """Search cases by name, worker name, or defendant name.

    Args:
        query: Search query (case insensitive)

    Returns:
        Matching cases sorted by last_modified
    """
    query_lower = query.lower()
    all_cases = list_cases()

    matches = []
    for case in all_cases:
        if (
            query_lower in case.case_name.lower()
            or (case.worker_name and query_lower in case.worker_name.lower())
            or (case.defendant_name and query_lower in case.defendant_name.lower())
        ):
            matches.append(case)

    return matches
