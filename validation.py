"""Validation helpers shared across Streamlit pages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class ValidationIssue:
    field: str
    message: str


def require_positive_number(name: str, value) -> Optional[ValidationIssue]:
    """Ensure the value can be interpreted as a positive float."""
    try:
        val = float(value)
    except (TypeError, ValueError):
        return ValidationIssue(name, "must be a number")

    if val <= 0:
        return ValidationIssue(name, "must be greater than 0")
    return None


def require_non_empty(name: str, value) -> Optional[ValidationIssue]:
    if value is None or (hasattr(value, "__len__") and len(value) == 0):
        return ValidationIssue(name, "cannot be empty")
    return None


def summarize(issues: List[ValidationIssue]) -> Tuple[bool, str]:
    """Return ok flag and printable summary."""
    if not issues:
        return True, "All inputs validated successfully."
    return False, "; ".join(f"{iss.field}: {iss.message}" for iss in issues)
