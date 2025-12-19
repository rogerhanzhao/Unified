"""Layout generation logic."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from validation import require_positive_number


@dataclass
class LayoutRequest:
    dc_blocks: float
    ac_blocks: float
    site_area_acres: float


def compute_layout(req: LayoutRequest) -> Dict[str, Any]:
    issues = [
        issue
        for issue in [
            require_positive_number("DC Blocks", req.dc_blocks),
            require_positive_number("AC Blocks", req.ac_blocks),
            require_positive_number("Site Area (acres)", req.site_area_acres),
        ]
        if issue
    ]
    if issues:
        raise ValueError(issues)

    density = req.dc_blocks / req.site_area_acres
    return {
        "dc_blocks": req.dc_blocks,
        "ac_blocks": req.ac_blocks,
        "site_area_acres": req.site_area_acres,
        "density_blocks_per_acre": round(density, 3),
        "notes": ["Layout density is an approximate placeholder for visualization."],
    }
