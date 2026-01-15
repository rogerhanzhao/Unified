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

import math
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Tuple


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def format_mva(value, round_to_standard=False) -> str:
    v = _safe_float(value, 0.0)
    if v <= 0:
        return "TBD"
    if round_to_standard:
        v = round(v)
    return f"{v:.1f} MVA"


def format_kv(value) -> str:
    v = _safe_float(value, 0.0)
    if v <= 0:
        return "TBD"
    return f"{v:.1f} kV"


def format_v(value) -> str:
    v = _safe_float(value, 0.0)
    if v <= 0:
        return "TBD"
    return f"{v:.0f} V"


def format_percent(value) -> str:
    v = _safe_float(value, 0.0)
    if v <= 0:
        return "TBD"
    return f"{v:.1f}%"


def format_mwh(value) -> str:
    v = _safe_float(value, 0.0)
    if v <= 0:
        return "TBD"
    return f"{v:.3f} MWh"


def _per_block_energy(snapshot: dict) -> float:
    energy = _safe_float(snapshot.get("dc_block_energy_mwh"), 0.0)
    if energy > 0:
        return energy
    for entry in snapshot.get("dc_blocks_by_feeder", []) or []:
        count = _safe_float(entry.get("dc_block_count"), 0.0)
        energy_total = _safe_float(entry.get("dc_block_energy_mwh"), 0.0)
        if count > 0 and energy_total > 0:
            return energy_total / count
    return 0.0


def _allocation_counts(snapshot: dict) -> Tuple[List[int], int]:
    entries = snapshot.get("dc_blocks_by_feeder", []) or []
    by_id = {entry.get("feeder_id"): entry for entry in entries if isinstance(entry, dict)}
    feeders = snapshot.get("feeders", []) or []
    pcs_count = _safe_float(snapshot.get("ac_block", {}).get("pcs_count"), 0.0)
    count = len(feeders) if feeders else int(pcs_count)
    counts = []
    for idx in range(count):
        feeder_id = (
            feeders[idx].get("feeder_id")
            if idx < len(feeders) and isinstance(feeders[idx], dict)
            else f"FDR-{idx + 1:02d}"
        )
        entry = by_id.get(feeder_id, {})
        counts.append(int(_safe_float(entry.get("dc_block_count"), 0.0)))
    return counts, sum(counts)


def _split_pcs_groups(pcs_count: int) -> Tuple[List[int], List[int]]:
    if pcs_count <= 0:
        return [], []
    split = int(math.ceil(pcs_count / 2))
    return list(range(1, split + 1)), list(range(split + 1, pcs_count + 1))


def _build_equipment_list(snapshot: dict) -> List[Tuple[str, str]]:
    inputs = snapshot.get("electrical_inputs", {}) or {}
    rmu = inputs.get("rmu", {}) or {}
    transformer = snapshot.get("transformer", {}) or {}
    tr_inputs = inputs.get("transformer", {}) or {}
    lv_bus = inputs.get("lv_busbar", {}) or {}
    cables = inputs.get("cables", {}) or {}
    dc_fuse = inputs.get("dc_fuse", {}) or {}
    ac_block = snapshot.get("ac_block", {}) or {}

    items = []

    rmu_parts = []
    if rmu.get("rated_kv"):
        rmu_parts.append(format_kv(rmu.get("rated_kv")))
    if rmu.get("rated_a"):
        rmu_parts.append(f"{_safe_float(rmu.get('rated_a'), 0.0):.0f} A")
    if rmu.get("short_circuit_ka_3s"):
        rmu_parts.append(f"{_safe_float(rmu.get('short_circuit_ka_3s'), 0.0):.1f} kA/3s")
    if rmu.get("ct_ratio"):
        rmu_parts.append(f"CT {rmu.get('ct_ratio')}")
    if rmu.get("ct_class"):
        rmu_parts.append(str(rmu.get("ct_class")))
    if rmu.get("ct_va"):
        rmu_parts.append(f"{_safe_float(rmu.get('ct_va'), 0.0):.0f} VA")
    items.append(("RMU", ", ".join(rmu_parts) if rmu_parts else "TBD"))

    tr_parts = []
    rated_mva = transformer.get("rated_mva")
    if rated_mva:
        tr_parts.append(format_mva(rated_mva))
    hv_kv = transformer.get("hv_kv")
    lv_v = transformer.get("lv_v")
    if hv_kv and lv_v:
        tr_parts.append(f"{format_kv(hv_kv)}/{format_v(lv_v)}")
    if tr_inputs.get("vector_group"):
        tr_parts.append(str(tr_inputs.get("vector_group")))
    if tr_inputs.get("uk_percent"):
        tr_parts.append(f"Uk={format_percent(tr_inputs.get('uk_percent'))}")
    if tr_inputs.get("tap_range"):
        tr_parts.append(str(tr_inputs.get("tap_range")))
    if tr_inputs.get("cooling"):
        tr_parts.append(str(tr_inputs.get("cooling")))
    items.append(("Transformer", ", ".join(tr_parts) if tr_parts else "TBD"))

    lv_parts = []
    if lv_bus.get("rated_a"):
        lv_parts.append(f"{_safe_float(lv_bus.get('rated_a'), 0.0):.0f} A")
    if lv_bus.get("short_circuit_ka"):
        lv_parts.append(f"{_safe_float(lv_bus.get('short_circuit_ka'), 0.0):.1f} kA")
    items.append(("LV Busbar", ", ".join(lv_parts) if lv_parts else "TBD"))

    pcs_count = int(_safe_float(ac_block.get("pcs_count"), 0.0))
    if pcs_count <= 0:
        pcs_count = len(snapshot.get("feeders", []) or []) or 1
    pcs_rating_each = _safe_float(ac_block.get("pcs_rating_each_kva"), 0.0)
    if pcs_rating_each <= 0:
        pcs_rating_each = _safe_float(ac_block.get("pcs_rating_each_kw"), 0.0)
    pcs_spec = "TBD"
    if pcs_rating_each > 0 and pcs_count > 0:
        pcs_spec = f"{pcs_rating_each:.0f} kVA x {pcs_count}"
    items.append(("PCS", pcs_spec))

    items.append(("MV Cable", cables.get("mv_cable_spec") or "TBD"))
    items.append(("LV Cable", cables.get("lv_cable_spec") or "TBD"))
    items.append(("DC Cable", cables.get("dc_cable_spec") or "TBD"))
    items.append(("DC Fuse", dc_fuse.get("fuse_spec") or "TBD"))

    counts, total_counts = _allocation_counts(snapshot)
    if counts:
        allocation_parts = [f"F{idx + 1}={counts[idx]}" for idx in range(len(counts))]
        items.append(("DC Block Allocation", ", ".join(allocation_parts)))
        items.append(("DC Blocks Total (this group)", f"{total_counts}"))

    return items


def render_jp_pro_svg(snapshot: dict, out_svg: Path) -> None:
    out_svg = Path(out_svg)

    width = int(_safe_float(snapshot.get("svg_width"), 1400))
    height = int(_safe_float(snapshot.get("svg_height"), 900))
    left_margin = 40
    left_col_width = 320
    diagram_left = left_margin + left_col_width + 40
    diagram_right = width - 40
    diagram_width = diagram_right - diagram_left

    root = ET.Element(
        "svg",
        attrib={
            "xmlns": "http://www.w3.org/2000/svg",
            "width": str(width),
            "height": str(height),
            "viewBox": f"0 0 {width} {height}",
        },
    )
    style = ET.SubElement(root, "style")
    style.text = """
svg { font-family: Arial, 'DejaVu Sans', sans-serif; font-size: 11px; }
.outline { stroke: #000000; stroke-width: 1.2; fill: none; }
.thin { stroke: #000000; stroke-width: 1; fill: none; }
.thick { stroke: #000000; stroke-width: 2; fill: none; }
.dash { stroke: #000000; stroke-width: 1.2; fill: none; stroke-dasharray: 6,4; }
.label { fill: #000000; }
.title { font-size: 12px; font-weight: bold; }
.small { font-size: 10px; }
"""
    ET.SubElement(
        root,
        "rect",
        attrib={"x": "0", "y": "0", "width": "100%", "height": "100%", "fill": "#ffffff"},
    )

    table_x = left_margin
    table_y = 40
    table_w = left_col_width
    row_h = 18
    header_h = 22
    items = _build_equipment_list(snapshot)
    table_h = header_h + row_h * (len(items) + 1)

    ET.SubElement(
        root,
        "rect",
        attrib={
            "x": str(table_x),
            "y": str(table_y),
            "width": str(table_w),
            "height": str(table_h),
            "class": "outline",
        },
    )
    col_split = table_x + 120
    ET.SubElement(
        root,
        "line",
        attrib={
            "x1": str(col_split),
            "y1": str(table_y),
            "x2": str(col_split),
            "y2": str(table_y + table_h),
            "class": "thin",
        },
    )
    ET.SubElement(
        root,
        "line",
        attrib={
            "x1": str(table_x),
            "y1": str(table_y + header_h),
            "x2": str(table_x + table_w),
            "y2": str(table_y + header_h),
            "class": "thin",
        },
    )
    title = ET.SubElement(
        root,
        "text",
        attrib={"x": str(table_x + 6), "y": str(table_y + 15), "class": "label title"},
    )
    title.text = "Equipment List"
    head_item = ET.SubElement(
        root,
        "text",
        attrib={"x": str(table_x + 6), "y": str(table_y + header_h + 14), "class": "label"},
    )
    head_item.text = "Item"
    head_spec = ET.SubElement(
        root,
        "text",
        attrib={"x": str(col_split + 6), "y": str(table_y + header_h + 14), "class": "label"},
    )
    head_spec.text = "Spec"

    for idx, (item, spec) in enumerate(items, start=1):
        y = table_y + header_h + row_h * idx + 14
        t_item = ET.SubElement(
            root, "text", attrib={"x": str(table_x + 6), "y": str(y), "class": "label"}
        )
        t_item.text = item
        t_spec = ET.SubElement(
            root, "text", attrib={"x": str(col_split + 6), "y": str(y), "class": "label"}
        )
        t_spec.text = spec

    skid_x = diagram_left
    skid_y = 40
    skid_w = diagram_width
    skid_h = 420

    ET.SubElement(
        root,
        "rect",
        attrib={
            "x": str(skid_x),
            "y": str(skid_y),
            "width": str(skid_w),
            "height": str(skid_h),
            "class": "dash",
        },
    )
    skid_label = ET.SubElement(
        root,
        "text",
        attrib={"x": str(skid_x + 8), "y": str(skid_y + 18), "class": "label title"},
    )
    skid_label.text = "PCS&MVT SKID (AC Block)"

    mv_labels = snapshot.get("mv", {}).get("labels", {}) if isinstance(snapshot.get("mv"), dict) else {}
    mv_kv = _safe_float(snapshot.get("mv", {}).get("kv"), 0.0)
    to_switchgear = mv_labels.get("to_switchgear") or (
        f"To {format_kv(mv_kv)} Switchgear" if mv_kv > 0 else "To Switchgear"
    )
    to_other_rmu = mv_labels.get("to_other_rmu") or "To Other RMU"

    terminal_y = skid_y + 50
    terminal_left_x = skid_x + 60
    terminal_right_x = skid_x + skid_w - 60
    ET.SubElement(
        root,
        "text",
        attrib={"x": str(terminal_left_x - 10), "y": str(terminal_y - 10), "class": "label"},
    ).text = to_switchgear
    ET.SubElement(
        root,
        "text",
        attrib={
            "x": str(terminal_right_x + 10),
            "y": str(terminal_y - 10),
            "class": "label",
            "text-anchor": "end",
        },
    ).text = to_other_rmu
    ET.SubElement(
        root,
        "line",
        attrib={
            "x1": str(terminal_left_x),
            "y1": str(terminal_y),
            "x2": str(terminal_left_x),
            "y2": str(terminal_y + 20),
            "class": "thin",
        },
    )
    ET.SubElement(
        root,
        "line",
        attrib={
            "x1": str(terminal_right_x),
            "y1": str(terminal_y),
            "x2": str(terminal_right_x),
            "y2": str(terminal_y + 20),
            "class": "thin",
        },
    )

    rmu_label = ET.SubElement(
        root,
        "text",
        attrib={"x": str(skid_x + 20), "y": str(skid_y + 60), "class": "label"},
    )
    rmu_label.text = "RMU: LBS x2 / GCB / DS"

    tr_w = 140
    tr_h = 60
    tr_x = skid_x + skid_w / 2 - tr_w / 2
    tr_y = skid_y + 120
    ET.SubElement(
        root,
        "rect",
        attrib={
            "x": str(tr_x),
            "y": str(tr_y),
            "width": str(tr_w),
            "height": str(tr_h),
            "class": "outline",
        },
    )
    tr_title = ET.SubElement(
        root,
        "text",
        attrib={"x": str(tr_x), "y": str(tr_y - 8), "class": "label"},
    )
    tr_title.text = "Transformer"

    hv_kv = _safe_float(snapshot.get("transformer", {}).get("hv_kv"), 0.0)
    lv_v = _safe_float(snapshot.get("transformer", {}).get("lv_v"), 0.0)
    rated_mva = _safe_float(snapshot.get("transformer", {}).get("rated_mva"), 0.0)
    uk_percent = snapshot.get("electrical_inputs", {}).get("transformer", {}).get("uk_percent")
    vector_group = snapshot.get("electrical_inputs", {}).get("transformer", {}).get("vector_group")
    cooling = snapshot.get("electrical_inputs", {}).get("transformer", {}).get("cooling")

    tr_lines = [
        f"{format_kv(hv_kv)}/{format_v(lv_v)}",
        format_mva(rated_mva),
    ]
    if uk_percent:
        tr_lines.append(f"Uk={format_percent(uk_percent)}")
    if vector_group:
        tr_lines.append(str(vector_group))
    if cooling:
        tr_lines.append(str(cooling))

    tr_text_x = tr_x + tr_w + 12
    tr_text_y = tr_y + 18
    for idx, line in enumerate(tr_lines):
        text = ET.SubElement(
            root,
            "text",
            attrib={"x": str(tr_text_x), "y": str(tr_text_y + idx * 16), "class": "label"},
        )
        text.text = line

    bus_y = tr_y + 120
    bus_x1 = skid_x + 80
    bus_x2 = skid_x + skid_w - 80
    ET.SubElement(
        root,
        "line",
        attrib={"x1": str(bus_x1), "y1": str(bus_y), "x2": str(bus_x2), "y2": str(bus_y), "class": "thick"},
    )
    bus_text = ET.SubElement(
        root,
        "text",
        attrib={"x": str(bus_x1), "y": str(bus_y - 8), "class": "label"},
    )
    bus_text.text = "LV Busbar"

    ac_block = snapshot.get("ac_block", {}) or {}
    feeders = snapshot.get("feeders", []) or []
    pcs_count = int(_safe_float(ac_block.get("pcs_count"), 0.0))
    if pcs_count <= 0:
        pcs_count = len(feeders) if feeders else 1
    group_a, group_b = _split_pcs_groups(pcs_count)
    group_split = len(group_a)

    pcs_rating_list = ac_block.get("pcs_rating_kva_list")
    if not isinstance(pcs_rating_list, list) or len(pcs_rating_list) != pcs_count:
        if feeders:
            pcs_rating_list = [
                _safe_float(entry.get("pcs_rating_kva"), 0.0)
                for entry in feeders
                if isinstance(entry, dict)
            ]
        else:
            pcs_rating_each = _safe_float(ac_block.get("pcs_rating_each_kva"), 0.0)
            pcs_rating_list = [pcs_rating_each for _ in range(pcs_count)]
    if len(pcs_rating_list) < pcs_count:
        pad = pcs_count - len(pcs_rating_list)
        pcs_rating_list.extend([pcs_rating_list[-1] if pcs_rating_list else 0.0] * pad)

    pcs_box_h = 52
    pcs_pad = 60
    available = max(200.0, skid_w - pcs_pad * 2)
    slot_w = available / pcs_count if pcs_count else available
    pcs_box_w = min(160.0, max(110.0, slot_w - 10.0))
    pcs_start_x = skid_x + pcs_pad + (slot_w - pcs_box_w) / 2
    pcs_y = bus_y + 25

    for idx in range(pcs_count):
        x = pcs_start_x + idx * slot_w
        ET.SubElement(
            root,
            "rect",
            attrib={
                "x": str(x),
                "y": str(pcs_y),
                "width": str(pcs_box_w),
                "height": str(pcs_box_h),
                "class": "outline",
            },
        )
        pcs_label = ET.SubElement(
            root,
            "text",
            attrib={"x": str(x + 8), "y": str(pcs_y + 20), "class": "label"},
        )
        pcs_label.text = f"PCS-{idx + 1}"
        pcs_rating_text = ET.SubElement(
            root,
            "text",
            attrib={"x": str(x + 8), "y": str(pcs_y + 38), "class": "label"},
        )
        pcs_rating = pcs_rating_list[idx] if idx < len(pcs_rating_list) else 0.0
        pcs_rating_text.text = f"{pcs_rating:.0f} kVA" if pcs_rating else "TBD"

        ET.SubElement(
            root,
            "line",
            attrib={
                "x1": str(x + pcs_box_w / 2),
                "y1": str(bus_y),
                "x2": str(x + pcs_box_w / 2),
                "y2": str(pcs_y),
                "class": "thin",
            },
        )

    dc_bus_a_y = pcs_y + pcs_box_h + 28
    dc_bus_gap = 22
    dc_bus_b_y = dc_bus_a_y + dc_bus_gap
    ET.SubElement(
        root,
        "line",
        attrib={"x1": str(bus_x1), "y1": str(dc_bus_a_y), "x2": str(bus_x2), "y2": str(dc_bus_a_y), "class": "thick"},
    )
    ET.SubElement(
        root,
        "text",
        attrib={"x": str(bus_x1), "y": str(dc_bus_a_y - 8), "class": "label"},
    ).text = "DC BUSBAR A"
    ET.SubElement(
        root,
        "line",
        attrib={"x1": str(bus_x1), "y1": str(dc_bus_b_y), "x2": str(bus_x2), "y2": str(dc_bus_b_y), "class": "thick"},
    )
    ET.SubElement(
        root,
        "text",
        attrib={"x": str(bus_x1), "y": str(dc_bus_b_y - 8), "class": "label"},
    ).text = "DC BUSBAR B"

    fuse_h = 10
    fuse_w = 18
    for idx in range(pcs_count):
        x = pcs_start_x + idx * slot_w
        line_x = x + pcs_box_w / 2
        target_bus_y = dc_bus_a_y if idx < group_split else dc_bus_b_y
        ET.SubElement(
            root,
            "line",
            attrib={
                "x1": str(line_x),
                "y1": str(pcs_y + pcs_box_h),
                "x2": str(line_x),
                "y2": str(target_bus_y),
                "class": "thin",
            },
        )
        fuse_y = (pcs_y + pcs_box_h + target_bus_y) / 2 - fuse_h / 2
        ET.SubElement(
            root,
            "rect",
            attrib={
                "x": str(line_x - fuse_w / 2),
                "y": str(fuse_y),
                "width": str(fuse_w),
                "height": str(fuse_h),
                "class": "outline",
            },
        )

    battery_energy = _per_block_energy(snapshot)
    battery_energy_text = format_mwh(battery_energy)

    counts, total_counts = _allocation_counts(snapshot)
    if len(counts) < pcs_count:
        counts.extend([0 for _ in range(pcs_count - len(counts))])
    total_override = int(_safe_float(snapshot.get("dc_blocks_for_one_ac_block_group"), 0.0))
    if total_override > 0:
        total_counts = total_override

    battery_y = dc_bus_b_y + 40
    battery_title_h = 18
    circuit_pad = 16
    circuit_gap = 18
    dc_circuit_a_y = battery_y + battery_title_h + circuit_pad
    dc_circuit_b_y = dc_circuit_a_y + circuit_gap
    dc_box_h = 54

    battery_x = skid_x + 20
    battery_w = skid_w - 40
    show_individual_blocks = 0 < total_counts <= 6
    blocks_to_draw = total_counts if show_individual_blocks else 1
    block_cols = min(3, blocks_to_draw) if show_individual_blocks else 1
    block_rows = int(math.ceil(blocks_to_draw / block_cols)) if show_individual_blocks else 1
    block_gap_x = 20
    block_gap_y = 16
    block_area_w = max(200.0, battery_w - 80.0)
    dc_box_w = min(
        160.0,
        max(110.0, (block_area_w - (block_cols - 1) * block_gap_x) / block_cols),
    )
    block_grid_w = block_cols * dc_box_w + max(0, block_cols - 1) * block_gap_x
    block_grid_h = block_rows * dc_box_h + max(0, block_rows - 1) * block_gap_y
    dc_box_x_start = battery_x + (battery_w - block_grid_w) / 2
    dc_box_y = dc_circuit_b_y + 24
    battery_note_y = dc_box_y + block_grid_h + 18
    battery_h = max(battery_title_h + 80.0, battery_note_y - battery_y + 24)

    ET.SubElement(
        root,
        "rect",
        attrib={
            "x": str(battery_x),
            "y": str(battery_y),
            "width": str(battery_w),
            "height": str(battery_h),
            "class": "dash",
        },
    )
    ET.SubElement(
        root,
        "text",
        attrib={"x": str(battery_x + 8), "y": str(battery_y + 16), "class": "label title"},
    ).text = "Battery Storage Bank"

    circuit_x1 = battery_x + 60
    circuit_x2 = battery_x + battery_w - 60
    ET.SubElement(
        root,
        "line",
        attrib={
            "x1": str(circuit_x1),
            "y1": str(dc_circuit_a_y),
            "x2": str(circuit_x2),
            "y2": str(dc_circuit_a_y),
            "class": "thin",
        },
    )
    ET.SubElement(
        root,
        "text",
        attrib={"x": str(circuit_x1), "y": str(dc_circuit_a_y - 6), "class": "small"},
    ).text = "Circuit A"
    ET.SubElement(
        root,
        "line",
        attrib={
            "x1": str(circuit_x1),
            "y1": str(dc_circuit_b_y),
            "x2": str(circuit_x2),
            "y2": str(dc_circuit_b_y),
            "class": "thin",
        },
    )
    ET.SubElement(
        root,
        "text",
        attrib={"x": str(circuit_x1), "y": str(dc_circuit_b_y - 6), "class": "small"},
    ).text = "Circuit B"

    link_x = bus_x2 - 40
    ET.SubElement(
        root,
        "line",
        attrib={"x1": str(link_x), "y1": str(dc_bus_a_y), "x2": str(link_x), "y2": str(dc_circuit_a_y), "class": "thin"},
    )
    ET.SubElement(
        root,
        "line",
        attrib={"x1": str(link_x), "y1": str(dc_bus_b_y), "x2": str(link_x), "y2": str(dc_circuit_b_y), "class": "thin"},
    )

    block_index = 0
    for row in range(block_rows):
        for col in range(block_cols):
            if show_individual_blocks and block_index >= total_counts:
                break
            cell_x = dc_box_x_start + col * (dc_box_w + block_gap_x)
            cell_y = dc_box_y + row * (dc_box_h + block_gap_y)
            ET.SubElement(
                root,
                "rect",
                attrib={
                    "x": str(cell_x),
                    "y": str(cell_y),
                    "width": str(dc_box_w),
                    "height": str(dc_box_h),
                    "class": "outline",
                },
            )
            if show_individual_blocks:
                label = f"DC Block #{block_index + 1} ({battery_energy_text})"
            else:
                label = f"DC Block Group ({battery_energy_text} each) x {total_counts}"
            ET.SubElement(
                root,
                "text",
                attrib={"x": str(cell_x + 6), "y": str(cell_y + 20), "class": "small"},
            ).text = label
            ET.SubElement(
                root,
                "text",
                attrib={"x": str(cell_x + 6), "y": str(cell_y + 38), "class": "small"},
            ).text = "2 circuits (A/B)"

            line_x_a = cell_x + dc_box_w * 0.4
            line_x_b = cell_x + dc_box_w * 0.6
            ET.SubElement(
                root,
                "line",
                attrib={
                    "x1": str(line_x_a),
                    "y1": str(cell_y),
                    "x2": str(line_x_a),
                    "y2": str(dc_circuit_a_y),
                    "class": "thin",
                },
            )
            ET.SubElement(
                root,
                "line",
                attrib={
                    "x1": str(line_x_b),
                    "y1": str(cell_y),
                    "x2": str(line_x_b),
                    "y2": str(dc_circuit_b_y),
                    "class": "thin",
                },
            )

            block_index += 1
        if show_individual_blocks and block_index >= total_counts:
            break

    ET.SubElement(
        root,
        "text",
        attrib={"x": str(battery_x + 8), "y": str(battery_note_y), "class": "small"},
    ).text = "Each DC block provides Circuit A and Circuit B."

    alloc_parts = [f"F{idx + 1}={counts[idx]}" for idx in range(pcs_count)]
    allocation_text = "DC Block Allocation: " + ", ".join(alloc_parts)
    group_a_text = ", ".join([f"F{idx + 1}={counts[idx]}" for idx in range(group_split)]) or "None"
    group_b_text = (
        ", ".join([f"F{idx + 1}={counts[idx]}" for idx in range(group_split, pcs_count)]) or "None"
    )

    group_index = int(_safe_float(snapshot.get("group_index") or ac_block.get("group_index"), 1.0))
    if group_index < 1:
        group_index = 1

    note_w = 420
    note_x = diagram_right - note_w
    note_y = battery_y + battery_h + 24
    lines = [
        "DC Block Allocation (for this AC Block group)",
        f"Group Summary: AC Block Group {group_index}: PCS = {pcs_count}, DC Blocks Total = {total_counts}",
        f"Group A feeders: {group_a_text} (total {sum(counts[:group_split])})",
        f"Group B feeders: {group_b_text} (total {sum(counts[group_split:])})",
        f"DC Block Group ({battery_energy_text} each)",
        allocation_text,
        "Counts indicate allocation for sizing/configuration; detailed DC wiring is not represented.",
    ]
    note_h = 24 + len(lines) * 18
    ET.SubElement(
        root,
        "rect",
        attrib={
            "x": str(note_x),
            "y": str(note_y),
            "width": str(note_w),
            "height": str(note_h),
            "class": "outline",
        },
    )
    for idx, line in enumerate(lines):
        text = ET.SubElement(
            root,
            "text",
            attrib={
                "x": str(note_x + 8),
                "y": str(note_y + 20 + idx * 18),
                "class": "label",
            },
        )
        text.text = line

    out_svg.parent.mkdir(parents=True, exist_ok=True)
    tree = ET.ElementTree(root)
    tree.write(out_svg, encoding="utf-8", xml_declaration=True)
