"""AC sizing logic layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from data_io import DEFAULT_AC_DATA_PATH, DataIOError, debug_payload, load_dictionary, resolve_data_path
from validation import ValidationIssue, require_positive_number


@dataclass
class ACRequest:
    data_path: Optional[str]
    poi_power_mw: float
    dc_block_qty: float


def run_ac_sizing(req: ACRequest) -> Dict[str, Any]:
    issues = [
        issue
        for issue in [
            require_positive_number("POI Power (MW)", req.poi_power_mw),
            require_positive_number("DC Block Qty", req.dc_block_qty),
        ]
        if issue
    ]
    if issues:
        raise ValueError(issues)

    path = resolve_data_path(req.data_path, DEFAULT_AC_DATA_PATH)
    dictionary = load_dictionary(path)

    blocks_per_ac = max(1, int(req.dc_block_qty // 4))
    ac_blocks_needed = max(1, int(req.poi_power_mw // 2.5) + 1)

    return {
        "inputs": {"poi_power_mw": req.poi_power_mw, "dc_block_qty": req.dc_block_qty},
        "ac_blocks_needed": ac_blocks_needed,
        "dc_blocks_per_ac_block": blocks_per_ac,
        "data_debug": debug_payload(dictionary),
    }
