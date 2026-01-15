# -----------------------------------------------------------------------------
# Personal Open-Source Notice
#
# Copyright (c) 2026 Alex.Zhao. All rights reserved.
#
# This repository is released under the MIT License (see LICENSE file).
# Intended use: learning, evaluation, and engineering reference for Utility-scale
# BESS/ESS sizing and Reporting workflows.
#
# DISCLAIMER: This software is provided "AS IS", without warranty of any kind,
# express or implied. In no event shall the author(s) be liable for any claim,
# damages, or other liability arising from, out of, or in connection with the
# software or the use or other dealings in the software.
#
# NOTE: This is a personal project. It is not an official product or statement
# of any company or organization.
# -----------------------------------------------------------------------------

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


def _build_feeders(pcs_rating_each_kw: float) -> List[Dict]:
    feeders = []
    for idx in range(1, 5):
        feeders.append(
            {
                "feeder_id": f"FDR-{idx:02d}",
                "pcs_id": f"PCS-{idx:02d}",
                "pcs_rating": pcs_rating_each_kw,
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
        entry = {
            "feeder_id": f"FDR-{idx+1:02d}",
            "dc_block_count": count,
            "dc_block_energy_mwh": None,
        }
        if dc_block_unit_mwh:
            entry["dc_block_energy_mwh"] = count * dc_block_unit_mwh
        allocations.append(entry)
    return allocations


def _compute_chain_dc_blocks(stage13_output: dict, ac_output: dict, dc_summary: dict) -> int:
    total_dc_blocks = _safe_int(stage13_output.get("dc_block_total_qty") or 0)
    if total_dc_blocks <= 0:
        total_dc_blocks = _safe_int(stage13_output.get("container_count") or 0) + _safe_int(
            stage13_output.get("cabinet_count") or 0
        )
    if total_dc_blocks <= 0 and isinstance(dc_summary, dict):
        dc_block = dc_summary.get("dc_block")
        if dc_block is not None:
            total_dc_blocks = _safe_int(getattr(dc_block, "count", 0))

    ac_blocks_total = _safe_int(ac_output.get("num_blocks") or ac_output.get("ac_blocks_total") or 0)
    if ac_blocks_total <= 0:
        return total_dc_blocks

    avg_per_block = total_dc_blocks / ac_blocks_total
    return max(0, int(round(avg_per_block)))


def build_sld_chain_snapshot_v2(
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
        sld_inputs.get("mv_kv")
        or ac_output.get("grid_kv")
        or stage13_output.get("poi_nominal_voltage_kv"),
        33.0,
    )
    pcs_lv_v = _safe_float(
        sld_inputs.get("pcs_lv_v")
        or ac_output.get("lv_v")
        or ac_output.get("inverter_lv_v"),
        0.0,
    )

    block_size_mw = _safe_float(
        sld_inputs.get("block_size_mw") or ac_output.get("block_size_mw"), 5.0
    )
    pcs_rating_each_kw = _safe_float(sld_inputs.get("pcs_rating_each_kw"))
    if pcs_rating_each_kw <= 0 and block_size_mw > 0:
        pcs_rating_each_kw = block_size_mw * 1000 / 4
    if pcs_rating_each_kw <= 0:
        pcs_rating_each_kw = _safe_float(ac_output.get("pcs_power_kw"), 0.0)

    transformer_rating_kva = _safe_float(
        sld_inputs.get("transformer_rating_kva") or ac_output.get("transformer_kva"),
        0.0,
    )
    if transformer_rating_kva <= 0 and block_size_mw > 0:
        transformer_rating_kva = block_size_mw * 1000 / 0.9

    template_fields = derive_ac_template_fields(
        {**ac_output, "pcs_per_block": 4, "feeders_per_block": 4}
    )
    ac_block_template_id = (
        sld_inputs.get("ac_block_template_id")
        or ac_output.get("ac_block_template_id")
        or template_fields["ac_block_template_id"]
    )
    if not ac_block_template_id and pcs_rating_each_kw:
        ac_block_template_id = f"4x{int(round(pcs_rating_each_kw))}kw"

    dc_block_unit_mwh = None
    dc_block = dc_summary.get("dc_block") if isinstance(dc_summary, dict) else None
    if dc_block is not None:
        dc_block_unit_mwh = getattr(dc_block, "capacity_mwh", None)
    dc_block_unit_mwh = _safe_float(sld_inputs.get("dc_block_unit_mwh"), dc_block_unit_mwh or 0.0)
    if dc_block_unit_mwh <= 0:
        dc_block_unit_mwh = None

    dc_blocks_by_feeder = sld_inputs.get("dc_blocks_by_feeder")
    if not isinstance(dc_blocks_by_feeder, list) or not dc_blocks_by_feeder:
        dc_blocks_total_chain = _compute_chain_dc_blocks(stage13_output, ac_output, dc_summary)
        dc_blocks_by_feeder = _allocate_dc_blocks(dc_blocks_total_chain, dc_block_unit_mwh)
    else:
        normalized = []
        for entry in dc_blocks_by_feeder:
            if not isinstance(entry, dict):
                continue
            feeder_id = entry.get("feeder_id")
            count = _safe_int(entry.get("dc_block_count"), 0)
            energy_mwh = entry.get("dc_block_energy_mwh")
            if energy_mwh is None and dc_block_unit_mwh:
                energy_mwh = count * dc_block_unit_mwh
            normalized.append(
                {
                    "feeder_id": feeder_id,
                    "dc_block_count": count,
                    "dc_block_energy_mwh": energy_mwh,
                }
            )
        dc_blocks_by_feeder = normalized

    feeders = sld_inputs.get("feeders")
    if not isinstance(feeders, list) or len(feeders) != 4:
        feeders = _build_feeders(pcs_rating_each_kw)

    labels = sld_inputs.get("labels") or {}
    if not isinstance(labels, dict):
        labels = {}

    snapshot = {
        "schema_version": "sld_chain_v2",
        "snapshot_id": f"SLD-Pro-{project_name}-{scenario_id}-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}",
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "project": {"name": project_name, "hz": project_hz, "scenario_id": scenario_id},
        "mv": {
            "kv": mv_kv,
            "node_id": "MV_NODE_01",
            "labels": {
                "to_switchgear": labels.get("to_switchgear") or "To MV Switchgear",
                "to_other_rmu": labels.get("to_other_rmu") or "To Other RMU",
            },
        },
        "rmu": sld_inputs.get("rmu", {}) or {},
        "transformer": {
            "rated_kva": transformer_rating_kva or None,
            "rated_mva": transformer_rating_kva / 1000.0 if transformer_rating_kva else None,
            "hv_kv": mv_kv,
            "lv_v": pcs_lv_v,
            "vector_group": sld_inputs.get("transformer", {}).get("vector_group"),
            "impedance_percent": sld_inputs.get("transformer", {}).get("impedance_percent"),
            "tap_range": sld_inputs.get("transformer", {}).get("tap_range"),
            "cooling": sld_inputs.get("transformer", {}).get("cooling"),
        },
        "ac_block": {
            "template_id": ac_block_template_id,
            "feeders_per_block": 4,
            "pcs_rating_each": pcs_rating_each_kw,
        },
        "feeders": feeders,
        "dc_blocks_by_feeder": dc_blocks_by_feeder,
        "equipment_list": sld_inputs.get("equipment_list"),
        "lv_busbar": sld_inputs.get("lv_busbar", {}) or {},
        "feeder_breaker": sld_inputs.get("feeder_breaker", {}) or {},
        "cables": sld_inputs.get("cables", {}) or {},
    }

    snapshot["snapshot_hash"] = _snapshot_hash(snapshot)
    return snapshot
