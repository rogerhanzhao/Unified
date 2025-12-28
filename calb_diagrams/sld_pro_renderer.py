import math
from pathlib import Path
from typing import List, Tuple

try:  # pragma: no cover - optional dependency
    import svgwrite
except Exception:  # pragma: no cover
    svgwrite = None

from calb_diagrams.specs import (
    SLD_DASH_ARRAY,
    SLD_FONT_FAMILY,
    SLD_FONT_SIZE,
    SLD_FONT_SIZE_SMALL,
    SLD_FONT_SIZE_TITLE,
    SLD_STROKE_OUTLINE,
    SLD_STROKE_THICK,
    SLD_STROKE_THIN,
    SldGroupSpec,
)

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


def _approx_chars(width_px: float) -> int:
    return max(6, int(width_px / 7))


def _table_row_lines(text: str, max_chars: int) -> List[str]:
    value = str(text or "TBD")
    lines = _wrap_text(value, max_chars)
    return lines if lines else ["TBD"]


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


def _split_pcs_groups(pcs_count: int) -> tuple[list[int], list[int]]:
    if pcs_count <= 0:
        return [], []
    split = int(math.ceil(pcs_count / 2))
    return list(range(1, split + 1)), list(range(split + 1, pcs_count + 1))


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
    pcs_spec = f"{pcs_text} x {spec.pcs_count}"
    if spec.lv_voltage_v_ll:
        pcs_spec = f"{pcs_spec}, LV {format_v(spec.lv_voltage_v_ll)}"
    items.append(("PCS", pcs_spec))

    items.append(("LV Cable", cables.get("lv_cable_spec") or "TBD"))
    items.append(("DC Cable", cables.get("dc_cable_spec") or "TBD"))
    items.append(("DC Fuse", dc_fuse.get("fuse_spec") or "TBD"))

    battery_parts = [f"{format_mwh(spec.dc_block_energy_mwh)} each"]
    if spec.dc_blocks_total_in_group:
        battery_parts.append(f"x {_safe_int(spec.dc_blocks_total_in_group, 0)}")
    items.append(("Battery Storage Bank", " ".join(battery_parts) if battery_parts else "TBD"))

    allocation_parts = [
        f"F{idx + 1}={spec.dc_blocks_per_feeder[idx] if idx < len(spec.dc_blocks_per_feeder) else 0}"
        for idx in range(spec.pcs_count)
    ]
    allocation_text = ", ".join(allocation_parts) if allocation_parts else "TBD"
    items.append(("DC Block Allocation", allocation_text))

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

    width = 1750
    left_margin = 40
    left_col_width = 420
    table_x = left_margin
    table_y = 40
    table_w = left_col_width
    diagram_left = left_margin + left_col_width + 40
    diagram_right = width - 40
    diagram_width = diagram_right - diagram_left

    row_h = 16
    title_h = 20
    header_h = 18
    item_col_w = 150
    spec_col_w = table_w - item_col_w
    items = _build_equipment_list(spec)

    item_chars = _approx_chars(item_col_w)
    spec_chars = _approx_chars(spec_col_w)
    rows = []
    for item, spec_text in items:
        item_lines = _table_row_lines(item, item_chars)
        spec_lines = _table_row_lines(spec_text, spec_chars)
        rows.append(
            {
                "item_lines": item_lines,
                "spec_lines": spec_lines,
                "lines": max(len(item_lines), len(spec_lines)),
            }
        )

    table_h = title_h + header_h + sum(row["lines"] * row_h for row in rows)

    skid_x = diagram_left
    skid_y = table_y
    pcs_count = max(1, int(spec.pcs_count))
    group_a, group_b = _split_pcs_groups(pcs_count)
    group_split = len(group_a)
    pcs_box_h = 54
    pcs_pad = 60
    available = max(240.0, diagram_width - pcs_pad * 2)
    slot_w = available / pcs_count
    pcs_box_w = min(160.0, max(110.0, slot_w - 10.0))
    pcs_start_x = skid_x + pcs_pad + (slot_w - pcs_box_w) / 2

    bus_y = skid_y + 230
    pcs_y = bus_y + 24
    dc_bus_a_y = pcs_y + pcs_box_h + 28
    dc_bus_gap = 22
    dc_bus_b_y = dc_bus_a_y + dc_bus_gap
    skid_h = max(380.0, dc_bus_b_y - skid_y + 60)

    battery_y = skid_y + skid_h + 40
    battery_title_h = 20
    circuit_pad = 18
    circuit_gap = 18
    dc_circuit_a_y = battery_y + battery_title_h + circuit_pad
    dc_circuit_b_y = dc_circuit_a_y + circuit_gap
    dc_box_h = 54

    battery_x = skid_x + 40
    battery_w = diagram_width - 80
    dc_blocks_total = _safe_int(spec.dc_blocks_total_in_group, 0)
    show_individual_blocks = 0 < dc_blocks_total <= 6
    blocks_to_draw = dc_blocks_total if show_individual_blocks else 1
    block_cols = min(3, blocks_to_draw) if show_individual_blocks else 1
    block_rows = int(math.ceil(blocks_to_draw / block_cols)) if show_individual_blocks else 1
    block_gap_x = 20.0
    block_gap_y = 16.0
    block_area_w = max(220.0, battery_w - 80.0)
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

    allocation_parts = [
        f"F{idx + 1}={spec.dc_blocks_per_feeder[idx] if idx < len(spec.dc_blocks_per_feeder) else 0}"
        for idx in range(pcs_count)
    ]
    allocation_text = ", ".join(allocation_parts) if allocation_parts else "TBD"
    group_a_counts = [
        spec.dc_blocks_per_feeder[idx - 1] if idx - 1 < len(spec.dc_blocks_per_feeder) else 0
        for idx in group_a
    ]
    group_b_counts = [
        spec.dc_blocks_per_feeder[idx - 1] if idx - 1 < len(spec.dc_blocks_per_feeder) else 0
        for idx in group_b
    ]
    group_a_text = ", ".join([f"F{idx}={group_a_counts[i]}" for i, idx in enumerate(group_a)]) or "None"
    group_b_text = ", ".join([f"F{idx}={group_b_counts[i]}" for i, idx in enumerate(group_b)]) or "None"
    summary_lines = [
        f"Battery Storage Bank: {dc_blocks_total} blocks @ {format_mwh(spec.dc_block_energy_mwh)} each",
        f"PCS count: {pcs_count}, LV {format_v(spec.lv_voltage_v_ll)}",
        f"Group A feeders: {group_a_text} (total {sum(group_a_counts)})",
        f"Group B feeders: {group_b_text} (total {sum(group_b_counts)})",
        f"Allocation: {allocation_text}",
        "Counts indicate allocation for sizing/configuration; detailed DC wiring is not represented.",
    ]
    wrapped_lines = []
    for line in summary_lines:
        wrapped_lines.extend(_wrap_text(line, 64))

    note_w = min(480.0, diagram_width * 0.9)
    note_h = 24 + len(wrapped_lines) * 18
    note_x = diagram_right - note_w
    note_y = battery_y + battery_h + 24

    height = max(table_y + table_h + 40, note_y + note_h + 40)

    dwg = svgwrite.Drawing(
        filename=str(out_svg),
        size=(f"{width}px", f"{height}px"),
        viewBox=f"0 0 {width} {height}",
    )
    dwg.add(
        dwg.style(
            f"""
svg {{ font-family: {SLD_FONT_FAMILY}; font-size: {SLD_FONT_SIZE}px; }}
.outline {{ stroke: #000000; stroke-width: {SLD_STROKE_OUTLINE}; fill: none; }}
.thin {{ stroke: #000000; stroke-width: {SLD_STROKE_THIN}; fill: none; }}
.thick {{ stroke: #000000; stroke-width: {SLD_STROKE_THICK}; fill: none; }}
.dash {{ stroke: #000000; stroke-width: {SLD_STROKE_OUTLINE}; fill: none; stroke-dasharray: {SLD_DASH_ARRAY}; }}
.label {{ fill: #000000; }}
.title {{ font-size: {SLD_FONT_SIZE_TITLE}px; font-weight: bold; }}
.small {{ font-size: {SLD_FONT_SIZE_SMALL}px; }}
"""
        )
    )
    dwg.add(dwg.rect(insert=(0, 0), size=(width, height), fill="#ffffff"))

    dwg.add(dwg.rect(insert=(table_x, table_y), size=(table_w, table_h), class_="outline"))
    col_split = table_x + item_col_w
    dwg.add(dwg.line((col_split, table_y), (col_split, table_y + table_h), class_="thin"))
    dwg.add(dwg.line((table_x, table_y + title_h), (table_x + table_w, table_y + title_h), class_="thin"))
    dwg.add(dwg.line((table_x, table_y + title_h + header_h), (table_x + table_w, table_y + title_h + header_h), class_="thin"))
    dwg.add(dwg.text("Equipment List", insert=(table_x + 6, table_y + 14), class_="label title"))
    dwg.add(dwg.text("Item", insert=(table_x + 6, table_y + title_h + 13), class_="label"))
    dwg.add(dwg.text("Spec", insert=(col_split + 6, table_y + title_h + 13), class_="label"))

    current_y = table_y + title_h + header_h
    for row in rows:
        for line_idx, line in enumerate(row["item_lines"]):
            y = current_y + row_h * (line_idx + 1) - 3
            dwg.add(dwg.text(line, insert=(table_x + 6, y), class_="label"))
        for line_idx, line in enumerate(row["spec_lines"]):
            y = current_y + row_h * (line_idx + 1) - 3
            dwg.add(dwg.text(line, insert=(col_split + 6, y), class_="label"))
        current_y += row_h * row["lines"]
        dwg.add(dwg.line((table_x, current_y), (table_x + table_w, current_y), class_="thin"))

    dwg.add(dwg.rect(insert=(skid_x, skid_y), size=(diagram_width, skid_h), class_="dash"))
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

    terminal_y = skid_y + 55
    terminal_left_x = skid_x + 70
    terminal_right_x = skid_x + diagram_width - 70
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

    rmu_center_y = skid_y + 95
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

    tr_x = skid_x + diagram_width / 2 - 40
    tr_y = skid_y + 130
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

    bus_x1 = skid_x + 80
    bus_x2 = skid_x + diagram_width - 80
    dwg.add(dwg.line((bus_x1, bus_y), (bus_x2, bus_y), class_="thick"))
    dwg.add(dwg.text("LV Busbar", insert=(bus_x1, bus_y - 8), class_="label"))

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

    dwg.add(dwg.line((bus_x1, dc_bus_a_y), (bus_x2, dc_bus_a_y), class_="thick"))
    dwg.add(dwg.text("DC BUSBAR A", insert=(bus_x1, dc_bus_a_y - 8), class_="label"))
    dwg.add(dwg.line((bus_x1, dc_bus_b_y), (bus_x2, dc_bus_b_y), class_="thick"))
    dwg.add(dwg.text("DC BUSBAR B", insert=(bus_x1, dc_bus_b_y - 8), class_="label"))

    fuse_h = 10
    fuse_w = 18
    for idx in range(pcs_count):
        x = pcs_start_x + idx * slot_w
        line_x = x + pcs_box_w / 2
        target_bus_y = dc_bus_a_y if idx < group_split else dc_bus_b_y
        dwg.add(dwg.line((line_x, pcs_y + pcs_box_h), (line_x, target_bus_y), class_="thin"))
        fuse_y = (pcs_y + pcs_box_h + target_bus_y) / 2 - fuse_h / 2
        dwg.add(
            dwg.rect(insert=(line_x - fuse_w / 2, fuse_y), size=(fuse_w, fuse_h), class_="outline")
        )

    dwg.add(dwg.rect(insert=(battery_x, battery_y), size=(battery_w, battery_h), class_="dash"))
    dwg.add(
        dwg.text("Battery Storage Bank", insert=(battery_x + 8, battery_y + 16), class_="label title")
    )

    circuit_x1 = battery_x + 60
    circuit_x2 = battery_x + battery_w - 60
    dwg.add(dwg.line((circuit_x1, dc_circuit_a_y), (circuit_x2, dc_circuit_a_y), class_="thin"))
    dwg.add(dwg.text("Circuit A", insert=(circuit_x1, dc_circuit_a_y - 6), class_="small"))
    dwg.add(dwg.line((circuit_x1, dc_circuit_b_y), (circuit_x2, dc_circuit_b_y), class_="thin"))
    dwg.add(dwg.text("Circuit B", insert=(circuit_x1, dc_circuit_b_y - 6), class_="small"))

    link_x = bus_x2 - 40
    dwg.add(dwg.line((link_x, dc_bus_a_y), (link_x, dc_circuit_a_y), class_="thin"))
    dwg.add(dwg.line((link_x, dc_bus_b_y), (link_x, dc_circuit_b_y), class_="thin"))

    block_index = 0
    for row in range(block_rows):
        for col in range(block_cols):
            if show_individual_blocks and block_index >= dc_blocks_total:
                break
            cell_x = dc_box_x_start + col * (dc_box_w + block_gap_x)
            cell_y = dc_box_y + row * (dc_box_h + block_gap_y)
            dwg.add(dwg.rect(insert=(cell_x, cell_y), size=(dc_box_w, dc_box_h), class_="outline"))

            if show_individual_blocks:
                label = f"DC Block #{block_index + 1} ({format_mwh(spec.dc_block_energy_mwh)})"
            else:
                label = f"DC Block ({format_mwh(spec.dc_block_energy_mwh)}) x {dc_blocks_total}"
            dwg.add(dwg.text(label, insert=(cell_x + 6, cell_y + 20), class_="small"))
            dwg.add(dwg.text("2 circuits (A/B)", insert=(cell_x + 6, cell_y + 38), class_="small"))

            line_x_a = cell_x + dc_box_w * 0.4
            line_x_b = cell_x + dc_box_w * 0.6
            dwg.add(dwg.line((line_x_a, cell_y), (line_x_a, dc_circuit_a_y), class_="thin"))
            dwg.add(dwg.line((line_x_b, cell_y), (line_x_b, dc_circuit_b_y), class_="thin"))

            block_index += 1
        if show_individual_blocks and block_index >= dc_blocks_total:
            break

    dwg.add(
        dwg.text(
            "Each DC block provides Circuit A and Circuit B.",
            insert=(battery_x + 8, battery_note_y),
            class_="small",
        )
    )

    dwg.add(dwg.rect(insert=(note_x, note_y), size=(note_w, note_h), class_="outline"))
    dwg.add(
        dwg.text(
            "Allocation Summary (AC Block group)",
            insert=(note_x + 8, note_y + 18),
            class_="label title",
        )
    )
    for idx, line in enumerate(wrapped_lines):
        dwg.add(dwg.text(line, insert=(note_x + 8, note_y + 36 + idx * 18), class_="label"))

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
