import base64
import html
import math
from pathlib import Path
from typing import Tuple

try:  # pragma: no cover - optional dependency
    import svgwrite
except Exception:  # pragma: no cover
    svgwrite = None

from calb_diagrams.specs import (
    LAYOUT_DASH_ARRAY,
    LAYOUT_FONT_FAMILY,
    LAYOUT_FONT_SIZE,
    LAYOUT_FONT_SIZE_SMALL,
    LAYOUT_FONT_SIZE_TITLE,
    LAYOUT_STROKE_OUTLINE,
    LAYOUT_STROKE_THIN,
    LayoutBlockSpec,
)

try:
    import cairosvg
except Exception:  # pragma: no cover - optional dependency
    cairosvg = None


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


def _write_png(svg_path: Path, png_path: Path) -> None:
    if cairosvg is None:
        raise ImportError("cairosvg is required to export PNG from SVG.")
    cairosvg.svg2png(url=str(svg_path), write_to=str(png_path))


def _grid_positions(arrangement: str) -> Tuple[int, int]:
    if arrangement == "2x2":
        return 2, 2
    if arrangement == "1x4":
        return 1, 4
    if arrangement == "4x1":
        return 4, 1
    return 2, 2


def _format_clearance(value) -> str:
    try:
        numeric = float(value)
    except Exception:
        return "TBD"
    if numeric <= 0:
        return "TBD"
    return f"{numeric:.1f} m"


def _m_to_px(value, scale: float) -> float:
    numeric = _safe_float(value, 0.0)
    if numeric <= 0:
        return 0.0
    return numeric * 1000.0 * scale


def _gap_px(value, scale: float, fallback_px: float) -> float:
    px = _m_to_px(value, scale)
    if px <= 0:
        return fallback_px
    return px


def _resolve_block_count(spec: LayoutBlockSpec, block_index: int) -> int:
    if isinstance(spec.dc_block_counts_by_block, dict):
        count = spec.dc_block_counts_by_block.get(block_index)
        if count is not None:
            return max(1, _safe_int(count, 1))
    return max(1, _safe_int(spec.dc_blocks_per_block, 1))


def _draw_h_dimension(dwg, x1, x2, y, ext_y, text):
    arrow = 6
    dwg.add(dwg.line((x1, ext_y), (x1, y), class_="thin"))
    dwg.add(dwg.line((x2, ext_y), (x2, y), class_="thin"))
    dwg.add(dwg.line((x1, y), (x2, y), class_="thin"))
    dwg.add(dwg.line((x1, y), (x1 + arrow, y - arrow / 2), class_="thin"))
    dwg.add(dwg.line((x1, y), (x1 + arrow, y + arrow / 2), class_="thin"))
    dwg.add(dwg.line((x2, y), (x2 - arrow, y - arrow / 2), class_="thin"))
    dwg.add(dwg.line((x2, y), (x2 - arrow, y + arrow / 2), class_="thin"))
    dwg.add(dwg.text(text, insert=((x1 + x2) / 2, y - 4), class_="dim-text", text_anchor="middle"))


def _draw_v_dimension(dwg, y1, y2, x, ext_x, text):
    arrow = 6
    dwg.add(dwg.line((ext_x, y1), (x, y1), class_="thin"))
    dwg.add(dwg.line((ext_x, y2), (x, y2), class_="thin"))
    dwg.add(dwg.line((x, y1), (x, y2), class_="thin"))
    dwg.add(dwg.line((x, y1), (x - arrow / 2, y1 + arrow), class_="thin"))
    dwg.add(dwg.line((x, y1), (x + arrow / 2, y1 + arrow), class_="thin"))
    dwg.add(dwg.line((x, y2), (x - arrow / 2, y2 - arrow), class_="thin"))
    dwg.add(dwg.line((x, y2), (x + arrow / 2, y2 - arrow), class_="thin"))
    dwg.add(dwg.text(text, insert=(x + 6, (y1 + y2) / 2), class_="dim-text"))


def _draw_dc_interior(dwg, x, y, w, h, mirrored: bool = False):
    """
    Draw DC Block (BESS) interior with 6 battery module racks + Liquid Cooling.
    Clean design: 6 rectangles (1x6 single row) representing battery racks.
    Right side: Liquid Cooling strip.
    """
    pad = min(10.0, max(4.0, w * 0.06))
    
    # Liquid Cooling strip on the right (approx 15% width)
    cooling_w = w * 0.15
    cooling_x = x + w - pad - cooling_w
    cooling_y = y + pad
    cooling_h = h - 2 * pad
    
    dwg.add(dwg.rect(insert=(cooling_x, cooling_y), size=(cooling_w, cooling_h), class_="thin"))
    # Add text "COOLING" vertically or small text
    dwg.add(dwg.text("COOLING", insert=(cooling_x + cooling_w/2, cooling_y + cooling_h/2), 
                     class_="dim-text", text_anchor="middle", transform=f"rotate(90, {cooling_x + cooling_w/2}, {cooling_y + cooling_h/2})"))

    # Battery modules grid: 1 row x 6 columns = 6 modules
    # Grid occupies remaining area to the left
    grid_x_start = x + pad
    grid_y_start = y + pad
    grid_w = w - 2 * pad - cooling_w - pad # Extra pad between modules and cooling
    grid_h = h - 2 * pad
    
    cols = 6
    rows = 1
    
    # Calculate module dimensions with inter-module spacing
    module_spacing = max(2.0, min(grid_w, grid_h) * 0.03)
    module_w = (grid_w - module_spacing * (cols - 1)) / cols
    module_h = grid_h
    
    # Draw 6 battery modules
    for row in range(rows):
        for col in range(cols):
            mod_x = grid_x_start + col * (module_w + module_spacing)
            mod_y = grid_y_start + row * (module_h + module_spacing)
            
            # Draw module rectangle
            dwg.add(dwg.rect(insert=(mod_x, mod_y), size=(module_w, module_h), class_="thin"))


def _draw_ac_interior(dwg, x, y, w, h, skid_text: str):
    """
    Draw AC Block (PCS&MVT SKID) interior.
    Represents power conversion and transformation area.
    """
    pcs_w = w * 0.55
    tr_w = w * 0.3
    rmu_w = w - pcs_w - tr_w
    if rmu_w < w * 0.1:
        rmu_w = w * 0.1
        pcs_w = w - tr_w - rmu_w

    split_1 = x + pcs_w
    split_2 = split_1 + tr_w
    dwg.add(dwg.line((split_1, y), (split_1, y + h), class_="thin"))
    dwg.add(dwg.line((split_2, y), (split_2, y + h), class_="thin"))

    dwg.add(dwg.text("PCS Unit", insert=(x + 6, y + 16), class_="dim-text"))
    dwg.add(dwg.text("Transformer", insert=(split_1 + 6, y + 16), class_="dim-text"))
    dwg.add(dwg.text("RMU", insert=(split_2 + 6, y + 16), class_="dim-text"))

    # PCS area: show 2 or 4 PCS modules depending on block config
    pcs_pad = max(4.0, pcs_w * 0.06)
    # Typically 2 or 4 PCS per block
    pcs_cols = 2
    pcs_rows = 2
    cabinet_w = (pcs_w - pcs_pad * (pcs_cols + 1)) / pcs_cols
    cabinet_h = (h - pcs_pad * 2) / pcs_rows
    
    for row in range(pcs_rows):
        for col in range(pcs_cols):
            cx = x + pcs_pad + col * (cabinet_w + pcs_pad)
            cy = y + pcs_pad + row * (cabinet_h + pcs_pad * 0.5)
            dwg.add(dwg.rect(insert=(cx, cy), size=(cabinet_w, cabinet_h), class_="thin"))

    # Transformer area: show transformer symbol
    tr_pad = max(5.0, tr_w * 0.08)
    dwg.add(
        dwg.rect(
            insert=(split_1 + tr_pad, y + tr_pad),
            size=(tr_w - tr_pad * 2, h - tr_pad * 2),
            class_="thin",
        )
    )

    rmu_pad = max(4.0, rmu_w * 0.12)
    dwg.add(
        dwg.rect(
            insert=(split_2 + rmu_pad, y + rmu_pad),
            size=(rmu_w - rmu_pad * 2, h - rmu_pad * 2),
            class_="thin",
        )
    )

    dwg.add(dwg.text(skid_text, insert=(x + w / 2, y + h / 2 + 4), class_="label", text_anchor="middle"))


def _svg_to_data_uri(path: Path) -> str | None:
    try:
        data = Path(path).read_bytes()
    except Exception:
        return None
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def _svg_escape(text) -> str:
    return html.escape(str(text)) if text is not None else ""


def _svg_line(lines, x1, y1, x2, y2, class_name="thin"):
    lines.append(
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" class="{class_name}" />'
    )


def _svg_rect(lines, x, y, w, h, class_name="outline"):
    lines.append(
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" class="{class_name}" />'
    )


def _svg_text(lines, text, x, y, class_name="label", anchor=None):
    anchor_attr = f' text-anchor="{anchor}"' if anchor else ""
    safe = _svg_escape(text)
    lines.append(
        f'<text x="{x:.1f}" y="{y:.1f}" class="{class_name}"{anchor_attr}>{safe}</text>'
    )


def _draw_h_dimension_raw(lines, x1, x2, y, ext_y, text):
    arrow = 6
    _svg_line(lines, x1, ext_y, x1, y)
    _svg_line(lines, x2, ext_y, x2, y)
    _svg_line(lines, x1, y, x2, y)
    _svg_line(lines, x1, y, x1 + arrow, y - arrow / 2)
    _svg_line(lines, x1, y, x1 + arrow, y + arrow / 2)
    _svg_line(lines, x2, y, x2 - arrow, y - arrow / 2)
    _svg_line(lines, x2, y, x2 - arrow, y + arrow / 2)
    _svg_text(lines, text, (x1 + x2) / 2, y - 4, class_name="dim-text", anchor="middle")


def _draw_v_dimension_raw(lines, y1, y2, x, ext_x, text):
    arrow = 6
    _svg_line(lines, ext_x, y1, x, y1)
    _svg_line(lines, ext_x, y2, x, y2)
    _svg_line(lines, x, y1, x, y2)
    _svg_line(lines, x, y1, x - arrow / 2, y1 + arrow)
    _svg_line(lines, x, y1, x + arrow / 2, y1 + arrow)
    _svg_line(lines, x, y2, x - arrow / 2, y2 - arrow)
    _svg_line(lines, x, y2, x + arrow / 2, y2 - arrow)
    _svg_text(lines, text, x + 6, (y1 + y2) / 2, class_name="dim-text")


def _draw_dc_interior_raw(lines, x, y, w, h, mirrored: bool = False):
    """
    Draw DC Block (BESS) interior with 6 battery module racks + Liquid Cooling (raw SVG).
    Clean design: 6 rectangles (1x6 single row) representing battery racks.
    Right side: Liquid Cooling strip.
    """
    pad = min(10.0, max(4.0, w * 0.06))
    
    # Liquid Cooling strip on the right (approx 15% width)
    cooling_w = w * 0.15
    cooling_x = x + w - pad - cooling_w
    cooling_y = y + pad
    cooling_h = h - 2 * pad
    
    _svg_rect(lines, cooling_x, cooling_y, cooling_w, cooling_h, class_name="thin")
    # Add text "COOLING" vertically
    cx = cooling_x + cooling_w/2
    cy = cooling_y + cooling_h/2
    # SVG transform rotate is around a point
    lines.append(f'<text x="{cx:.1f}" y="{cy:.1f}" class="dim-text" text-anchor="middle" transform="rotate(90, {cx:.1f}, {cy:.1f})">COOLING</text>')

    # Battery modules grid: 1 row x 6 columns = 6 modules
    # Grid occupies remaining area to the left
    grid_x_start = x + pad
    grid_y_start = y + pad
    grid_w = w - 2 * pad - cooling_w - pad
    grid_h = h - 2 * pad
    
    cols = 6
    rows = 1
    
    # Calculate module dimensions with inter-module spacing
    module_spacing = max(2.0, min(grid_w, grid_h) * 0.03)
    module_w = (grid_w - module_spacing * (cols - 1)) / cols
    module_h = grid_h
    
    # Draw 6 battery modules
    for row in range(rows):
        for col in range(cols):
            mod_x = grid_x_start + col * (module_w + module_spacing)
            mod_y = grid_y_start + row * (module_h + module_spacing)
            
            # Draw module rectangle
            _svg_rect(lines, mod_x, mod_y, module_w, module_h, class_name="thin")


def _draw_ac_interior_raw(lines, x, y, w, h, skid_text: str):
    """
    Draw AC Block (PCS&MVT SKID) interior (raw SVG).
    Represents power conversion and transformation area.
    """
    pcs_w = w * 0.55
    tr_w = w * 0.3
    rmu_w = w - pcs_w - tr_w
    if rmu_w < w * 0.1:
        rmu_w = w * 0.1
        pcs_w = w - tr_w - rmu_w

    split_1 = x + pcs_w
    split_2 = split_1 + tr_w
    _svg_line(lines, split_1, y, split_1, y + h, class_name="thin")
    _svg_line(lines, split_2, y, split_2, y + h, class_name="thin")
    _svg_text(lines, "PCS Unit", x + 6, y + 16, class_name="dim-text")
    _svg_text(lines, "Transformer", split_1 + 6, y + 16, class_name="dim-text")
    _svg_text(lines, "RMU", split_2 + 6, y + 16, class_name="dim-text")

    # PCS area: show 2x2 grid of PCS modules
    pcs_pad = max(4.0, pcs_w * 0.06)
    pcs_cols = 2
    pcs_rows = 2
    cabinet_w = (pcs_w - pcs_pad * (pcs_cols + 1)) / pcs_cols
    cabinet_h = (h - pcs_pad * 2) / pcs_rows
    
    for row in range(pcs_rows):
        for col in range(pcs_cols):
            cx = x + pcs_pad + col * (cabinet_w + pcs_pad)
            cy = y + pcs_pad + row * (cabinet_h + pcs_pad * 0.5)
            _svg_rect(lines, cx, cy, cabinet_w, cabinet_h, class_name="thin")

    # Transformer area
    tr_pad = max(5.0, tr_w * 0.08)
    _svg_rect(lines, split_1 + tr_pad, y + tr_pad, tr_w - tr_pad * 2, h - tr_pad * 2, class_name="thin")

    rmu_pad = max(4.0, rmu_w * 0.12)
    _svg_rect(lines, split_2 + rmu_pad, y + rmu_pad, rmu_w - rmu_pad * 2, h - rmu_pad * 2, class_name="thin")

    _svg_text(lines, skid_text, x + w / 2, y + h / 2 + 4, class_name="label", anchor="middle")


def _render_layout_block_svg_fallback(spec: LayoutBlockSpec) -> str:
    scale = _safe_float(getattr(spec, "scale", 0.04), 0.04)
    container_len = max(1.0, _safe_float(spec.container_length_mm, 6058)) * scale
    container_w = max(1.0, _safe_float(spec.container_width_mm, 2438)) * scale

    fallback_gap = max(16.0, container_w * 0.25)
    dc_gap = _gap_px(spec.dc_to_dc_clearance_m, scale, fallback_gap)
    ac_gap = _gap_px(spec.dc_to_ac_clearance_m, scale, fallback_gap)
    perimeter_px = _m_to_px(spec.perimeter_clearance_m, scale)

    left_margin = _safe_int(getattr(spec, "left_margin", 40), 40)
    top_margin = _safe_int(getattr(spec, "top_margin", 40), 40)
    gap_y = 50
    inner_pad = 10
    title_h = 22
    dim_band_h = 18
    label_h = 18

    blocks = []
    max_block_width = 0.0
    for block_index in spec.block_indices_to_render:
        dc_count = _resolve_block_count(spec, block_index)
        cols, rows = _grid_positions(spec.arrangement)
        cols = max(1, cols)
        rows = max(1, rows)
        if dc_count > cols * rows:
            rows = int(math.ceil(dc_count / cols))

        dc_w = cols * container_len + max(0, cols - 1) * dc_gap
        dc_h = rows * container_w + max(0, rows - 1) * dc_gap
        skid_w = container_len if spec.show_skid else 0.0
        skid_h = container_w if spec.show_skid else 0.0

        content_w = dc_w + (ac_gap if spec.show_skid else 0.0) + skid_w
        content_h = max(dc_h, skid_h)

        block_w = content_w + (inner_pad * 2) + (perimeter_px * 2)
        block_h = title_h + dim_band_h + content_h + label_h + (perimeter_px * 2) + 24

        blocks.append(
            {
                "block_index": block_index,
                "dc_count": dc_count,
                "cols": cols,
                "rows": rows,
                "dc_w": dc_w,
                "dc_h": dc_h,
                "content_w": content_w,
                "content_h": content_h,
                "block_w": block_w,
                "block_h": block_h,
            }
        )
        max_block_width = max(max_block_width, block_w)

    height = top_margin * 2 + sum(b["block_h"] for b in blocks) + max(0, len(blocks) - 1) * gap_y
    width = left_margin * 2 + max_block_width

    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.1f}px" height="{height:.1f}px" viewBox="0 0 {width:.1f} {height:.1f}">',
        '<rect x="0" y="0" width="100%" height="100%" fill="#ffffff" />',
        "<style>",
        f"svg {{ font-family: {LAYOUT_FONT_FAMILY}; font-size: {LAYOUT_FONT_SIZE}px; }}",
        f".outline {{ stroke: #000000; stroke-width: {LAYOUT_STROKE_OUTLINE}; fill: none; }}",
        f".thin {{ stroke: #000000; stroke-width: {LAYOUT_STROKE_THIN}; fill: none; }}",
        f".dash {{ stroke: #000000; stroke-width: {LAYOUT_STROKE_OUTLINE}; fill: none; stroke-dasharray: {LAYOUT_DASH_ARRAY}; }}",
        ".label { fill: #000000; }",
        f".title {{ font-size: {LAYOUT_FONT_SIZE_TITLE}px; font-weight: bold; }}",
        f".dim-text {{ fill: #000000; font-size: {LAYOUT_FONT_SIZE_SMALL}px; }}",
        "</style>",
    ]

    block_title_template = spec.labels.get("block_title") if isinstance(spec.labels, dict) else None
    bess_text_template = spec.labels.get("bess_range_text") if isinstance(spec.labels, dict) else None
    skid_text = spec.labels.get("skid_text") if isinstance(spec.labels, dict) else None
    skid_subtext = spec.labels.get("skid_subtext") if isinstance(spec.labels, dict) else None
    if not block_title_template:
        block_title_template = "Block {index}: DC Blocks={dc_blocks}"
    if not bess_text_template:
        bess_text_template = "BESS {start}~{end}"
    if not skid_text:
        skid_text = "PCS&MVT SKID"

    block_offset = 0
    current_y = top_margin
    for block in blocks:
        block_index = block["block_index"]
        dc_count = block["dc_count"]
        cols = block["cols"]
        rows = block["rows"]
        dc_w = block["dc_w"]
        dc_h = block["dc_h"]

        block_x = left_margin
        block_y = current_y
        if perimeter_px > 0:
            _svg_rect(lines, block_x, block_y, block["block_w"], block["block_h"], class_name="dash")

        start = block_offset + 1
        end = block_offset + dc_count
        block_offset += dc_count

        try:
            title_text = block_title_template.format(index=block_index, dc_blocks=dc_count, start=start, end=end)
        except Exception:
            title_text = block_title_template
        _svg_text(lines, title_text, block_x + 6, block_y + 16, class_name="label title")

        content_x = block_x + perimeter_px + inner_pad
        content_y = block_y + perimeter_px + title_h + dim_band_h + 6

        dc_array_x = content_x
        dc_array_y = content_y

        for r in range(rows):
            for c in range(cols):
                idx = r * cols + c
                if idx >= dc_count:
                    continue
                cell_x = dc_array_x + c * (container_len + dc_gap)
                cell_y = dc_array_y + r * (container_w + dc_gap)
                _svg_rect(lines, cell_x, cell_y, container_len, container_w)
                _draw_dc_interior_raw(
                    lines, cell_x, cell_y, container_len, container_w, mirrored=spec.dc_block_mirrored
                )
                # _svg_text(lines, "DC Block", cell_x + 6, cell_y + 18)

        bess_text = bess_text_template.format(start=start, end=end)
        _svg_text(lines, bess_text, dc_array_x, dc_array_y + dc_h + 18)

        if spec.show_skid:
            skid_x = dc_array_x + dc_w + ac_gap
            skid_y = dc_array_y
            _svg_rect(lines, skid_x, skid_y, container_len, container_w)
            _draw_ac_interior_raw(lines, skid_x, skid_y, container_len, container_w, skid_text)
            if skid_subtext:
                _svg_text(lines, skid_subtext, skid_x + 6, skid_y + container_w - 10, class_name="dim-text")

        dim_y_main = dc_array_y - 6
        dim_y_secondary = dim_y_main - 16
        dc_text = _format_clearance(spec.dc_to_dc_clearance_m)
        ac_text = _format_clearance(spec.dc_to_ac_clearance_m)

        if cols > 1:
            x1 = dc_array_x + container_len
            x2 = dc_array_x + container_len + dc_gap
            _draw_h_dimension_raw(lines, x1, x2, dim_y_main, dc_array_y, dc_text)
        if rows > 1:
            y1 = dc_array_y + container_w
            y2 = dc_array_y + container_w + dc_gap
            _draw_v_dimension_raw(lines, y1, y2, dc_array_x - 6, dc_array_x, dc_text)

        if spec.show_skid:
            x1 = dc_array_x + dc_w
            x2 = dc_array_x + dc_w + ac_gap
            _draw_h_dimension_raw(
                lines, x1, x2, dim_y_secondary if cols > 1 else dim_y_main, dc_array_y, ac_text
            )

        current_y += block["block_h"] + gap_y

    lines.append("</svg>")
    return "\n".join(lines)


def render_layout_block_svg(
    spec: LayoutBlockSpec, out_svg: Path, out_png: Path | None = None
) -> tuple[Path | None, str | None]:
    if svgwrite is None:
        out_svg = Path(out_svg)
        svg_text = _render_layout_block_svg_fallback(spec)
        out_svg.parent.mkdir(parents=True, exist_ok=True)
        out_svg.write_text(svg_text, encoding="utf-8")
        png_warning = None
        if out_png is not None:
            png_warning = "PNG export skipped (svgwrite unavailable)."
        return out_svg, "Pro renderer unavailable; fallback to raw SVG."
    out_svg = Path(out_svg)

    scale = _safe_float(getattr(spec, "scale", 0.04), 0.04)
    container_len = max(1.0, _safe_float(spec.container_length_mm, 6058)) * scale
    container_w = max(1.0, _safe_float(spec.container_width_mm, 2438)) * scale

    fallback_gap = max(16.0, container_w * 0.25)
    dc_gap = _gap_px(spec.dc_to_dc_clearance_m, scale, fallback_gap)
    ac_gap = _gap_px(spec.dc_to_ac_clearance_m, scale, fallback_gap)
    perimeter_px = _m_to_px(spec.perimeter_clearance_m, scale)

    left_margin = _safe_int(getattr(spec, "left_margin", 40), 40)
    top_margin = _safe_int(getattr(spec, "top_margin", 40), 40)
    gap_y = 50
    inner_pad = 10
    title_h = 22
    dim_band_h = 18
    label_h = 18

    use_template = bool(getattr(spec, "use_template", False))
    dc_template_uri = None
    ac_template_uri = None
    template_warning = None
    if use_template:
        if getattr(spec, "dc_block_svg_path", None):
            dc_template_uri = _svg_to_data_uri(Path(spec.dc_block_svg_path))
        if getattr(spec, "ac_block_svg_path", None):
            ac_template_uri = _svg_to_data_uri(Path(spec.ac_block_svg_path))
        if dc_template_uri is None or ac_template_uri is None:
            template_warning = "Layout template asset missing; using built-in template."

    blocks = []
    max_block_width = 0.0
    for block_index in spec.block_indices_to_render:
        dc_count = _resolve_block_count(spec, block_index)
        cols, rows = _grid_positions(spec.arrangement)
        cols = max(1, cols)
        rows = max(1, rows)
        if dc_count > cols * rows:
            rows = int(math.ceil(dc_count / cols))

        dc_w = cols * container_len + max(0, cols - 1) * dc_gap
        dc_h = rows * container_w + max(0, rows - 1) * dc_gap
        skid_w = container_len if spec.show_skid else 0.0
        skid_h = container_w if spec.show_skid else 0.0

        content_w = dc_w + (ac_gap if spec.show_skid else 0.0) + skid_w
        content_h = max(dc_h, skid_h)

        block_w = content_w + (inner_pad * 2) + (perimeter_px * 2)
        block_h = title_h + dim_band_h + content_h + label_h + (perimeter_px * 2) + 24

        blocks.append(
            {
                "block_index": block_index,
                "dc_count": dc_count,
                "cols": cols,
                "rows": rows,
                "dc_w": dc_w,
                "dc_h": dc_h,
                "content_w": content_w,
                "content_h": content_h,
                "block_w": block_w,
                "block_h": block_h,
            }
        )
        max_block_width = max(max_block_width, block_w)

    height = top_margin * 2 + sum(b["block_h"] for b in blocks) + max(0, len(blocks) - 1) * gap_y
    width = left_margin * 2 + max_block_width

    dwg = svgwrite.Drawing(
        filename=str(out_svg),
        size=(f"{width}px", f"{height}px"),
        viewBox=f"0 0 {width} {height}",
    )
    dwg.add(
        dwg.style(
            f"""
svg {{ font-family: {LAYOUT_FONT_FAMILY}; font-size: {LAYOUT_FONT_SIZE}px; }}
.outline {{ stroke: #000000; stroke-width: {LAYOUT_STROKE_OUTLINE}; fill: none; }}
.thin {{ stroke: #000000; stroke-width: {LAYOUT_STROKE_THIN}; fill: none; }}
.dash {{ stroke: #000000; stroke-width: {LAYOUT_STROKE_OUTLINE}; fill: none; stroke-dasharray: {LAYOUT_DASH_ARRAY}; }}
.label {{ fill: #000000; }}
.title {{ font-size: {LAYOUT_FONT_SIZE_TITLE}px; font-weight: bold; }}
.dim-text {{ fill: #000000; font-size: {LAYOUT_FONT_SIZE_SMALL}px; }}
"""
        )
    )
    dwg.add(dwg.rect(insert=(0, 0), size=(width, height), fill="#ffffff"))

    block_title_template = spec.labels.get("block_title") if isinstance(spec.labels, dict) else None
    bess_text_template = spec.labels.get("bess_range_text") if isinstance(spec.labels, dict) else None
    skid_text = spec.labels.get("skid_text") if isinstance(spec.labels, dict) else None
    skid_subtext = spec.labels.get("skid_subtext") if isinstance(spec.labels, dict) else None
    if not block_title_template:
        block_title_template = "Block {index}: DC Blocks={dc_blocks}"
    if not bess_text_template:
        bess_text_template = "BESS {start}~{end}"
    if not skid_text:
        skid_text = "PCS&MVT SKID"

    block_offset = 0
    current_y = top_margin
    for block in blocks:
        block_index = block["block_index"]
        dc_count = block["dc_count"]
        cols = block["cols"]
        rows = block["rows"]
        dc_w = block["dc_w"]
        dc_h = block["dc_h"]

        block_x = left_margin
        block_y = current_y
        if perimeter_px > 0:
            dwg.add(dwg.rect(insert=(block_x, block_y), size=(block["block_w"], block["block_h"]), class_="dash"))

        start = block_offset + 1
        end = block_offset + dc_count
        block_offset += dc_count

        try:
            title_text = block_title_template.format(index=block_index, dc_blocks=dc_count, start=start, end=end)
        except Exception:
            title_text = block_title_template
        dwg.add(dwg.text(title_text, insert=(block_x + 6, block_y + 16), class_="label title"))

        content_x = block_x + perimeter_px + inner_pad
        content_y = block_y + perimeter_px + title_h + dim_band_h + 6

        dc_array_x = content_x
        dc_array_y = content_y

        for r in range(rows):
            for c in range(cols):
                idx = r * cols + c
                if idx >= dc_count:
                    continue
                cell_x = dc_array_x + c * (container_len + dc_gap)
                cell_y = dc_array_y + r * (container_w + dc_gap)
                if use_template and dc_template_uri and not spec.dc_block_mirrored:
                    dwg.add(
                        dwg.image(
                            href=dc_template_uri,
                            insert=(cell_x, cell_y),
                            size=(container_len, container_w),
                        )
                    )
                    _draw_dc_interior(dwg, cell_x, cell_y, container_len, container_w, mirrored=False)
                else:
                    dwg.add(
                        dwg.rect(
                            insert=(cell_x, cell_y),
                            size=(container_len, container_w),
                            class_="outline",
                        )
                    )
                    _draw_dc_interior(
                        dwg, cell_x, cell_y, container_len, container_w, mirrored=spec.dc_block_mirrored
                    )
                dwg.add(dwg.text("", insert=(cell_x + 6, cell_y + 18), class_="label"))

        bess_text = bess_text_template.format(start=start, end=end)
        dwg.add(dwg.text(bess_text, insert=(dc_array_x, dc_array_y + dc_h + 18), class_="label"))

        if spec.show_skid:
            skid_x = dc_array_x + dc_w + ac_gap
            skid_y = dc_array_y
            if use_template and ac_template_uri:
                dwg.add(
                    dwg.image(
                        href=ac_template_uri,
                        insert=(skid_x, skid_y),
                        size=(container_len, container_w),
                    )
                )
            else:
                dwg.add(dwg.rect(insert=(skid_x, skid_y), size=(container_len, container_w), class_="outline"))
            _draw_ac_interior(dwg, skid_x, skid_y, container_len, container_w, skid_text)
            if skid_subtext:
                dwg.add(dwg.text(skid_subtext, insert=(skid_x + 6, skid_y + container_w - 10), class_="dim-text"))

        dim_y_main = dc_array_y - 6
        dim_y_secondary = dim_y_main - 16
        dc_text = _format_clearance(spec.dc_to_dc_clearance_m)
        ac_text = _format_clearance(spec.dc_to_ac_clearance_m)

        if cols > 1:
            x1 = dc_array_x + container_len
            x2 = dc_array_x + container_len + dc_gap
            _draw_h_dimension(dwg, x1, x2, dim_y_main, dc_array_y, dc_text)
        if rows > 1:
            y1 = dc_array_y + container_w
            y2 = dc_array_y + container_w + dc_gap
            _draw_v_dimension(dwg, y1, y2, dc_array_x - 6, dc_array_x, dc_text)

        if spec.show_skid:
            x1 = dc_array_x + dc_w
            x2 = dc_array_x + dc_w + ac_gap
            _draw_h_dimension(dwg, x1, x2, dim_y_secondary if cols > 1 else dim_y_main, dc_array_y, ac_text)

        current_y += block["block_h"] + gap_y

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

    if template_warning and png_warning:
        return out_svg, f"{template_warning} {png_warning}"
    return out_svg, template_warning or png_warning
