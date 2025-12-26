from pathlib import Path
from typing import List, Tuple

try:  # pragma: no cover - optional dependency
    import svgwrite
except Exception:  # pragma: no cover
    svgwrite = None

from calb_diagrams.specs import SldGroupSpec

try:
    import cairosvg
except Exception:  # pragma: no cover - optional dependency
    cairosvg = None


def _safe_float(value, default=0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _safe_int(value, default=0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def format_mva(value) -> str:
    v = _safe_float(value, 0.0)
    if v <= 0:
        return "TBD"
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


def _wrap_text(text: str, max_chars: int) -> List[str]:
    words = text.split()
    if not words:
        return [""]
    lines = []
    current = words[0]
    for word in words[1:]:
        if len(current) + 1 + len(word) <= max_chars:
            current = f"{current} {word}"
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _rmu_class_kv(mv_kv: float) -> float:
    if mv_kv <= 24:
        return 24.0
    if mv_kv <= 36:
        return 36.0
    return round(mv_kv)


def _range_text(values: List[float], unit: str) -> str:
    if not values:
        return "TBD"
    minimum = min(values)
    maximum = max(values)
    if abs(maximum - minimum) < 1e-6:
        return f"{minimum:.0f} {unit}"
    return f"{minimum:.0f}-{maximum:.0f} {unit}"


def _build_equipment_list(spec: SldGroupSpec) -> List[Tuple[str, str]]:
    eq = spec.equipment_list or {}
    rmu = eq.get("rmu", {}) if isinstance(eq.get("rmu"), dict) else {}
    transformer = eq.get("transformer", {}) if isinstance(eq.get("transformer"), dict) else {}
    lv_bus = eq.get("lv_busbar", {}) if isinstance(eq.get("lv_busbar"), dict) else {}
    cables = eq.get("cables", {}) if isinstance(eq.get("cables"), dict) else {}
    dc_fuse = eq.get("dc_fuse", {}) if isinstance(eq.get("dc_fuse"), dict) else {}

    items = []
    items.append(("MV Cable", cables.get("mv_cable_spec") or "TBD"))

    rmu_parts = []
    rated_kv = _safe_float(rmu.get("rated_kv"), 0.0)
    if rated_kv <= 0:
        rated_kv = _rmu_class_kv(spec.mv_voltage_kv)
    rmu_parts.append(f"{rated_kv:.0f} kV class")
    rated_a = _safe_float(rmu.get("rated_a"), 0.0)
    if rated_a > 0:
        rmu_parts.append(f"{rated_a:.0f} A")
    short_ka = _safe_float(rmu.get("short_circuit_ka_3s"), 0.0)
    if short_ka > 0:
        rmu_parts.append(f"{short_ka:.1f} kA/3s")
    if rmu.get("ct_ratio"):
        rmu_parts.append(f"CT {rmu.get('ct_ratio')}")
    if rmu.get("ct_class"):
        rmu_parts.append(str(rmu.get("ct_class")))
    ct_va = _safe_float(rmu.get("ct_va"), 0.0)
    if ct_va > 0:
        rmu_parts.append(f"{ct_va:.0f} VA")
    items.append(("Ring Main Unit (RMU)", ", ".join(rmu_parts) if rmu_parts else "TBD"))

    tr_parts = [
        format_mva(spec.transformer_mva),
        f"{format_kv(spec.mv_voltage_kv)}/{format_v(spec.lv_voltage_v_ll)}",
    ]
    vector = transformer.get("vector_group") or spec.transformer_vector_group
    if vector:
        tr_parts.append(str(vector))
    uk = transformer.get("uk_percent")
    if uk is None:
        uk = spec.transformer_uk_percent
    if uk:
        tr_parts.append(f"Uk={format_percent(uk)}")
    cooling = transformer.get("cooling")
    if cooling:
        tr_parts.append(str(cooling))
    items.append(("Transformer", ", ".join(tr_parts) if tr_parts else "TBD"))

    lv_parts = []
    lv_a = _safe_float(lv_bus.get("rated_a"), 0.0)
    if lv_a > 0:
        lv_parts.append(f"{lv_a:.0f} A")
    lv_ka = _safe_float(lv_bus.get("short_circuit_ka"), 0.0)
    if lv_ka > 0:
        lv_parts.append(f"{lv_ka:.1f} kA")
    items.append(("LV Busbar", ", ".join(lv_parts) if lv_parts else "TBD"))

    pcs_text = _range_text(spec.pcs_rating_kw_list, "kW")
    items.append(("PCS", f"{pcs_text} x {spec.pcs_count}"))

    items.append(("LV Cable", cables.get("lv_cable_spec") or "TBD"))
    items.append(("DC Cable", cables.get("dc_cable_spec") or "TBD"))
    items.append(("DC Fuse", dc_fuse.get("fuse_spec") or "TBD"))

    allocation_parts = [
        f"F{idx + 1}={spec.dc_blocks_per_feeder[idx] if idx < len(spec.dc_blocks_per_feeder) else 0}"
        for idx in range(spec.pcs_count)
    ]
    allocation_text = ", ".join(allocation_parts) if allocation_parts else "TBD"
    items.append(("DC Block Allocation", allocation_text))
    items.append(
        ("DC Blocks Total (this group)", f"{_safe_int(spec.dc_blocks_total_in_group, 0)}")
    )

    return items


def _write_png(svg_path: Path, png_path: Path) -> None:
    if cairosvg is None:
        raise ImportError("cairosvg is required to export PNG from SVG.")
    cairosvg.svg2png(url=str(svg_path), write_to=str(png_path))


def render_sld_pro_svg(
    spec: SldGroupSpec, out_svg: Path, out_png: Path | None = None
) -> tuple[Path | None, str | None]:
    if svgwrite is None:
        return None, "Missing dependency: svgwrite. Please install: pip install svgwrite"
    out_svg = Path(out_svg)

    width = 1600
    height = 1000
    left_margin = 40
    left_col_width = 360
    diagram_left = left_margin + left_col_width + 40
    diagram_right = width - 40
    diagram_width = diagram_right - diagram_left

    dwg = svgwrite.Drawing(
        filename=str(out_svg),
        size=(f"{width}px", f"{height}px"),
        viewBox=f"0 0 {width} {height}",
    )
    dwg.add(
        dwg.style(
            """
svg { font-family: Arial, Helvetica, sans-serif; font-size: 12px; }
.outline { stroke: #000000; stroke-width: 1.2; fill: none; }
.thin { stroke: #000000; stroke-width: 1; fill: none; }
.thick { stroke: #000000; stroke-width: 2.2; fill: none; }
.dash { stroke: #000000; stroke-width: 1.2; fill: none; stroke-dasharray: 6,4; }
.label { fill: #000000; }
.title { font-size: 13px; font-weight: bold; }
"""
        )
    )

    table_x = left_margin
    table_y = 40
    row_h = 18
    header_h = 22
    items = _build_equipment_list(spec)
    table_h = header_h + row_h * (len(items) + 1)
    table_w = left_col_width

    dwg.add(
        dwg.rect(
            insert=(table_x, table_y),
            size=(table_w, table_h),
            class_="outline",
        )
    )
    col_split = table_x + 130
    dwg.add(dwg.line((col_split, table_y), (col_split, table_y + table_h), class_="thin"))
    dwg.add(dwg.line((table_x, table_y + header_h), (table_x + table_w, table_y + header_h), class_="thin"))
    dwg.add(dwg.text("Equipment List", insert=(table_x + 6, table_y + 15), class_="label title"))
    dwg.add(dwg.text("Item", insert=(table_x + 6, table_y + header_h + 14), class_="label"))
    dwg.add(dwg.text("Spec", insert=(col_split + 6, table_y + header_h + 14), class_="label"))

    for idx, (item, spec_text) in enumerate(items, start=1):
        y = table_y + header_h + row_h * idx + 14
        dwg.add(dwg.text(item, insert=(table_x + 6, y), class_="label"))
        dwg.add(dwg.text(spec_text, insert=(col_split + 6, y), class_="label"))

    skid_x = diagram_left
    skid_y = 40
    skid_w = diagram_width
    skid_h = 420
    dwg.add(dwg.rect(insert=(skid_x, skid_y), size=(skid_w, skid_h), class_="dash"))
    dwg.add(
        dwg.text(
            "PCS&MVT SKID (AC Block)",
            insert=(skid_x + 8, skid_y + 18),
            class_="label title",
        )
    )

    mv_labels = spec.equipment_list.get("mv_labels") if isinstance(spec.equipment_list, dict) else {}
    to_switchgear = mv_labels.get("to_switchgear") if isinstance(mv_labels, dict) else None
    to_other_rmu = mv_labels.get("to_other_rmu") if isinstance(mv_labels, dict) else None
    if not to_switchgear:
        to_switchgear = f"To {format_kv(spec.mv_voltage_kv)} Switchgear"
    if not to_other_rmu:
        to_other_rmu = "To Other RMU"

    terminal_y = skid_y + 50
    terminal_left_x = skid_x + 60
    terminal_right_x = skid_x + skid_w - 60
    dwg.add(dwg.text(to_switchgear, insert=(terminal_left_x - 10, terminal_y - 10), class_="label"))
    dwg.add(
        dwg.text(
            to_other_rmu,
            insert=(terminal_right_x + 10, terminal_y - 10),
            class_="label",
            text_anchor="end",
        )
    )
    dwg.add(dwg.line((terminal_left_x, terminal_y), (terminal_left_x, terminal_y + 20), class_="thin"))
    dwg.add(dwg.line((terminal_right_x, terminal_y), (terminal_right_x, terminal_y + 20), class_="thin"))

    rmu_center_y = skid_y + 90
    rmu_left_x = skid_x + 80
    rmu_right_x = rmu_left_x + 70
    dwg.add(dwg.text("RMU", insert=(rmu_left_x, rmu_center_y - 25), class_="label"))
    dwg.add(dwg.line((rmu_left_x, rmu_center_y - 20), (rmu_left_x, rmu_center_y + 20), class_="thin"))
    dwg.add(dwg.line((rmu_right_x, rmu_center_y - 20), (rmu_right_x, rmu_center_y + 20), class_="thin"))
    dwg.add(dwg.line((rmu_left_x, rmu_center_y), (rmu_right_x, rmu_center_y), class_="thin"))
    dwg.add(dwg.line((rmu_left_x + 28, rmu_center_y - 6), (rmu_left_x + 40, rmu_center_y + 6), class_="thin"))
    dwg.add(dwg.line((rmu_left_x + 40, rmu_center_y + 6), (rmu_left_x + 52, rmu_center_y + 6), class_="thin"))
    ground_x = rmu_left_x + 35
    ground_y = rmu_center_y + 24
    dwg.add(dwg.line((ground_x, ground_y), (ground_x, ground_y + 10), class_="thin"))
    dwg.add(dwg.line((ground_x - 8, ground_y + 10), (ground_x + 8, ground_y + 10), class_="thin"))
    dwg.add(dwg.line((ground_x - 6, ground_y + 14), (ground_x + 6, ground_y + 14), class_="thin"))
    dwg.add(dwg.line((ground_x - 4, ground_y + 18), (ground_x + 4, ground_y + 18), class_="thin"))

    tr_x = skid_x + skid_w / 2 - 40
    tr_y = skid_y + 120
    dwg.add(dwg.circle(center=(tr_x, tr_y + 25), r=18, class_="outline"))
    dwg.add(dwg.circle(center=(tr_x + 50, tr_y + 25), r=18, class_="outline"))
    dwg.add(dwg.line((tr_x + 18, tr_y + 25), (tr_x + 32, tr_y + 25), class_="thin"))

    tr_text_x = tr_x + 80
    tr_text_y = tr_y + 12
    tr_lines = [
        "Transformer",
        f"{format_kv(spec.mv_voltage_kv)}/{format_v(spec.lv_voltage_v_ll)}",
        format_mva(spec.transformer_mva),
    ]
    if spec.transformer_vector_group:
        tr_lines.append(str(spec.transformer_vector_group))
    if spec.transformer_uk_percent:
        tr_lines.append(f"Uk={format_percent(spec.transformer_uk_percent)}")
    cooling = (
        spec.equipment_list.get("transformer", {}).get("cooling")
        if isinstance(spec.equipment_list, dict)
        else None
    )
    if cooling:
        tr_lines.append(str(cooling))
    for idx, line in enumerate(tr_lines):
        dwg.add(dwg.text(line, insert=(tr_text_x, tr_text_y + idx * 16), class_="label"))

    bus_y = skid_y + 270
    bus_x1 = skid_x + 80
    bus_x2 = skid_x + skid_w - 80
    dwg.add(dwg.line((bus_x1, bus_y), (bus_x2, bus_y), class_="thick"))
    dwg.add(dwg.text("LV Busbar", insert=(bus_x1, bus_y - 8), class_="label"))

    pcs_count = max(1, int(spec.pcs_count))
    pcs_box_h = 52
    pcs_pad = 60
    available = max(200.0, skid_w - pcs_pad * 2)
    slot_w = available / pcs_count
    pcs_box_w = min(170.0, max(110.0, slot_w - 10.0))
    pcs_start_x = skid_x + pcs_pad + (slot_w - pcs_box_w) / 2
    pcs_y = bus_y + 28

    for idx in range(pcs_count):
        x = pcs_start_x + idx * slot_w
        dwg.add(dwg.rect(insert=(x, pcs_y), size=(pcs_box_w, pcs_box_h), class_="outline"))
        dwg.add(dwg.text(f"PCS-{idx + 1}", insert=(x + 8, pcs_y + 20), class_="label"))
        rating = spec.pcs_rating_kw_list[idx] if idx < len(spec.pcs_rating_kw_list) else 0.0
        rating_text = f"{rating:.0f} kW" if rating else "TBD"
        dwg.add(dwg.text(rating_text, insert=(x + 8, pcs_y + 38), class_="label"))
        dwg.add(
            dwg.line(
                (x + pcs_box_w / 2, bus_y),
                (x + pcs_box_w / 2, pcs_y),
                class_="thin",
            )
        )

    dc_group_y = skid_y + skid_h + 60
    dc_box_h = 50
    dc_box_w = pcs_box_w
    combiner_h = 22
    combiner_w = pcs_box_w * 0.7

    for idx in range(pcs_count):
        count = spec.dc_blocks_per_feeder[idx] if idx < len(spec.dc_blocks_per_feeder) else 0
        x = pcs_start_x + idx * slot_w
        line_x = x + pcs_box_w / 2
        comb_x = x + (pcs_box_w - combiner_w) / 2
        comb_y = pcs_y + pcs_box_h + 10
        dwg.add(dwg.line((line_x, pcs_y + pcs_box_h), (line_x, comb_y), class_="thin"))
        dwg.add(dwg.rect(insert=(comb_x, comb_y), size=(combiner_w, combiner_h), class_="outline"))
        dwg.add(
            dwg.text(
                "DC Combiner (simplified)",
                insert=(comb_x + 4, comb_y + 15),
                class_="label",
            )
        )
        dwg.add(
            dwg.line(
                (line_x, comb_y + combiner_h),
                (line_x, dc_group_y),
                class_="thin",
            )
        )

        dwg.add(dwg.rect(insert=(x, dc_group_y), size=(dc_box_w, dc_box_h), class_="outline"))
        dc_text = f"DC Block Group ({format_mwh(spec.dc_block_energy_mwh)} each) x {count}"
        dwg.add(dwg.text(dc_text, insert=(x + 6, dc_group_y + 30), class_="label"))

    battery_x = skid_x + 40
    battery_y = dc_group_y - 20
    battery_w = skid_w - 80
    battery_h = dc_box_h + 60
    dwg.add(dwg.rect(insert=(battery_x, battery_y), size=(battery_w, battery_h), class_="dash"))
    dwg.add(dwg.text("DC Block Group", insert=(battery_x + 8, battery_y + 16), class_="label title"))
    battery_symbol_x = battery_x + 8
    battery_symbol_y = battery_y + 26
    dwg.add(dwg.rect(insert=(battery_symbol_x, battery_symbol_y), size=(28, 16), class_="outline"))
    dwg.add(dwg.line((battery_symbol_x + 28, battery_symbol_y + 4), (battery_symbol_x + 32, battery_symbol_y + 4), class_="thin"))
    dwg.add(dwg.line((battery_symbol_x + 28, battery_symbol_y + 12), (battery_symbol_x + 32, battery_symbol_y + 12), class_="thin"))
    dwg.add(dwg.text("+", insert=(battery_symbol_x + 6, battery_symbol_y + 12), class_="label"))
    dwg.add(dwg.text("-", insert=(battery_symbol_x + 18, battery_symbol_y + 12), class_="label"))

    allocation_parts = [
        f"F{idx + 1}={spec.dc_blocks_per_feeder[idx] if idx < len(spec.dc_blocks_per_feeder) else 0}"
        for idx in range(pcs_count)
    ]
    allocation_text = "DC Block Allocation: " + ", ".join(allocation_parts)

    note_lines = [
        f"Group Summary: PCS={pcs_count}, DC Blocks Total={spec.dc_blocks_total_in_group}",
        allocation_text,
        "Note: Counts indicate allocation for sizing/configuration; detailed DC wiring is not represented.",
    ]
    wrapped_lines = []
    for line in note_lines:
        wrapped_lines.extend(_wrap_text(line, 56))

    note_w = 430
    note_h = 24 + len(wrapped_lines) * 18
    note_x = diagram_right - note_w
    note_y = battery_y + battery_h + 30
    dwg.add(dwg.rect(insert=(note_x, note_y), size=(note_w, note_h), class_="outline"))
    dwg.add(
        dwg.text(
            "DC Block Allocation (for this AC Block group)",
            insert=(note_x + 8, note_y + 18),
            class_="label title",
        )
    )
    for idx, line in enumerate(wrapped_lines):
        dwg.add(dwg.text(line, insert=(note_x + 8, note_y + 36 + idx * 18), class_="label"))

    total_height = max(height, int(note_y + note_h + 40))
    if total_height != height:
        dwg["height"] = f"{total_height}px"
        dwg.viewbox(0, 0, width, total_height)

    out_svg.parent.mkdir(parents=True, exist_ok=True)
    dwg.save()

    png_warning = None
    if out_png is not None:
        out_png = Path(out_png)
        out_png.parent.mkdir(parents=True, exist_ok=True)
        try:
            _write_png(out_svg, out_png)
        except ImportError:
            png_warning = "Missing dependency: cairosvg. PNG export skipped."
        except Exception:
            png_warning = "PNG export failed."

    return out_svg, png_warning
