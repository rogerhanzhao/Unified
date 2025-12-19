"""Single-line diagram helper logic."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from validation import require_non_empty


@dataclass
class SLDRequest:
    ac_blocks: int
    layout_note: str


def build_sld(req: SLDRequest) -> Dict[str, Any]:
    issues = [
        issue
        for issue in [
            require_non_empty("layout note", req.layout_note),
        ]
        if issue
    ]
    if issues:
        raise ValueError(issues)

    return {
        "diagram": f"AC Blocks: {req.ac_blocks} | Note: {req.layout_note}",
        "warnings": ["Placeholder SLD generated for preview only."],
    }
