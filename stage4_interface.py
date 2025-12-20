# stage4_interface.py
# Minimal, robust interface between Stage 1–3 (DC sizing) and Stage 4 (AC Block sizing).
# Keeps payload JSON-/session_state-friendly (no raw DataFrames).

from __future__ import annotations
from typing import Any, Dict
import time

def pack_stage13_output(
    stage1: Dict[str, Any],
    stage2: Dict[str, Any],
    stage3: Dict[str, Any],
    dc_block_total_qty: int,
    selected_scenario: str,
    poi_nominal_voltage_kv: float,
    highest_equipment_voltage_kv: float | None = None,
) -> Dict[str, Any]:
    """Pack Stage 1–3 outputs into a lightweight dict for Stage 4.

    Args:
        stage1: Output dict from Stage 1.
        stage2: Output dict from Stage 2 (should be sanitized; no DataFrames).
        stage3: Meta dict from Stage 3.
        dc_block_total_qty: Total 5MWh DC Block containers (for Stage 4 layout / AC sizing).
        selected_scenario: 'container_only' / 'hybrid' / 'cabinet_only' etc.
        poi_nominal_voltage_kv: MV voltage used for Stage 4.
        highest_equipment_voltage_kv: Optional MV equipment BIL; defaults to POI voltage if omitted.

    Returns:
        A dict safe to store in st.session_state.
    """
    s1 = dict(stage1 or {})
    s2 = dict(stage2 or {})
    s3 = dict(stage3 or {})

    # Normalize common keys for Stage 4 convenience
    out: Dict[str, Any] = {
        "packed_at_epoch": int(time.time()),
        "selected_scenario": selected_scenario,
        "poi_nominal_voltage_kv": float(poi_nominal_voltage_kv),
        "dc_block_total_qty": int(dc_block_total_qty),
        "highest_equipment_voltage_kv": float(
            highest_equipment_voltage_kv
            if highest_equipment_voltage_kv is not None
            else poi_nominal_voltage_kv
        ),

        # Stage 2 (sanitized)
        "container_count": int(s2.get("container_count", 0) or 0),
        "cabinet_count": int(s2.get("cabinet_count", 0) or 0),
        "busbars_needed": int(s2.get("busbars_needed", 0) or 0),
        "dc_nameplate_bol_mwh": float(s2.get("dc_nameplate_bol_mwh", 0.0) or 0.0),

        # Stage 1 essentials
        "project_name": str(s1.get("project_name", "CALB ESS Project")),
        "poi_power_req_mw": float(s1.get("poi_power_req_mw", 0.0) or 0.0),
        "poi_energy_req_mwh": float(s1.get("poi_energy_req_mwh", 0.0) or 0.0),
        "eff_dc_to_poi_frac": float(s1.get("eff_dc_to_poi_frac", 0.0) or 0.0),
        "dc_power_required_mw": float(s1.get("dc_power_required_mw", 0.0) or 0.0),

        # Stage 3 selection meta (useful for traceability)
        "effective_c_rate": float(s3.get("effective_c_rate", 0.0) or 0.0),
        "soh_profile_id": int(s3.get("soh_profile_id", 0) or 0),
        "rte_profile_id": int(s3.get("rte_profile_id", 0) or 0),
    }

    # Optionally carry over small extra fields (safe primitives only)
    for k in ["block_config_table_records", "oversize_mwh", "config_adjustment_frac", "mode"]:
        if k in s2:
            out[k] = s2[k]

    return out
