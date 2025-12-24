import datetime
import hashlib
import json
import re
from typing import Dict, List, Optional

from calb_sizing_tool.common.ac_block import derive_ac_template_fields


def _snapshot_hash(snapshot: dict) -> str:
    payload = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def _parse_feeders_per_block(template_id: Optional[str]) -> Optional[int]:
    if not template_id:
        return None
    match = re.search(r"(\d+)\s*x", template_id.lower())
    if match:
        try:
            return int(match.group(1))
        except Exception:
            return None
    return None


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


def _build_feeders(ac_blocks_total: int, feeders_per_block: int, pcs_rating_kw: float) -> List[Dict]:
    feeders = []
    feeder_count = ac_blocks_total * feeders_per_block if ac_blocks_total and feeders_per_block else 0
    for idx in range(1, feeder_count + 1):
        feeders.append(
            {
                "feeder_id": f"FDR_{idx:02d}",
                "ac_block_index": (idx - 1) // feeders_per_block + 1 if feeders_per_block else 1,
                "pcs_id": f"PCS-{idx:02d}",
                "pcs_rating_kw": pcs_rating_kw,
            }
        )
    return feeders


def _allocate_dc_blocks(
    feeder_count: int, dc_blocks_total: int, dc_block_unit_mwh: Optional[float]
) -> List[Dict]:
    allocations = []
    if feeder_count <= 0:
        return allocations

    base = dc_blocks_total // feeder_count if feeder_count else 0
    remainder = dc_blocks_total % feeder_count if feeder_count else 0

    for idx in range(feeder_count):
        count = base + (1 if idx < remainder else 0)
        entry = {"feeder_id": f"FDR_{idx+1:02d}", "dc_blocks": count}
        if dc_block_unit_mwh:
            entry["dc_energy_mwh"] = count * dc_block_unit_mwh
        allocations.append(entry)
    return allocations


def build_sld_snapshot_v1(stage4_output: dict, project_inputs: dict, scenario_id: str) -> dict:
    project_inputs = project_inputs or {}
    stage4_output = stage4_output or {}

    template_fields = derive_ac_template_fields(stage4_output)
    ac_block_template_id = template_fields["ac_block_template_id"]
    pcs_per_block = template_fields["pcs_per_block"]
    feeders_per_block = template_fields["feeders_per_block"] or _parse_feeders_per_block(ac_block_template_id) or pcs_per_block
    grid_power_factor = template_fields["grid_power_factor"]

    ac_blocks_total = _safe_int(stage4_output.get("num_blocks") or stage4_output.get("ac_blocks_total"))
    pcs_rating_kw = _safe_float(stage4_output.get("pcs_power_kw"))
    if not pcs_rating_kw and pcs_per_block:
        pcs_rating_kw = _safe_float(stage4_output.get("block_size_mw")) * 1000 / pcs_per_block

    if stage4_output.get("dc_blocks_total") is not None:
        dc_blocks_total = _safe_int(stage4_output.get("dc_blocks_total"))
    else:
        base_dc_blocks = _safe_int(
            stage4_output.get("dc_block_total_qty")
            or stage4_output.get("container_count")
            or 0
        )
        dc_blocks_total = base_dc_blocks + _safe_int(stage4_output.get("cabinet_count") or 0)

    dc_block_unit_mwh = stage4_output.get("dc_block_unit_mwh")
    dc_total_energy_mwh = stage4_output.get("dc_total_energy_mwh")

    project_name = project_inputs.get("project_name") or stage4_output.get("project_name") or "CALB ESS Project"
    poi_energy_guarantee_mwh = (
        project_inputs.get("poi_energy_guarantee_mwh")
        or project_inputs.get("poi_energy_requirement_mwh")
        or stage4_output.get("poi_energy_mwh")
    )

    feeders = _build_feeders(ac_blocks_total, feeders_per_block, pcs_rating_kw)
    dc_blocks_by_feeder = _allocate_dc_blocks(len(feeders), dc_blocks_total, dc_block_unit_mwh)

    poi_power_requirement_mw = (
        project_inputs.get("poi_power_requirement_mw") or stage4_output.get("poi_power_mw")
    )
    poi_energy_requirement_mwh = (
        project_inputs.get("poi_energy_requirement_mwh") or stage4_output.get("poi_energy_mwh")
    )

    snapshot = {
        "schema_version": "sld_snapshot_v1",
        "snapshot_id": f"SLD-{project_name}-{scenario_id}-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}",
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "project": {
            "project_name": project_name,
            "scenario_id": scenario_id,
            "poi_power_requirement_mw": poi_power_requirement_mw,
            "poi_energy_requirement_mwh": poi_energy_requirement_mwh,
            "poi_energy_guarantee_mwh": poi_energy_guarantee_mwh,
            "poi_nominal_voltage_kv": project_inputs.get("poi_nominal_voltage_kv"),
            "poi_frequency_hz": project_inputs.get("poi_frequency_hz"),
        },
        "ac_system": {
            "topology": "BUS_BREAKER",
            "ac_block_template_id": ac_block_template_id,
            "ac_blocks_total": ac_blocks_total,
            "pcs_per_block": pcs_per_block,
            "feeders_per_block": feeders_per_block,
            "feeders_total": len(feeders),
            "grid_mv_voltage_kv_ac": stage4_output.get("grid_kv"),
            "pcs_lv_voltage_v_ll_rms_ac": stage4_output.get("inverter_lv_v"),
            "grid_power_factor": grid_power_factor,
            "transformer_rating_kva": stage4_output.get("transformer_kva"),
            "ac_block_size_mw": stage4_output.get("block_size_mw"),
            "pcs_rating_kw": pcs_rating_kw,
        },
        "dc_system": {
            "dc_blocks_total": dc_blocks_total,
            "dc_block_unit_mwh": dc_block_unit_mwh,
            "dc_total_energy_mwh": dc_total_energy_mwh,
        },
        "feeders": feeders,
        "dc_blocks_by_feeder": dc_blocks_by_feeder,
    }

    snapshot["snapshot_hash"] = _snapshot_hash(snapshot)
    return snapshot
