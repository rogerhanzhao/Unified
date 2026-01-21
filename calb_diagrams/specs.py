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

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from calb_sizing_tool.common.allocation import allocate_dc_blocks, evenly_distribute

SLD_FONT_FAMILY = "Arial, 'DejaVu Sans', sans-serif"
SLD_FONT_SIZE = 11
SLD_FONT_SIZE_SMALL = 10
SLD_FONT_SIZE_TITLE = 12
SLD_STROKE_THIN = 1.0
SLD_STROKE_THICK = 2.0
SLD_STROKE_OUTLINE = 1.4
SLD_DASH_ARRAY = "6,4"

LAYOUT_FONT_FAMILY = "Arial, 'DejaVu Sans', sans-serif"
LAYOUT_FONT_SIZE = 11
LAYOUT_FONT_SIZE_SMALL = 10
LAYOUT_FONT_SIZE_TITLE = 12
LAYOUT_STROKE_THIN = 1.0
LAYOUT_STROKE_OUTLINE = 1.2
LAYOUT_DASH_ARRAY = "6,4"


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

    pcs_units = ac_output.get("pcs_units")
    if isinstance(pcs_units, list) and pcs_units:
        return [len(pcs_units) for _ in range(ac_blocks_total or 1)]

    pcs_count_per_block = _safe_int(ac_output.get("pcs_count_per_ac_block"), 0)
    if ac_blocks_total > 0 and pcs_count_per_block > 0:
        return [pcs_count_per_block for _ in range(ac_blocks_total)]

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
    allocation = ac_output.get("dc_block_allocation")
    if isinstance(allocation, dict):
        per_ac_block = allocation.get("per_ac_block")
        if isinstance(per_ac_block, list) and per_ac_block:
            totals = []
            for entry in per_ac_block:
                total = entry.get("dc_blocks_total")
                if total is None:
                    per_feeder = entry.get("per_feeder")
                    if isinstance(per_feeder, dict):
                        total = sum(_safe_int(v, 0) for v in per_feeder.values())
                totals.append(_safe_int(total, 0))
            normalized = _normalize_counts(totals, ac_blocks_total)
            if normalized:
                return normalized

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
class SldGroupSpec:
    group_index: int
    mv_voltage_kv: float
    lv_voltage_v_ll: float
    transformer_mva: float
    transformer_vector_group: Optional[str]
    transformer_uk_percent: Optional[float]
    pcs_count: int
    pcs_rating_kw_list: List[float]
    dc_block_energy_mwh: float
    dc_blocks_total_in_group: int
    dc_blocks_per_feeder: List[int]
    equipment_list: Dict[str, Dict] = field(default_factory=dict)
    layout_params: Dict[str, float] = field(default_factory=dict)


@dataclass
class LayoutBlockSpec:
    block_indices_to_render: List[int]
    pcs_count: int = 4
    dc_blocks_per_block: int = 4
    dc_block_counts_by_block: Dict[int, int] = field(default_factory=dict)
    arrangement: str = "2x2"
    show_skid: bool = True
    labels: Dict[str, str] = field(default_factory=dict)
    container_length_mm: int = 6058
    container_width_mm: int = 2438
    dc_to_dc_clearance_m: Optional[float] = None
    dc_to_ac_clearance_m: Optional[float] = None
    perimeter_clearance_m: Optional[float] = None
    dc_block_mirrored: bool = False
    use_template: bool = False
    dc_block_svg_path: Optional[str] = None
    ac_block_svg_path: Optional[str] = None
    scale: float = 0.04
    left_margin: int = 40
    top_margin: int = 40
    theme: str = "light"


def build_sld_group_spec(
    stage13_output: dict,
    ac_output: dict,
    dc_summary: dict,
    sld_inputs: dict,
    group_index: int,
) -> SldGroupSpec:
    stage13_output = stage13_output or {}
    ac_output = ac_output or {}
    dc_summary = dc_summary or {}
    sld_inputs = sld_inputs or {}

    ac_blocks_total = _safe_int(ac_output.get("num_blocks") or ac_output.get("ac_blocks_total"), 0)
    if ac_blocks_total <= 0:
        # Try to infer from total PCS and PCS per block
        total_pcs = _safe_int(ac_output.get("total_pcs"), 0)
        pcs_per_block = _safe_int(ac_output.get("pcs_per_block"), 0)
        if total_pcs > 0 and pcs_per_block > 0:
            ac_blocks_total = total_pcs // pcs_per_block
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
    pcs_rating_each_kw = _safe_float(sld_inputs.get("pcs_rating_each_kw"), 0.0)
    if pcs_rating_each_kw <= 0:
        pcs_rating_each_kw = _safe_float(sld_inputs.get("pcs_rating_each_kva"), 0.0)
    if pcs_rating_each_kw <= 0:
        pcs_rating_each_kw = _safe_float(ac_output.get("pcs_power_kw"), 0.0)
    if pcs_rating_each_kw <= 0 and block_size_mw > 0 and pcs_count > 0:
        pcs_rating_each_kw = block_size_mw * 1000 / pcs_count
    if pcs_rating_each_kw <= 0:
        pcs_rating_each_kw = 1250.0

    pcs_rating_kw_list = sld_inputs.get("pcs_rating_kw_list")
    if not isinstance(pcs_rating_kw_list, list) or len(pcs_rating_kw_list) != pcs_count:
        pcs_rating_kw_list = [pcs_rating_each_kw for _ in range(pcs_count)]

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
        0.0,
    )

    transformer_mva = _safe_float(sld_inputs.get("transformer_rating_mva"), 0.0)
    if transformer_mva <= 0:
        transformer_mva = _safe_float(ac_output.get("transformer_mva"), 0.0)
    if transformer_mva <= 0:
        transformer_kva = _safe_float(
            sld_inputs.get("transformer_rating_kva") or ac_output.get("transformer_kva"),
            0.0,
        )
        if transformer_kva > 0:
            transformer_mva = transformer_kva / 1000.0
        elif block_size_mw > 0:
            transformer_mva = block_size_mw / 0.9
    if transformer_mva <= 0:
        transformer_mva = 5.0

    dc_block_energy_mwh = _safe_float(sld_inputs.get("dc_block_energy_mwh"), 0.0)
    if dc_block_energy_mwh <= 0:
        dc_block = dc_summary.get("dc_block") if isinstance(dc_summary, dict) else None
        if dc_block is not None:
            dc_block_energy_mwh = _safe_float(getattr(dc_block, "capacity_mwh", 0.0))
    if dc_block_energy_mwh <= 0:
        dc_block_energy_mwh = 5.106

    dc_blocks_per_feeder = _normalize_counts(sld_inputs.get("dc_blocks_per_feeder"), pcs_count)

    if not dc_blocks_per_feeder:
        allocation = ac_output.get("dc_block_allocation")
        if isinstance(allocation, dict):
            per_ac_block = allocation.get("per_ac_block")
            if isinstance(per_ac_block, list) and per_ac_block:
                if group_idx < len(per_ac_block):
                    per_feeder = per_ac_block[group_idx].get("per_feeder")
                    if isinstance(per_feeder, dict) and per_feeder:
                        keys = sorted(
                            per_feeder.keys(),
                            key=lambda k: _safe_int(str(k).lstrip("Ff"), 0),
                        )
                        dc_blocks_per_feeder = [
                            _safe_int(per_feeder.get(key), 0) for key in keys
                        ]
            if not dc_blocks_per_feeder:
                per_feeder = allocation.get("per_feeder")
                if isinstance(per_feeder, dict) and per_feeder:
                    keys = sorted(
                        per_feeder.keys(),
                        key=lambda k: _safe_int(str(k).lstrip("Ff"), 0),
                    )
                    dc_blocks_per_feeder = [
                        _safe_int(per_feeder.get(key), 0) for key in keys
                    ]
            if not dc_blocks_per_feeder:
                per_pcs_group = allocation.get("per_pcs_group")
                if isinstance(per_pcs_group, list) and per_pcs_group:
                    dc_blocks_per_feeder = [
                        _safe_int(item.get("dc_block_count"), 0) for item in per_pcs_group
                    ]

    if not dc_blocks_per_feeder:
        dc_blocks_per_feeder_by_block = ac_output.get("dc_blocks_per_feeder_by_block")
        if isinstance(dc_blocks_per_feeder_by_block, list) and dc_blocks_per_feeder_by_block:
            if group_idx < len(dc_blocks_per_feeder_by_block):
                candidate = dc_blocks_per_feeder_by_block[group_idx]
                if isinstance(candidate, list) and candidate:
                    dc_blocks_per_feeder = _normalize_counts(candidate, pcs_count)

    if not dc_blocks_per_feeder:
        dc_totals_by_block = _resolve_dc_blocks_total_by_block(
            ac_output, stage13_output, dc_summary, ac_blocks_total
        )
        dc_total_group = (
            dc_totals_by_block[group_idx] if group_idx < len(dc_totals_by_block) else 0
        )
        dc_blocks_per_feeder = allocate_dc_blocks(dc_total_group, pcs_count)

    dc_blocks_total_in_group = sum(dc_blocks_per_feeder)

    mv_labels = sld_inputs.get("mv_labels")
    if not isinstance(mv_labels, dict):
        mv_labels = {}

    equipment_list = sld_inputs.get("equipment_list")
    if not isinstance(equipment_list, dict):
        equipment_list = {
            "mv_labels": mv_labels,
            "rmu": sld_inputs.get("rmu", {}) or {},
            "transformer": sld_inputs.get("transformer", {}) or {},
            "lv_busbar": sld_inputs.get("lv_busbar", {}) or {},
            "cables": sld_inputs.get("cables", {}) or {},
            "dc_fuse": sld_inputs.get("dc_fuse", {}) or {},
        }
    dc_block_voltage_v = _safe_float(sld_inputs.get("dc_block_voltage_v"), 0.0)
    if dc_block_voltage_v <= 0 and isinstance(dc_summary, dict):
        dc_block = dc_summary.get("dc_block")
        if dc_block is not None:
            dc_block_voltage_v = _safe_float(getattr(dc_block, "voltage_v", 0.0), 0.0)
    project_hz = _safe_float(stage13_output.get("poi_frequency_hz"), 0.0)
    if project_hz > 0 or dc_block_voltage_v > 0:
        equipment_list = dict(equipment_list)
        if project_hz > 0:
            equipment_list.setdefault("project_hz", project_hz)
        if dc_block_voltage_v > 0:
            equipment_list.setdefault("dc_block_voltage_v", dc_block_voltage_v)

    layout_params = {
        "svg_width": _safe_float(sld_inputs.get("svg_width"), 1750),
        "svg_height": _safe_float(sld_inputs.get("svg_height"), 900),
        "left_margin": _safe_float(sld_inputs.get("left_margin"), 40),
        "top_margin": _safe_float(sld_inputs.get("top_margin"), 40),
        "column_width": _safe_float(sld_inputs.get("column_width"), 420),
        "row_height": _safe_float(sld_inputs.get("row_height"), 16),
        "pcs_gap": _safe_float(sld_inputs.get("pcs_gap"), 60),
        "busbar_gap": _safe_float(sld_inputs.get("busbar_gap"), 22),
        "font_scale": _safe_float(sld_inputs.get("font_scale"), 1.0),
        "compact_mode": bool(sld_inputs.get("compact_mode")),
        "theme": str(sld_inputs.get("theme") or "light"),
    }
    if sld_inputs.get("draw_summary") is not None:
        layout_params["draw_summary"] = bool(sld_inputs.get("draw_summary"))

    return SldGroupSpec(
        group_index=group_index,
        mv_voltage_kv=mv_kv,
        lv_voltage_v_ll=lv_v,
        transformer_mva=transformer_mva,
        transformer_vector_group=sld_inputs.get("transformer", {}).get("vector_group"),
        transformer_uk_percent=sld_inputs.get("transformer", {}).get("uk_percent"),
        pcs_count=pcs_count,
        pcs_rating_kw_list=pcs_rating_kw_list,
        dc_block_energy_mwh=dc_block_energy_mwh,
        dc_blocks_total_in_group=dc_blocks_total_in_group,
        dc_blocks_per_feeder=dc_blocks_per_feeder,
        equipment_list=equipment_list,
        layout_params=layout_params,
    )


def build_layout_block_spec(
    ac_output: dict,
    block_indices_to_render: List[int],
    labels: Optional[Dict[str, str]] = None,
    pcs_count: int = 4,
    dc_blocks_per_block: int = 4,
    dc_block_counts_by_block: Optional[Dict[int, int]] = None,
    arrangement: str = "2x2",
    show_skid: bool = True,
    container_length_mm: int = 6058,
    container_width_mm: int = 2438,
    dc_to_dc_clearance_m: Optional[float] = None,
    dc_to_ac_clearance_m: Optional[float] = None,
    perimeter_clearance_m: Optional[float] = None,
    dc_block_mirrored: bool = False,
    use_template: bool = False,
    dc_block_svg_path: Optional[str] = None,
    ac_block_svg_path: Optional[str] = None,
    scale: float = 0.04,
    left_margin: int = 40,
    top_margin: int = 40,
    theme: str = "light",
) -> LayoutBlockSpec:
    block_indices = block_indices_to_render or [1]
    normalized = []
    for idx in block_indices:
        value = _safe_int(idx, 0)
        if value > 0:
            normalized.append(value)
    if not normalized:
        normalized = [1]

    output_labels = labels or {}
    if not isinstance(output_labels, dict):
        output_labels = {}

    normalized_counts: Dict[int, int] = {}
    if isinstance(dc_block_counts_by_block, dict):
        for key, value in dc_block_counts_by_block.items():
            idx = _safe_int(key, 0)
            if idx > 0:
                normalized_counts[idx] = max(0, _safe_int(value, 0))

    return LayoutBlockSpec(
        block_indices_to_render=normalized,
        pcs_count=int(pcs_count),
        dc_blocks_per_block=int(dc_blocks_per_block),
        dc_block_counts_by_block=normalized_counts,
        arrangement=arrangement,
        show_skid=bool(show_skid),
        labels=output_labels,
        container_length_mm=int(container_length_mm),
        container_width_mm=int(container_width_mm),
        dc_to_dc_clearance_m=dc_to_dc_clearance_m,
        dc_to_ac_clearance_m=dc_to_ac_clearance_m,
        perimeter_clearance_m=perimeter_clearance_m,
        dc_block_mirrored=bool(dc_block_mirrored),
        use_template=bool(use_template),
        dc_block_svg_path=dc_block_svg_path,
        ac_block_svg_path=ac_block_svg_path,
        scale=scale,
        left_margin=left_margin,
        top_margin=top_margin,
        theme=str(theme or "light"),
    )
