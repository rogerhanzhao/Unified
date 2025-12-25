from pathlib import Path
from typing import Tuple

try:  # pragma: no cover - optional dependency
    import svgwrite
except Exception:  # pragma: no cover
    svgwrite = None

from calb_diagrams.specs import LayoutBlockSpec

try:
    import cairosvg
except Exception:  # pragma: no cover - optional dependency
    cairosvg = None


def _safe_int(value, default=0) -> int:
    try:
        return int(value)
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


def render_layout_block_svg(
    spec: LayoutBlockSpec, out_svg: Path, out_png: Path | None = None
) -> tuple[Path | None, str | None]:
    if svgwrite is None:
        return None, "Missing dependency: svgwrite. Please install: pip install svgwrite"
    out_svg = Path(out_svg)

    block_width = 880
    block_height = 300
    gap_y = 50
    left_margin = 40
    top_margin = 40

    rows_count = len(spec.block_indices_to_render)
    width = block_width + left_margin * 2
    height = top_margin * 2 + rows_count * block_height + max(0, rows_count - 1) * gap_y

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
.dash { stroke: #000000; stroke-width: 1.2; fill: none; stroke-dasharray: 6,4; }
.label { fill: #000000; }
.title { font-size: 13px; font-weight: bold; }
"""
        )
    )

    block_title_template = spec.labels.get("block_title") if isinstance(spec.labels, dict) else None
    bess_text_template = spec.labels.get("bess_range_text") if isinstance(spec.labels, dict) else None
    skid_text = spec.labels.get("skid_text") if isinstance(spec.labels, dict) else None
    if not block_title_template:
        block_title_template = "Block {index}"
    if not bess_text_template:
        bess_text_template = "BESS {start}~{end}"
    if not skid_text:
        skid_text = "PCS&MVT SKID"

    cols, rows = _grid_positions(spec.arrangement)
    dc_blocks_per_block = max(1, _safe_int(spec.dc_blocks_per_block, 4))
    dc_blocks_per_block = max(dc_blocks_per_block, cols * rows)

    for row_idx, block_index in enumerate(spec.block_indices_to_render):
        block_x = left_margin
        block_y = top_margin + row_idx * (block_height + gap_y)
        dwg.add(dwg.rect(insert=(block_x, block_y), size=(block_width, block_height), class_="outline"))

        title_text = block_title_template.format(index=block_index)
        dwg.add(dwg.text(title_text, insert=(block_x + 10, block_y + 20), class_="label title"))

        dc_area_x = block_x + 30
        dc_area_y = block_y + 50
        dc_area_w = 520
        dc_area_h = 200
        dwg.add(dwg.rect(insert=(dc_area_x, dc_area_y), size=(dc_area_w, dc_area_h), class_="dash"))

        cell_w = dc_area_w / cols
        cell_h = dc_area_h / rows

        for r in range(rows):
            for c in range(cols):
                idx = r * cols + c
                if idx >= dc_blocks_per_block:
                    continue
                cell_x = dc_area_x + c * cell_w
                cell_y = dc_area_y + r * cell_h
                dwg.add(
                    dwg.rect(
                        insert=(cell_x + 8, cell_y + 8),
                        size=(cell_w - 16, cell_h - 16),
                        class_="outline",
                    )
                )
                for line_idx in range(1, 4):
                    y = cell_y + 8 + line_idx * (cell_h - 16) / 4
                    dwg.add(
                        dwg.line(
                            (cell_x + 8, y),
                            (cell_x + cell_w - 8, y),
                            class_="thin",
                        )
                    )

        start = (block_index - 1) * dc_blocks_per_block + 1
        end = start + dc_blocks_per_block - 1
        bess_text = bess_text_template.format(start=start, end=end)
        dwg.add(dwg.text(bess_text, insert=(dc_area_x + 10, dc_area_y + dc_area_h + 18), class_="label"))

        if spec.show_skid:
            skid_x = block_x + dc_area_w + 80
            skid_y = dc_area_y + 20
            skid_w = 230
            skid_h = 160
            dwg.add(dwg.rect(insert=(skid_x, skid_y), size=(skid_w, skid_h), class_="outline"))
            dwg.add(dwg.text(skid_text, insert=(skid_x + 10, skid_y + 22), class_="label"))
            if isinstance(spec.labels, dict) and spec.labels.get("skid_subtext"):
                dwg.add(
                    dwg.text(
                        spec.labels.get("skid_subtext"),
                        insert=(skid_x + 10, skid_y + 40),
                        class_="label",
                    )
                )

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
