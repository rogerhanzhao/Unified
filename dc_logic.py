"""DC sizing business logic."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import pandas as pd

from data_io import DEFAULT_DC_DATA_PATH, DataIOError, debug_payload, load_dictionary, resolve_data_path
from validation import ValidationIssue, require_positive_number


@dataclass
class DCRequest:
    data_path: Optional[str]
    poi_power_mw: float
    energy_mwh: float


def run_dc_sizing(req: DCRequest) -> Dict[str, Any]:
    issues = [
        issue
        for issue in [
            require_positive_number("POI Power (MW)", req.poi_power_mw),
            require_positive_number("Energy (MWh)", req.energy_mwh),
        ]
        if issue
    ]
    if issues:
        raise ValueError(issues)

    path = resolve_data_path(req.data_path, DEFAULT_DC_DATA_PATH)
    result = load_dictionary(path)
    # Placeholder computation: simple sizing ratio
    c_rate = req.poi_power_mw / req.energy_mwh if req.energy_mwh else 0
    return {
        "inputs": {"poi_power_mw": req.poi_power_mw, "energy_mwh": req.energy_mwh},
        "c_rate": round(c_rate, 3),
        "data_debug": debug_payload(result),
    }
