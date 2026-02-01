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

from dataclasses import dataclass
from typing import List, Optional, Sequence

from calb_sizing_tool.common.allocation import allocate_dc_blocks, evenly_distribute
from calb_sizing_tool.common.nameplate import get_standard_container_mwh


def _safe_int(value, default=0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _safe_float(value, default=0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _normalize_counts(values: Sequence, expected_len: int) -> List[int]:
    if not isinstance(values, (list, tuple)) or expected_len <= 0:
        return []
    counts = []
    for entry in values:
        counts.append(_safe_int(entry, 0))
    if len(counts) == expected_len:
        return counts
    if len(counts) > expected_len:
        return counts[:expected_len]
    counts.extend([0 for _ in range(expected_len - len(counts))])
    return counts


def _resolve_pcs_count_by_block(ac_output: dict, ac_blocks_total: int) -> List[int]:
    pcs_counts = _normalize_counts(ac_output.get("pcs_count_by_block"), ac_blocks_total)
    if pcs_counts:
        return pcs_counts

    pcs_per_block = _safe_int(ac_output.get("pcs_per_block"), 0)
    total_pcs = _safe_int(ac_output.get("total_pcs"), 0)
    if ac_blocks_total > 0 and total_pcs > 0:
        return evenly_distribute(total_pcs, ac_blocks_total)
    if ac_blocks_total > 0 and pcs_per_block > 0:
        return [pcs_per_block for _ in range(ac_blocks_total)]
    return [4] if ac_blocks_total == 1 else []


def _resolve_dc_blocks_total_by_block(
    ac_output: dict,
    stage13_output: dict,
    dc_summary: dict,
    ac_blocks_total: int,
) -> List[int]:
    totals = _normalize_counts(ac_output.get("dc_blocks_total_by_block"), ac_blocks_total)
    if totals:
        return totals

    dc_per_ac = _safe_int(ac_output.get("dc_blocks_per_ac"), 0)
    if ac_blocks_total > 0 and dc_per_ac > 0:
        return [dc_per_ac for _ in range(ac_blocks_total)]

    total_dc_blocks = _safe_int(stage13_output.get("dc_block_total_qty"), 0)
    if total_dc_blocks <= 0:
        total_dc_blocks = _safe_int(stage13_output.get("container_count"), 0) + _safe_int(
            stage13_output.get("cabinet_count"), 0
        )
    if total_dc_blocks <= 0 and isinstance(dc_summary, dict):
        dc_block = dc_summary.get("dc_block")
        if dc_block is not None:
            total_dc_blocks = _safe_int(getattr(dc_block, "count", 0))

    if ac_blocks_total > 0:
        return evenly_distribute(total_dc_blocks, ac_blocks_total)
    return []


@dataclass
class AcBlockGroupSpec:
    group_index: int
    mv_voltage_kv: float
    lv_voltage_v_ll: float
    transformer_rating_mva: float
    transformer_uk_percent: Optional[float]
    transformer_vector_group: Optional[str]
    pcs_count: int
    pcs_rating_kva_list: List[float]
    dc_block_energy_mwh: float
    dc_blocks_per_feeder: List[int]
    dc_blocks_total_in_group: int
    rmu_ratings_text: Optional[str] = None
    ct_text: Optional[str] = None
    cable_specs: Optional[dict] = None
    fuse_spec: Optional[str] = None


def build_ac_block_group_spec(
    stage13_output: dict,
    ac_output: dict,
    dc_summary: dict,
    sld_inputs: dict,
    group_index: int,
) -> AcBlockGroupSpec:
    stage13_output = stage13_output or {}
    ac_output = ac_output or {}
    dc_summary = dc_summary or {}
    sld_inputs = sld_inputs or {}

    ac_blocks_total = _safe_int(ac_output.get("num_blocks") or ac_output.get("ac_blocks_total"), 0)
    if ac_blocks_total <= 0:
        ac_blocks_total = 1

    group_index = _safe_int(group_index, 1)
    if group_index < 1:
        group_index = 1
    if group_index > ac_blocks_total:
        group_index = ac_blocks_total
    group_idx = group_index - 1

    pcs_counts = _resolve_pcs_count_by_block(ac_output, ac_blocks_total)
    pcs_count = pcs_counts[group_idx] if group_idx < len(pcs_counts) else _safe_int(
        ac_output.get("pcs_per_block"), 4
    )
    if pcs_count <= 0:
        pcs_count = 1

    block_size_mw = _safe_float(ac_output.get("block_size_mw"), 0.0)
    pcs_rating_each_kva = _safe_float(sld_inputs.get("pcs_rating_each_kva"), 0.0)
    if pcs_rating_each_kva <= 0:
        pcs_rating_each_kva = _safe_float(ac_output.get("pcs_power_kw"), 0.0)
    if pcs_rating_each_kva <= 0 and block_size_mw > 0 and pcs_count > 0:
        pcs_rating_each_kva = block_size_mw * 1000 / pcs_count
    if pcs_rating_each_kva <= 0:
        pcs_rating_each_kva = 1250.0

    pcs_rating_list = sld_inputs.get("pcs_rating_kva_list")
    if not isinstance(pcs_rating_list, list) or len(pcs_rating_list) != pcs_count:
        pcs_rating_list = [pcs_rating_each_kva for _ in range(pcs_count)]

    mv_kv = _safe_float(
        sld_inputs.get("mv_nominal_kv_ac")
        or ac_output.get("mv_voltage_kv")
        or ac_output.get("mv_kv")
        or ac_output.get("grid_kv")
        or stage13_output.get("poi_nominal_voltage_kv"),
        33.0,
    )
    lv_v = _safe_float(
        sld_inputs.get("pcs_lv_voltage_v_ll")
        or ac_output.get("lv_voltage_v")
        or ac_output.get("lv_v")
        or ac_output.get("inverter_lv_v"),
        690.0,
    )

    transformer_rating_mva = _safe_float(sld_inputs.get("transformer_rating_mva"), 0.0)
    if transformer_rating_mva <= 0:
        transformer_kva = _safe_float(
            sld_inputs.get("transformer_rating_kva") or ac_output.get("transformer_kva"),
            0.0,
        )
        if transformer_kva > 0:
            transformer_rating_mva = transformer_kva / 1000.0
        elif block_size_mw > 0:
            transformer_rating_mva = block_size_mw / 0.9
    if transformer_rating_mva <= 0:
        transformer_rating_mva = 5.0

    dc_block_energy_mwh = _safe_float(sld_inputs.get("dc_block_energy_mwh"), 0.0)
    if dc_block_energy_mwh <= 0:
        dc_block = dc_summary.get("dc_block") if isinstance(dc_summary, dict) else None
        if dc_block is not None:
            dc_block_energy_mwh = _safe_float(getattr(dc_block, "capacity_mwh", 0.0))
    if dc_block_energy_mwh <= 0:
        dc_block_energy_mwh = get_standard_container_mwh()

    dc_blocks_per_feeder = None
    dc_blocks_per_feeder_by_block = ac_output.get("dc_blocks_per_feeder_by_block")
    if isinstance(dc_blocks_per_feeder_by_block, list) and dc_blocks_per_feeder_by_block:
        if group_idx < len(dc_blocks_per_feeder_by_block):
            candidate = dc_blocks_per_feeder_by_block[group_idx]
            if isinstance(candidate, list) and candidate:
                dc_blocks_per_feeder = _normalize_counts(candidate, pcs_count)

    if dc_blocks_per_feeder is None:
        dc_totals_by_block = _resolve_dc_blocks_total_by_block(
            ac_output, stage13_output, dc_summary, ac_blocks_total
        )
        dc_total_group = (
            dc_totals_by_block[group_idx] if group_idx < len(dc_totals_by_block) else 0
        )
        dc_blocks_per_feeder = allocate_dc_blocks(dc_total_group, pcs_count)
    return AcBlockGroupSpec(
        group_index=group_index,
        mv_voltage_kv=mv_kv,
        lv_voltage_v_ll=lv_v,
        transformer_rating_mva=transformer_rating_mva,
        transformer_uk_percent=sld_inputs.get("transformer", {}).get("uk_percent"),
        transformer_vector_group=sld_inputs.get("transformer", {}).get("vector_group"),
        pcs_count=pcs_count,
        pcs_rating_kva_list=pcs_rating_list,
        dc_block_energy_mwh=dc_block_energy_mwh,
        dc_blocks_per_feeder=dc_blocks_per_feeder,
        dc_blocks_total_in_group=sum(dc_blocks_per_feeder),
    )
