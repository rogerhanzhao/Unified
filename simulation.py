"""Simulation placeholder logic."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from validation import require_positive_number


@dataclass
class SimulationRequest:
    annual_cycles: float
    eff_rte: float
    soi_mwh: float


def run_simulation(req: SimulationRequest) -> Dict[str, Any]:
    issues = [
        issue
        for issue in [
            require_positive_number("Annual Cycles", req.annual_cycles),
            require_positive_number("Round-trip Efficiency", req.eff_rte),
            require_positive_number("Initial MWh", req.soi_mwh),
        ]
        if issue
    ]
    if issues:
        raise ValueError(issues)

    delivered_mwh = req.soi_mwh * (req.eff_rte / 100.0)
    total_energy = delivered_mwh * req.annual_cycles

    return {
        "delivered_mwh": round(delivered_mwh, 3),
        "total_energy_mwh": round(total_energy, 3),
        "notes": ["Simulation uses simplified placeholders; integrate full model later."],
    }
