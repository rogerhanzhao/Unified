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
    text = f"{v:.2f}".rstrip("0").rstrip(".")
    return f"{text} kV"


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
    counts = []
    entries = snapshot.get("dc_blocks_by_feeder", []) or []
    by_id = {entry.get("feeder_id"): entry for entry in entries if isinstance(entry, dict)}
    for idx in range(1, 5):
        feeder_id = f"FDR-{idx:02d}"
        entry = by_id.get(feeder_id, {})
        counts.append(int(_safe_float(entry.get("dc_block_count"), 0.0)))
    return counts, sum(counts)


def _build_equipment_list(snapshot: dict) -> List[Tuple[str, str]]:
    inputs = snapshot.get("electrical_inputs", {}) or {}
    rmu = inputs.get("rmu", {}) or {}
    transformer = snapshot.get("transformer", {}) or {}
    tr_inputs = inputs.get("transformer", {}) or {}
    lv_bus = inputs.get("lv_busbar", {}) or {}
    cables = inputs.get("cables", {}) or {}
    dc_fuse = inputs.get("dc_fuse", {}) or {}

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

    items.append(("MV Cable", cables.get("mv_cable_spec") or "TBD"))
    items.append(("LV Cable", cables.get("lv_cable_spec") or "TBD"))
    items.append(("DC Cable", cables.get("dc_cable_spec") or "TBD"))
    items.append(("DC Fuse", dc_fuse.get("fuse_spec") or "TBD"))

    return items


def render_jp_pro_svg(snapshot: dict, out_svg: Path) -> None:
    out_svg = Path(out_svg)

    width = 1400
    height = 900
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
svg { font-family: Arial, Helvetica, sans-serif; font-size: 12px; }
.outline { stroke: #000000; stroke-width: 1.2; fill: none; }
.thin { stroke: #000000; stroke-width: 1; fill: none; }
.dash { stroke: #000000; stroke-width: 1.2; fill: none; stroke-dasharray: 6,4; }
.label { fill: #000000; }
.title { font-size: 13px; font-weight: bold; }
"""

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
    skid_label.text = "PCS&MV Skid (AC Block)"

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
        attrib={"x1": str(bus_x1), "y1": str(bus_y), "x2": str(bus_x2), "y2": str(bus_y), "class": "outline"},
    )
    bus_text = ET.SubElement(
        root,
        "text",
        attrib={"x": str(bus_x1), "y": str(bus_y - 8), "class": "label"},
    )
    bus_text.text = "LV Bus"

    pcs_count = 4
    pcs_box_w = 150
    pcs_box_h = 52
    pcs_gap = 24
    pcs_total = pcs_count * pcs_box_w + (pcs_count - 1) * pcs_gap
    pcs_start_x = skid_x + (skid_w - pcs_total) / 2
    pcs_y = bus_y + 25
    pcs_rating = _safe_float(snapshot.get("ac_block", {}).get("pcs_rating_each_kva"), 0.0)

    for idx in range(pcs_count):
        x = pcs_start_x + idx * (pcs_box_w + pcs_gap)
        ET.SubElement(
            root,
            "rect",
            attrib={"x": str(x), "y": str(pcs_y), "width": str(pcs_box_w), "height": str(pcs_box_h), "class": "outline"},
        )
        pcs_label = ET.SubElement(
            root,
            "text",
            attrib={"x": str(x + 8), "y": str(pcs_y + 20), "class": "label"},
        )
        pcs_label.text = f"PCS{idx + 1}"
        pcs_rating_text = ET.SubElement(
            root,
            "text",
            attrib={"x": str(x + 8), "y": str(pcs_y + 38), "class": "label"},
        )
        pcs_rating_text.text = f"{pcs_rating:.0f} kVA" if pcs_rating else "TBD"

        ET.SubElement(
            root,
            "line",
            attrib={"x1": str(x + pcs_box_w / 2), "y1": str(bus_y), "x2": str(x + pcs_box_w / 2), "y2": str(pcs_y), "class": "thin"},
        )

    diagram_scope = snapshot.get("diagram_scope") or "one_ac_block_group"
    battery_energy = _per_block_energy(snapshot)
    battery_energy_text = format_mwh(battery_energy)

    battery_box_w = 260
    battery_box_h = 60
    battery_box_x = skid_x + (skid_w - battery_box_w) / 2
    battery_box_y = skid_y + skid_h + 40

    if diagram_scope == "one_ac_block_group":
        ET.SubElement(
            root,
            "rect",
            attrib={
                "x": str(battery_box_x),
                "y": str(battery_box_y),
                "width": str(battery_box_w),
                "height": str(battery_box_h),
                "class": "outline",
            },
        )
        bu_label = ET.SubElement(
            root,
            "text",
            attrib={"x": str(battery_box_x + 10), "y": str(battery_box_y + 24), "class": "label"},
        )
        bu_label.text = "Battery Unit (Representative)"
        bu_energy = ET.SubElement(
            root,
            "text",
            attrib={"x": str(battery_box_x + 10), "y": str(battery_box_y + 44), "class": "label"},
        )
        bu_energy.text = battery_energy_text
    else:
        for idx in range(pcs_count):
            x = pcs_start_x + idx * (pcs_box_w + pcs_gap)
            y = battery_box_y
            ET.SubElement(
                root,
                "rect",
                attrib={
                    "x": str(x),
                    "y": str(y),
                    "width": str(pcs_box_w),
                    "height": str(pcs_box_h),
                    "class": "outline",
                },
            )
            bu_label = ET.SubElement(
                root,
                "text",
                attrib={"x": str(x + 8), "y": str(y + 24), "class": "label"},
            )
            bu_label.text = "Battery Unit"
            bu_energy = ET.SubElement(
                root,
                "text",
                attrib={"x": str(x + 8), "y": str(y + 44), "class": "label"},
            )
            bu_energy.text = battery_energy_text

    if diagram_scope == "one_ac_block_group":
        counts, total_counts = _allocation_counts(snapshot)
        total_override = int(_safe_float(snapshot.get("dc_blocks_for_one_ac_block_group"), 0.0))
        if total_override > 0:
            total_counts = total_override
        allocation_text = (
            f"Allocation by feeder: F1={counts[0]}, F2={counts[1]}, "
            f"F3={counts[2]}, F4={counts[3]}"
        )

        note_w = 360
        note_h = 120
        note_x = diagram_right - note_w
        note_y = battery_box_y + battery_box_h + 30
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
        lines = [
            "DC Block Allocation (for this AC Block group)",
            f"DC Block ({battery_energy_text} each): total = {total_counts}",
            allocation_text,
            "Note: Counts indicate configuration allocation, not series/daisy-chain wiring.",
        ]
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
