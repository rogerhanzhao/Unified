import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Tuple


def _format_lv_voltage(lv_v: float) -> str:
    if lv_v <= 0:
        return "TBD"
    if lv_v < 20:
        return f"{lv_v:g}kV"
    return f"{lv_v:g}V"


def _format_hv_voltage(hv_kv: float) -> str:
    if hv_kv <= 0:
        return "TBD"
    return f"{hv_kv:g}kV"


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


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
        rmu_parts.append(f"{rmu.get('rated_kv')} kV")
    if rmu.get("rated_a"):
        rmu_parts.append(f"{rmu.get('rated_a')} A")
    if rmu.get("short_circuit_ka_3s"):
        rmu_parts.append(f"{rmu.get('short_circuit_ka_3s')} kA/3s")
    if rmu.get("ct_ratio"):
        rmu_parts.append(f"CT {rmu.get('ct_ratio')}")
    if rmu.get("ct_class"):
        rmu_parts.append(str(rmu.get("ct_class")))
    if rmu.get("ct_va"):
        rmu_parts.append(f"{rmu.get('ct_va')} VA")
    items.append(("RMU", ", ".join(rmu_parts) if rmu_parts else "TBD"))

    tr_parts = []
    rated_mva = transformer.get("rated_mva")
    if rated_mva:
        tr_parts.append(f"{rated_mva} MVA")
    hv_kv = transformer.get("hv_kv")
    lv_v = transformer.get("lv_v")
    if hv_kv and lv_v:
        tr_parts.append(f"{_format_hv_voltage(hv_kv)}/{_format_lv_voltage(lv_v)}")
    if tr_inputs.get("vector_group"):
        tr_parts.append(str(tr_inputs.get("vector_group")))
    if tr_inputs.get("uk_percent"):
        tr_parts.append(f"Uk={tr_inputs.get('uk_percent')}%")
    if tr_inputs.get("tap_range"):
        tr_parts.append(str(tr_inputs.get("tap_range")))
    if tr_inputs.get("cooling"):
        tr_parts.append(str(tr_inputs.get("cooling")))
    items.append(("Transformer", ", ".join(tr_parts) if tr_parts else "TBD"))

    lv_parts = []
    if lv_bus.get("rated_a"):
        lv_parts.append(f"{lv_bus.get('rated_a')} A")
    if lv_bus.get("short_circuit_ka"):
        lv_parts.append(f"{lv_bus.get('short_circuit_ka')} kA")
    items.append(("LV Busbar", ", ".join(lv_parts) if lv_parts else "TBD"))

    items.append(("MV Cable", cables.get("mv_cable_spec") or "TBD"))
    items.append(("LV Cable", cables.get("lv_cable_spec") or "TBD"))
    items.append(("DC Cable", cables.get("dc_cable_spec") or "TBD"))
    items.append(("DC Fuse", dc_fuse.get("fuse_spec") or "TBD"))

    return items


def _energy_per_block(snapshot: dict, entry: dict) -> float:
    energy = entry.get("dc_block_energy_mwh")
    count = entry.get("dc_block_count") or 0
    if energy and count:
        return energy / count
    return _safe_float(snapshot.get("dc_block_energy_mwh"), 0.0)


def render_jp_pro_svg(snapshot: dict, out_svg: Path) -> None:
    out_svg = Path(out_svg)

    width = 1200
    height = 900

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
"""

    table_x = 40
    table_y = 40
    table_w = 230
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
    col_split = table_x + 90
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
        root, "text", attrib={"x": str(table_x + 4), "y": str(table_y + 15), "class": "label"}
    )
    title.text = "Equipment List"
    head_item = ET.SubElement(
        root,
        "text",
        attrib={"x": str(table_x + 4), "y": str(table_y + header_h + 14), "class": "label"},
    )
    head_item.text = "Item"
    head_spec = ET.SubElement(
        root,
        "text",
        attrib={"x": str(col_split + 4), "y": str(table_y + header_h + 14), "class": "label"},
    )
    head_spec.text = "Spec"

    for idx, (item, spec) in enumerate(items, start=1):
        y = table_y + header_h + row_h * idx + 14
        t_item = ET.SubElement(
            root, "text", attrib={"x": str(table_x + 4), "y": str(y), "class": "label"}
        )
        t_item.text = item
        t_spec = ET.SubElement(
            root, "text", attrib={"x": str(col_split + 4), "y": str(y), "class": "label"}
        )
        t_spec.text = spec

    diagram_left = 300
    mv_box = (diagram_left, 40, 820, 120)
    ET.SubElement(
        root,
        "rect",
        attrib={
            "x": str(mv_box[0]),
            "y": str(mv_box[1]),
            "width": str(mv_box[2]),
            "height": str(mv_box[3]),
            "class": "dash",
        },
    )
    mv_label = ET.SubElement(
        root,
        "text",
        attrib={"x": str(mv_box[0] + 6), "y": str(mv_box[1] + 16), "class": "label"},
    )
    mv_label.text = "MV Skid"
    rmu_label = ET.SubElement(
        root,
        "text",
        attrib={"x": str(mv_box[0] + 20), "y": str(mv_box[1] + 60), "class": "label"},
    )
    rmu_label.text = "RMU: LBS x2 / GCB / DS"

    tr_x = diagram_left + 260
    tr_y = 190
    tr_w = 120
    tr_h = 50
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
    tr_text = ET.SubElement(
        root,
        "text",
        attrib={"x": str(tr_x + tr_w + 10), "y": str(tr_y + 20), "class": "label"},
    )
    hv_kv = _safe_float(snapshot.get("transformer", {}).get("hv_kv"), 0.0)
    lv_v = _safe_float(snapshot.get("transformer", {}).get("lv_v"), 0.0)
    rated_mva = _safe_float(snapshot.get("transformer", {}).get("rated_mva"), 0.0)
    uk_percent = snapshot.get("electrical_inputs", {}).get("transformer", {}).get("uk_percent")
    vector_group = snapshot.get("electrical_inputs", {}).get("transformer", {}).get("vector_group")
    cooling = snapshot.get("electrical_inputs", {}).get("transformer", {}).get("cooling")
    tr_parts = [
        f"{_format_hv_voltage(hv_kv)}/{_format_lv_voltage(lv_v)}",
        f"{rated_mva:g} MVA" if rated_mva else "TBD",
    ]
    if uk_percent:
        tr_parts.append(f"Uk={uk_percent}%")
    if vector_group:
        tr_parts.append(str(vector_group))
    if cooling:
        tr_parts.append(str(cooling))
    tr_text.text = " / ".join(tr_parts)

    bus_y = 320
    bus_x1 = diagram_left + 80
    bus_x2 = diagram_left + 780
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
    pcs_box_w = 140
    pcs_box_h = 50
    pcs_gap = 30
    pcs_total = pcs_count * pcs_box_w + (pcs_count - 1) * pcs_gap
    pcs_start_x = diagram_left + (bus_x2 - bus_x1 - pcs_total) / 2 + 80
    pcs_rating = _safe_float(snapshot.get("ac_block", {}).get("pcs_rating_each_kva"), 0.0)

    feeders = snapshot.get("feeders", []) or []
    dc_by_feeder = {entry.get("feeder_id"): entry for entry in snapshot.get("dc_blocks_by_feeder", [])}

    for idx in range(pcs_count):
        x = pcs_start_x + idx * (pcs_box_w + pcs_gap)
        y = 360
        ET.SubElement(
            root,
            "rect",
            attrib={"x": str(x), "y": str(y), "width": str(pcs_box_w), "height": str(pcs_box_h), "class": "outline"},
        )
        pcs_label = ET.SubElement(
            root,
            "text",
            attrib={"x": str(x + 6), "y": str(y + 20), "class": "label"},
        )
        pcs_label.text = f"PCS{idx + 1}"
        pcs_rating_text = ET.SubElement(
            root,
            "text",
            attrib={"x": str(x + 6), "y": str(y + 38), "class": "label"},
        )
        pcs_rating_text.text = f"{pcs_rating:g} kVA" if pcs_rating else "TBD"

        feeder = feeders[idx] if idx < len(feeders) else {}
        feeder_id = feeder.get("feeder_id") or f"FDR-{idx + 1:02d}"
        dc_entry = dc_by_feeder.get(feeder_id, {})
        dc_count = dc_entry.get("dc_block_count") or 0
        energy = _energy_per_block(snapshot, dc_entry)

        bu_y = y + 80
        ET.SubElement(
            root,
            "rect",
            attrib={"x": str(x), "y": str(bu_y), "width": str(pcs_box_w), "height": str(pcs_box_h), "class": "outline"},
        )
        bu_label = ET.SubElement(
            root,
            "text",
            attrib={"x": str(x + 6), "y": str(bu_y + 22), "class": "label"},
        )
        if dc_count and dc_count > 1:
            bu_label.text = f"Battery Unit x{dc_count}"
        else:
            bu_label.text = "Battery Unit"
        bu_energy = ET.SubElement(
            root,
            "text",
            attrib={"x": str(x + 6), "y": str(bu_y + 40), "class": "label"},
        )
        if energy:
            bu_energy.text = f"{energy:.3f} MWh"
        else:
            bu_energy.text = "MWh TBD"

        ET.SubElement(
            root,
            "line",
            attrib={"x1": str(x + pcs_box_w / 2), "y1": str(bus_y), "x2": str(x + pcs_box_w / 2), "y2": str(y), "class": "thin"},
        )
        ET.SubElement(
            root,
            "line",
            attrib={"x1": str(x + pcs_box_w / 2), "y1": str(y + pcs_box_h), "x2": str(x + pcs_box_w / 2), "y2": str(bu_y), "class": "thin"},
        )

    out_svg.parent.mkdir(parents=True, exist_ok=True)
    tree = ET.ElementTree(root)
    tree.write(out_svg, encoding="utf-8", xml_declaration=True)
