import datetime
import hashlib
import json
from typing import Dict, List, Optional


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


def _build_feeders(pcs_rating_each_kva: float) -> List[Dict]:
    feeders = []
    for idx in range(1, 5):
        feeders.append(
            {
                "feeder_id": f"FDR-{idx:02d}",
                "pcs_id": f"PCS-{idx:02d}",
                "pcs_rating_kva": pcs_rating_each_kva,
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
        entry = {
            "feeder_id": f"FDR-{idx+1:02d}",
            "dc_block_count": count,
            "dc_block_energy_mwh": None,
        }
        if dc_block_unit_mwh:
            entry["dc_block_energy_mwh"] = count * dc_block_unit_mwh
        allocations.append(entry)
    return allocations


def _compute_site_dc_blocks(stage13_output: dict, dc_summary: dict) -> int:
    total_dc_blocks = _safe_int(stage13_output.get("dc_block_total_qty") or 0)
    if total_dc_blocks <= 0:
        total_dc_blocks = _safe_int(stage13_output.get("container_count") or 0) + _safe_int(
            stage13_output.get("cabinet_count") or 0
        )
    if total_dc_blocks <= 0 and isinstance(dc_summary, dict):
        dc_block = dc_summary.get("dc_block")
        if dc_block is not None:
            total_dc_blocks = _safe_int(getattr(dc_block, "count", 0))
    return total_dc_blocks


def _compute_site_ac_blocks(ac_output: dict) -> int:
    return _safe_int(ac_output.get("num_blocks") or ac_output.get("ac_blocks_total") or 0)


def build_single_unit_snapshot(
    stage13_output: dict,
    ac_output: dict,
    dc_summary: dict,
    sld_inputs: dict,
    scenario_id: str,
) -> dict:
    stage13_output = stage13_output or {}
    ac_output = ac_output or {}
    dc_summary = dc_summary or {}
    sld_inputs = sld_inputs or {}

    project_name = (
        stage13_output.get("project_name")
        or ac_output.get("project_name")
        or "CALB ESS Project"
    )
    project_hz = _safe_float(stage13_output.get("poi_frequency_hz"), 60.0)

    mv_kv = _safe_float(
        sld_inputs.get("mv_nominal_kv_ac")
        or ac_output.get("grid_kv")
        or stage13_output.get("poi_nominal_voltage_kv"),
        33.0,
    )
    pcs_lv_v = _safe_float(
        sld_inputs.get("pcs_lv_voltage_v_ll")
        or ac_output.get("inverter_lv_v"),
        690.0,
    )

    block_size_mw = _safe_float(ac_output.get("block_size_mw"), 5.0)

    transformer_rating_mva = _safe_float(
        sld_inputs.get("transformer_rating_mva"), 0.0
    )
    if transformer_rating_mva <= 0:
        transformer_kva = _safe_float(
            sld_inputs.get("transformer_rating_kva") or ac_output.get("transformer_kva"),
            0.0,
        )
        if transformer_kva > 0:
            transformer_rating_mva = transformer_kva / 1000.0
        elif block_size_mw > 0:
            transformer_rating_mva = block_size_mw / 0.9
    transformer_rating_mva = transformer_rating_mva or 5.0
    transformer_rating_kva = transformer_rating_mva * 1000.0

    pcs_rating_each_kva = _safe_float(sld_inputs.get("pcs_rating_each_kva"), 0.0)
    if pcs_rating_each_kva <= 0 and block_size_mw > 0:
        pcs_rating_each_kva = block_size_mw * 1000 / 4
    if pcs_rating_each_kva <= 0:
        pcs_rating_each_kva = _safe_float(ac_output.get("pcs_power_kw"), 0.0)
    pcs_rating_each_kva = pcs_rating_each_kva or 1250.0

    dc_block_unit_mwh = _safe_float(sld_inputs.get("dc_block_energy_mwh"), 0.0)
    if dc_block_unit_mwh <= 0:
        dc_block = dc_summary.get("dc_block") if isinstance(dc_summary, dict) else None
        if dc_block is not None:
            dc_block_unit_mwh = _safe_float(getattr(dc_block, "capacity_mwh", 0.0))
    dc_block_unit_mwh = dc_block_unit_mwh or 5.106

    feeders = sld_inputs.get("feeders")
    if not isinstance(feeders, list) or len(feeders) != 4:
        feeders = _build_feeders(pcs_rating_each_kva)

    site_ac_block_total = _safe_int(
        sld_inputs.get("site_ac_block_total") or _compute_site_ac_blocks(ac_output)
    )
    site_dc_block_total = _safe_int(
        sld_inputs.get("site_dc_block_total") or _compute_site_dc_blocks(stage13_output, dc_summary)
    )
    ratio_default = 0
    if site_ac_block_total > 0 and site_dc_block_total > 0:
        ratio_default = max(1, int(round(site_dc_block_total / site_ac_block_total)))

    dc_blocks_by_feeder = sld_inputs.get("dc_blocks_by_feeder")
    dc_blocks_for_one_ac_block_group = _safe_int(
        sld_inputs.get("dc_blocks_for_one_ac_block_group"), 0
    )

    if not isinstance(dc_blocks_by_feeder, list) or not dc_blocks_by_feeder:
        if dc_blocks_for_one_ac_block_group <= 0:
            if sld_inputs.get("use_site_ratio"):
                dc_blocks_for_one_ac_block_group = ratio_default or 4
            else:
                dc_blocks_for_one_ac_block_group = 4
        dc_blocks_by_feeder = _allocate_dc_blocks(
            dc_blocks_for_one_ac_block_group, dc_block_unit_mwh
        )
    else:
        normalized = []
        total_count = 0
        for entry in dc_blocks_by_feeder:
            if not isinstance(entry, dict):
                continue
            feeder_id = entry.get("feeder_id")
            count = _safe_int(entry.get("dc_block_count"), 0)
            total_count += count
            energy = entry.get("dc_block_energy_mwh")
            if energy is None and dc_block_unit_mwh:
                energy = count * dc_block_unit_mwh
            normalized.append(
                {
                    "feeder_id": feeder_id,
                    "dc_block_count": count,
                    "dc_block_energy_mwh": energy,
                }
            )
        dc_blocks_by_feeder = normalized
        if total_count > 0:
            dc_blocks_for_one_ac_block_group = total_count
        elif dc_blocks_for_one_ac_block_group <= 0:
            dc_blocks_for_one_ac_block_group = 4

    labels = sld_inputs.get("mv_labels") if isinstance(sld_inputs.get("mv_labels"), dict) else {}
    diagram_scope = sld_inputs.get("diagram_scope") or "one_ac_block_group"

    snapshot = {
        "schema_version": "sld_single_unit_v0_5",
        "snapshot_id": f"SLD-Raw-{project_name}-{scenario_id}-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}",
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "diagram_scope": diagram_scope,
        "site_ac_block_total": site_ac_block_total,
        "site_dc_block_total": site_dc_block_total,
        "dc_blocks_for_one_ac_block_group": dc_blocks_for_one_ac_block_group,
        "project": {"name": project_name, "scenario_id": scenario_id, "hz": project_hz},
        "mv": {
            "kv": mv_kv,
            "node_id": "MV_NODE_01",
            "labels": {
                "to_switchgear": labels.get("to_switchgear") or "To Switchgear",
                "to_other_rmu": labels.get("to_other_rmu") or "To Other RMU",
            },
        },
        "transformer": {
            "rated_mva": transformer_rating_mva,
            "rated_kva": transformer_rating_kva,
            "hv_kv": mv_kv,
            "lv_v": pcs_lv_v,
            "vector_group": sld_inputs.get("transformer", {}).get("vector_group"),
            "uk_percent": sld_inputs.get("transformer", {}).get("uk_percent"),
            "tap_range": sld_inputs.get("transformer", {}).get("tap_range"),
            "cooling": sld_inputs.get("transformer", {}).get("cooling"),
        },
        "ac_block": {
            "pcs_count": 4,
            "pcs_rating_each_kva": pcs_rating_each_kva,
            "pcs_lv_voltage_v_ll": pcs_lv_v,
        },
        "feeders": feeders,
        "dc_block_energy_mwh": dc_block_unit_mwh,
        "dc_blocks_by_feeder": dc_blocks_by_feeder,
        "electrical_inputs": {
            "rmu": sld_inputs.get("rmu", {}) or {},
            "transformer": sld_inputs.get("transformer", {}) or {},
            "lv_busbar": sld_inputs.get("lv_busbar", {}) or {},
            "cables": sld_inputs.get("cables", {}) or {},
            "dc_fuse": sld_inputs.get("dc_fuse", {}) or {},
        },
    }

    snapshot["snapshot_hash"] = _snapshot_hash(snapshot)
    return snapshot


def validate_single_unit_snapshot(snapshot: dict) -> None:
    if not isinstance(snapshot, dict):
        raise ValueError("Snapshot must be a dict.")

    if snapshot.get("schema_version") != "sld_single_unit_v0_5":
        raise ValueError("Unsupported snapshot schema_version.")

    project = snapshot.get("project")
    if not isinstance(project, dict):
        raise ValueError("Snapshot 'project' must be a dict.")
    for key in ("name", "hz"):
        if key not in project:
            raise ValueError(f"Missing '{key}' in project.")

    mv = snapshot.get("mv")
    if not isinstance(mv, dict):
        raise ValueError("Snapshot 'mv' must be a dict.")
    for key in ("kv", "node_id", "labels"):
        if key not in mv:
            raise ValueError(f"Missing '{key}' in mv.")

    transformer = snapshot.get("transformer")
    if not isinstance(transformer, dict):
        raise ValueError("Snapshot 'transformer' must be a dict.")
    for key in ("rated_mva", "hv_kv", "lv_v"):
        if key not in transformer:
            raise ValueError(f"Missing '{key}' in transformer.")

    ac_block = snapshot.get("ac_block")
    if not isinstance(ac_block, dict):
        raise ValueError("Snapshot 'ac_block' must be a dict.")
    for key in ("pcs_count", "pcs_rating_each_kva", "pcs_lv_voltage_v_ll"):
        if key not in ac_block:
            raise ValueError(f"Missing '{key}' in ac_block.")

    feeders = snapshot.get("feeders")
    if not isinstance(feeders, list) or len(feeders) != 4:
        raise ValueError("Snapshot 'feeders' must be a list of 4 feeders.")
    for feeder in feeders:
        if not isinstance(feeder, dict):
            raise ValueError("Each feeder entry must be a dict.")
        for key in ("feeder_id", "pcs_id"):
            if key not in feeder:
                raise ValueError(f"Missing '{key}' in feeders[].")

    dc_blocks_by_feeder = snapshot.get("dc_blocks_by_feeder")
    if not isinstance(dc_blocks_by_feeder, list) or len(dc_blocks_by_feeder) != 4:
        raise ValueError("Snapshot 'dc_blocks_by_feeder' must be a list of 4 entries.")
