import datetime
import hashlib
import json
from typing import Dict, List, Optional

from calb_sizing_tool.common.ac_block import derive_ac_template_fields


def _snapshot_hash(snapshot: dict) -> str:
    payload = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def _safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def _build_feeders(pcs_kw: float) -> List[Dict]:
    feeders = []
    for idx in range(1, 5):
        feeders.append(
            {
                "feeder_id": f"FDR-{idx:02d}",
                "pcs_id": f"PCS-{idx:02d}",
                "pcs_kw": pcs_kw,
                "breaker_present": True,
            }
        )
    return feeders


def _allocate_dc_blocks(
    dc_blocks_total: int, dc_block_unit_mwh: Optional[float]
) -> List[Dict]:
    allocations = []
    base = dc_blocks_total // 4
    remainder = dc_blocks_total % 4

    for idx in range(4):
        count = base + (1 if idx < remainder else 0)
        entry = {"feeder_id": f"FDR-{idx+1:02d}", "dc_blocks": count}
        if dc_block_unit_mwh:
            entry["dc_energy_mwh"] = count * dc_block_unit_mwh
        allocations.append(entry)
    return allocations


def _compute_chain_dc_blocks(stage4_output: dict) -> int:
    ac_blocks_total = _safe_int(stage4_output.get("num_blocks") or stage4_output.get("ac_blocks_total") or 0)
    if stage4_output.get("dc_blocks_total") is not None:
        total_dc_blocks = _safe_int(stage4_output.get("dc_blocks_total"))
    else:
        base_dc_blocks = _safe_int(
            stage4_output.get("dc_block_total_qty")
            or stage4_output.get("container_count")
            or 0
        )
        total_dc_blocks = base_dc_blocks + _safe_int(stage4_output.get("cabinet_count") or 0)

    if ac_blocks_total <= 0:
        return total_dc_blocks

    avg_per_block = total_dc_blocks / ac_blocks_total
    return max(0, int(round(avg_per_block)))


def build_sld_snapshot_v1(stage4_output: dict, project_inputs: dict, scenario_id: str) -> dict:
    project_inputs = project_inputs or {}
    stage4_output = stage4_output or {}

    template_fields = derive_ac_template_fields(stage4_output)
    ac_block_template_id = stage4_output.get("ac_block_template_id") or template_fields["ac_block_template_id"]

    pcs_per_block = 4
    feeders_per_block = 4

    block_size_mw = _safe_float(stage4_output.get("block_size_mw"))
    pcs_kw = block_size_mw * 1000 / pcs_per_block if block_size_mw and pcs_per_block else 0.0

    mv_kv = _safe_float(stage4_output.get("grid_kv") or project_inputs.get("poi_nominal_voltage_kv"), 33.0)
    lv_kv = _safe_float(stage4_output.get("inverter_lv_v"), 800.0) / 1000.0

    grid_power_factor = template_fields.get("grid_power_factor") or 0.9
    transformer_kva = stage4_output.get("transformer_kva")
    if transformer_kva is None and block_size_mw:
        transformer_kva = block_size_mw * 1000 / grid_power_factor if grid_power_factor else None
    transformer_kva = _safe_float(transformer_kva, 0.0)

    dc_block_unit_mwh = stage4_output.get("dc_block_unit_mwh")
    dc_blocks_total_chain = _compute_chain_dc_blocks(stage4_output)
    dc_total_energy_mwh = (
        dc_blocks_total_chain * dc_block_unit_mwh if dc_block_unit_mwh else None
    )

    project_name = project_inputs.get("project_name") or stage4_output.get("project_name") or "CALB ESS Project"
    poi_energy_guarantee_mwh = (
        project_inputs.get("poi_energy_guarantee_mwh")
        or project_inputs.get("poi_energy_requirement_mwh")
        or stage4_output.get("poi_energy_mwh")
    )

    snapshot = {
        "schema_version": "sld_snapshot_v1",
        "snapshot_id": f"SLD-{project_name}-{scenario_id}-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}",
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "project": {
            "project_name": project_name,
            "scenario_id": scenario_id,
            "poi_power_requirement_mw": project_inputs.get("poi_power_requirement_mw") or stage4_output.get("poi_power_mw"),
            "poi_energy_requirement_mwh": project_inputs.get("poi_energy_requirement_mwh") or stage4_output.get("poi_energy_mwh"),
            "poi_energy_guarantee_mwh": poi_energy_guarantee_mwh,
            "poi_frequency_hz": project_inputs.get("poi_frequency_hz"),
        },
        "mv_node": {
            "node_id": "MV_NODE_01",
            "mv_kv_ac": mv_kv,
        },
        "rmu": {
            "device_type": "RMU",
            "present": True,
        },
        "transformer": {
            "id": "TR_01",
            "rated_kva": transformer_kva,
            "rated_mva": transformer_kva / 1000.0 if transformer_kva else None,
            "hv_kv": mv_kv,
            "lv_kv": lv_kv,
        },
        "ac_block": {
            "template_id": ac_block_template_id,
            "feeders_per_block": feeders_per_block,
            "pcs_per_block": pcs_per_block,
        },
        "dc_block_summary": {
            "dc_blocks_total": dc_blocks_total_chain,
            "dc_block_unit_mwh": dc_block_unit_mwh,
            "dc_total_energy_mwh": dc_total_energy_mwh,
        },
        "feeders": _build_feeders(pcs_kw),
        "dc_blocks_by_feeder": _allocate_dc_blocks(dc_blocks_total_chain, dc_block_unit_mwh),
    }

    snapshot["snapshot_hash"] = _snapshot_hash(snapshot)
    return snapshot
