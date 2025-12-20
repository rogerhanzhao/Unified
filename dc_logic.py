from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple

import pandas as pd


def select_soh_profile(effective_c_rate: float, cycles_per_year: int, df_soh_profile: pd.DataFrame) -> Tuple[int, float, int]:
    """Pick the closest SOH profile by C-rate and cycles."""
    df = df_soh_profile.copy()
    df["c_rate_diff"] = (df["C_Rate"] - effective_c_rate).abs()
    df["cycles_diff"] = (df["Cycles_Per_Year"] - cycles_per_year).abs()
    df["score"] = df["c_rate_diff"] * 10.0 + df["cycles_diff"] / 365.0
    best = df.sort_values("score").iloc[0]
    return int(best["Profile_Id"]), float(best["C_Rate"]), int(best["Cycles_Per_Year"])


def select_rte_profile(effective_c_rate: float, df_rte_profile: pd.DataFrame) -> Tuple[int, float]:
    """Pick the closest RTE profile by C-rate."""
    df = df_rte_profile.copy()
    df["c_rate_diff"] = (df["C_Rate"] - effective_c_rate).abs()
    best = df.sort_values("c_rate_diff").iloc[0]
    return int(best["Profile_Id"]), float(best["C_Rate"])


@dataclass
class FaultEquivalent:
    fault_mva: float
    dc_short_circuit_ka: float
    basis_voltage_kv: float
    description: str


def estimate_dc_fault_equivalent(
    dc_blocks: int,
    *,
    dc_busbars: int = 2,
    dc_nominal_kv: float = 1.5,
    per_block_short_circuit_ka: float = 7.5,
    busbar_impedance_pct: float = 8.0,
) -> FaultEquivalent:
    """Estimate a DC fault equivalent used by Stage 4 power-flow sanity checks."""
    dc_blocks = max(dc_blocks, 0)
    dc_busbars = max(dc_busbars, 1)

    # Spread blocks evenly; a split factor approximates effective contribution during a fault.
    blocks_per_busbar = dc_blocks / dc_busbars
    dc_short_circuit_ka = blocks_per_busbar * per_block_short_circuit_ka

    z_pu = max(busbar_impedance_pct / 100.0, 0.01)
    base_mva = (dc_nominal_kv ** 2) / z_pu
    fault_mva = base_mva * (dc_short_circuit_ka / (per_block_short_circuit_ka or 1.0))

    return FaultEquivalent(
        fault_mva=fault_mva,
        dc_short_circuit_ka=dc_short_circuit_ka,
        basis_voltage_kv=dc_nominal_kv,
        description=(
            f"{dc_blocks} blocks across {dc_busbars} busbars, "
            f"{dc_short_circuit_ka:.1f} kA short-circuit, {fault_mva:.1f} MVA equivalent."
        ),
    )
