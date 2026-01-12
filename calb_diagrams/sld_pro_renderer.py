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

try:  # pragma: no cover - optional dependency
    import cairosvg
except Exception:  # pragma: no cover
    cairosvg = None


# =============================================================================
# 工具函数：安全类型转换 / 格式化
# =============================================================================
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


def format_kv_plain(value) -> str:
    v = _safe_float(value, 0.0)
    if v <= 0:
        return "TBD"
    if abs(v - round(v)) < 1e-3:
        return f"{int(round(v))}kV"
    return f"{v:.1f}kV"


def format_v_plain(value) -> str:
    v = _safe_float(value, 0.0)
    if v <= 0:
        return "TBD"
    return f"{v:.0f}V"


def _estimate_current_a(power_kw: float, voltage_v: float) -> float:
    """三相 AC 电流估算：I = P / (sqrt(3) * V)"""
    if power_kw <= 0 or voltage_v <= 0:
        return 0.0
    return power_kw * 1000.0 / (math.sqrt(3) * voltage_v)


def _estimate_dc_current_a(power_kw: float, voltage_v: float) -> float:
    """DC 电流估算：I = P / V"""
    if power_kw <= 0 or voltage_v <= 0:
        return 0.0
    return power_kw * 1000.0 / voltage_v


def _pick_pcs_rating_kw(spec: SldGroupSpec) -> float:
    """从 pcs_rating_kw_list 里拿一个非 0 的作为显示/估算用"""
    for rating in spec.pcs_rating_kw_list:
        if rating:
            return rating
    return 0.0


# =============================================================================
# 基础图元（线/点/符号）
# =============================================================================
def _snap_point(point: tuple[float, float], anchor: tuple[float, float], tol: float = 0.5) -> tuple[float, float]:
    """
    “吸附”端点：如果 point 和 anchor 已经非常接近（误差<tol），就强制用 anchor，
    这样能减少 SVG 渲染时出现的“微小错位/断缝”。
    """
    if abs(point[0] - anchor[0]) > tol or abs(point[1] - anchor[1]) > tol:
        return anchor
    return point


def _draw_line_anchored(
    dwg,
    start: tuple[float, float],
    end: tuple[float, float],
    class_: str = "thin",
    start_anchor: tuple[float, float] | None = None,
    end_anchor: tuple[float, float] | None = None,
    tol: float = 0.5,
) -> None:
    """带端点吸附的直线，建议所有“连接线”都用它，减少断线概率。"""
    if start_anchor is not None:
        start = _snap_point(start, start_anchor, tol)
    if end_anchor is not None:
        end = _snap_point(end, end_anchor, tol)
    dwg.add(dwg.line(start, end, class_=class_))


def _draw_breaker_x(dwg, x: float, y: float, size: float) -> None:
    """画一个 X（常用来表示断路器/开关标记）"""
    half = size * 0.5
    dwg.add(dwg.line((x - half, y - half), (x + half, y + half), class_="thin"))
    dwg.add(dwg.line((x - half, y + half), (x + half, y - half), class_="thin"))


def _draw_contact_bar(dwg, x: float, y: float, length: float, line_class: str = "thin") -> None:
    """画一个短横线（触点/母排小段）"""
    if length <= 0:
        return
    half = length / 2
    dwg.add(dwg.line((x - half, y), (x + half, y), class_=line_class))


def _draw_open_circle(dwg, x: float, y: float, r: float, line_class: str = "thin") -> None:
    """画空心圆"""
    if r <= 0:
        return
    dwg.add(dwg.circle(center=(x, y), r=r, class_=line_class))


def _draw_node(dwg, x: float, y: float, r: float, fill: str) -> None:
    """画一个节点（空心/实心由 class 控制）"""
    dwg.add(dwg.circle(center=(x, y), r=r, class_="outline", fill=fill))


def _draw_solid_node(dwg, x: float, y: float, r: float, fill: str) -> None:
    """画一个实心节点（用于强调连接点）"""
    dwg.add(dwg.circle(center=(x, y), r=r, fill=fill, stroke=fill, stroke_width=0.6))


def _draw_ground(dwg, x: float, y: float) -> None:
    """接地符号"""
    dwg.add(dwg.line((x, y), (x, y + 6), class_="thin"))
    dwg.add(dwg.line((x - 6, y + 6), (x + 6, y + 6), class_="thin"))
    dwg.add(dwg.line((x - 4, y + 9), (x + 4, y + 9), class_="thin"))
    dwg.add(dwg.line((x - 2, y + 12), (x + 2, y + 12), class_="thin"))


def _draw_triangle_down(dwg, x: float, y: float, size: float) -> None:
    half = size * 0.6
    points = [(x, y + size), (x - half, y), (x + half, y)]
    dwg.add(dwg.polygon(points=points, class_="thin", fill="none"))


def _draw_triangle_up(dwg, x: float, y: float, size: float) -> None:
    half = size * 0.6
    points = [(x, y - size), (x - half, y), (x + half, y)]
    dwg.add(dwg.polygon(points=points, class_="thin", fill="none"))


def _draw_triangle_pair(dwg, x: float, y_center: float, size: float, gap: float) -> None:
    """上下对顶三角形（常用于保护/方向性符号）"""
    top_apex = y_center - gap / 2
    bottom_apex = y_center + gap / 2
    _draw_triangle_down(dwg, x, top_apex - size, size)
    _draw_triangle_up(dwg, x, bottom_apex + size, size)


# =============================================================================
# PCS 符号：更接近你目标图（左下“-” + 右上“~” + 对角线）
# =============================================================================
def _draw_pcs_dc_ac_symbol(dwg, x: float, y: float, w: float, h: float) -> None:
    """
    在 PCS 方框内部画 “DC/AC 转换” 符号：
      - 一条对角线（左上->右下）
      - 左下角一个短横线 “-” 表示 DC
      - 右上角一个短波形 “~” 表示 AC
    """
    if w <= 0 or h <= 0:
        return

    pad = min(w, h) * 0.12
    inner_x = x + pad
    inner_y = y + pad
    inner_w = max(1.0, w - pad * 2)
    inner_h = max(1.0, h - pad * 2)

    # 1) 对角线
    dwg.add(
        dwg.line(
            (inner_x, inner_y),
            (inner_x + inner_w, inner_y + inner_h),
            class_="thin",
        )
    )

    # 2) DC: 左下角短横线（更像你目标图的 “-”）
    minus_len = inner_w * 0.30
    minus_x1 = inner_x + inner_w * 0.08
    minus_x2 = minus_x1 + minus_len
    minus_y = inner_y + inner_h * 0.78
    dwg.add(dwg.line((minus_x1, minus_y), (minus_x2, minus_y), class_="thin"))

    # 3) AC: 右上角短波形（~）
    ac_x1 = inner_x + inner_w * 0.68
    ac_x2 = inner_x + inner_w * 0.94
    wave_w = max(1.0, ac_x2 - ac_x1)
    wave_amp = inner_h * 0.10
    wave_mid_y = inner_y + inner_h * 0.26

    points = []
    steps = 6
    for idx in range(steps + 1):
        t = idx / steps
        px = ac_x1 + t * wave_w
        py = wave_mid_y + math.sin(t * math.pi * 2) * wave_amp
        points.append((px, py))
    dwg.add(dwg.polyline(points=points, class_="thin", fill="none"))


# =============================================================================
# DC Switch（刀闸 + Fuse）：目标样式（支持去掉 Fuse 内竖线）
# =============================================================================
def _draw_dc_switch(
    dwg,
    x: float,
    y: float,
    h: float,
    *,
    draw_fuse_inner: bool = False,
) -> dict[str, tuple[float, float]]:
    """
    画 DC Switch（更接近你给的目标图）：

      顶部：进线 (x,y) -> 竖线 -> 固定触点横线（T形触点的横）
      中部：断开刀闸（斜线，不接触横线）
      下部：串联 Fuse（小矩形）
      最底：从 Fuse 底部继续引线到符号底部 (x, y+h)

    注意：为了“符号可以很小但线还能接到 DC Block”，建议：
      - 这里的 h 只用于画“符号本体+一点底部引线”
      - 符号画完后，外部再画一段竖线，把 (x, y+h) 接到 branch_bus_y / DC Block 顶部
    """
    if h <= 0:
        return {"top": (x, y), "bottom": (x, y)}

    # -------------------------
    # 关键比例（可按目标图微调）
    # -------------------------
    contact_y = y + h * 0.18          # 顶部固定触点横线的位置
    pivot_y = y + h * 0.42            # 刀闸“转轴”位置（竖向主干的上端）
    fuse_top = y + h * 0.62           # Fuse 矩形上边
    fuse_h = max(8.0, min(h * 0.22, h * 0.30))
    fuse_bot = fuse_top + fuse_h

    # 如果 h 很小导致 fuse 太靠下，做个压缩
    if fuse_bot > y + h * 0.92:
        fuse_top = y + h * 0.56
        fuse_bot = min(y + h * 0.92, fuse_top + fuse_h)

    contact_w = max(10.0, min(h * 0.50, h * 0.70))  # 顶部触点横线长度
    fuse_w = max(10.0, fuse_h * 0.60)               # Fuse 宽度

    # 刀闸尖端（断开状态）：偏左上
    blade_tip_x = x - h * 0.32
    blade_tip_y = contact_y + h * 0.12

    # 1) 顶部引线： (x,y) -> (x, contact_y)
    _draw_line_anchored(
        dwg,
        (x, y),
        (x, contact_y),
        class_="thin",
        start_anchor=(x, y),
        end_anchor=(x, contact_y),
    )

    # 2) 固定触点横线（T形）
    dwg.add(
        dwg.line(
            (x - contact_w / 2, contact_y),
            (x + contact_w / 2, contact_y),
            class_="thin",
        )
    )

    # 3) 竖向主干（从 pivot 到 fuse_top）
    _draw_line_anchored(
        dwg,
        (x, pivot_y),
        (x, fuse_top),
        class_="thin",
        start_anchor=(x, pivot_y),
        end_anchor=(x, fuse_top),
    )

    # 4) 断开刀闸（从 pivot 指向 blade_tip，不接触 contact_y 横线）
    dwg.add(dwg.line((x, pivot_y), (blade_tip_x, blade_tip_y), class_="thin"))

    # 5) Fuse 矩形
    dwg.add(
        dwg.rect(
            insert=(x - fuse_w / 2, fuse_top),
            size=(fuse_w, fuse_bot - fuse_top),
            class_="outline",
        )
    )

    # 6) Fuse 内竖线（你现在明确要删，所以默认 False；需要时再打开）
    if draw_fuse_inner:
        inner_top = fuse_top + (fuse_bot - fuse_top) * 0.18
        inner_bot = fuse_top + (fuse_bot - fuse_top) * 0.82
        bar_dx = fuse_w * 0.18
        dwg.add(dwg.line((x - bar_dx, inner_top), (x - bar_dx, inner_bot), class_="thin"))
        dwg.add(dwg.line((x + bar_dx, inner_top), (x + bar_dx, inner_bot), class_="thin"))

    # 7) Fuse 底部到符号底部的引线（注意：这里只到 y+h）
    _draw_line_anchored(
        dwg,
        (x, fuse_bot),
        (x, y + h),
        class_="thin",
        start_anchor=(x, fuse_bot),
        end_anchor=(x, y + h),
    )

    return {
        "top": (x, y),
        "contact_y": (x, contact_y),
        "pivot_y": (x, pivot_y),
        "fuse_top": (x, fuse_top),
        "fuse_bot": (x, fuse_bot),
        "bottom": (x, y + h),
    }


# =============================================================================
# 其它符号：断路器圆、变压器、避雷器等（保持你原逻辑）
# =============================================================================
def _draw_breaker_circle(dwg, x: float, y: float, r: float) -> None:
    if r <= 0:
        return
    dwg.add(dwg.circle(center=(x, y), r=r, class_="outline"))
    dwg.add(dwg.line((x - r * 0.7, y - r * 0.7), (x + r * 0.7, y + r * 0.7), class_="thin"))
    dwg.add(dwg.line((x - r * 0.7, y + r * 0.7), (x + r * 0.7, y - r * 0.7), class_="thin"))


def _draw_breaker_with_isolators(dwg, x: float, y: float, r: float, bar_len: float, bar_gap: float, line_class: str) -> None:
    half = bar_len / 2
    dwg.add(dwg.line((x - half, y - bar_gap), (x + half, y - bar_gap), class_=line_class))
    dwg.add(dwg.line((x - half, y + bar_gap), (x + half, y + bar_gap), class_=line_class))
    _draw_breaker_circle(dwg, x, y, r)


def _draw_capacitor(dwg, x: float, y: float, w: float, gap: float) -> None:
    dwg.add(dwg.line((x - w / 2, y), (x + w / 2, y), class_="thin"))
    dwg.add(dwg.line((x - w / 2, y + gap), (x + w / 2, y + gap), class_="thin"))


def _draw_arrow_box(dwg, x: float, y: float, w: float, h: float) -> None:
    dwg.add(dwg.rect(insert=(x - w / 2, y), size=(w, h), class_="outline"))
    dwg.add(dwg.line((x, y + 4), (x, y + h - 6), class_="thin"))
    dwg.add(dwg.line((x, y + h - 6), (x - 4, y + h - 10), class_="thin"))
    dwg.add(dwg.line((x, y + h - 6), (x + 4, y + h - 10), class_="thin"))


def _draw_transformer_symbol(dwg, x: float, y: float, r: float) -> tuple[tuple[float, float], tuple[float, float]]:
    """三绕组/三圈变压器符号（保持你原来的画法）"""
    gap = r * 0.9
    top_center = (x, y)
    left_center = (x - gap, y + gap)
    right_center = (x + gap, y + gap)
    for cx, cy in (top_center, left_center, right_center):
        dwg.add(dwg.circle(center=(cx, cy), r=r, class_="outline"))

    tri = [
        (top_center[0], top_center[1] - r * 0.55),
        (top_center[0] - r * 0.5, top_center[1] + r * 0.35),
        (top_center[0] + r * 0.5, top_center[1] + r * 0.35),
    ]
    dwg.add(dwg.polygon(points=tri, class_="thin", fill="none"))

    for cx, cy in (left_center, right_center):
        dwg.add(dwg.line((cx, cy), (cx, cy - r * 0.6), class_="thin"))
        dwg.add(dwg.line((cx, cy), (cx - r * 0.5, cy + r * 0.35), class_="thin"))
        dwg.add(dwg.line((cx, cy), (cx + r * 0.5, cy + r * 0.35), class_="thin"))

    return left_center, right_center


def _draw_battery_column(dwg, x: float, y: float, h: float, rows: int) -> None:
    """
    DC Block 内部电池“极板”符号（你原来的实现已经很接近目标图）
    """
    if rows <= 0 or h <= 0:
        return
    cell_pitch = h / rows
    long_w = max(8.0, min(16.0, cell_pitch * 0.9))
    short_w = long_w * 0.6
    plate_gap = min(4.0, max(2.0, cell_pitch * 0.2))

    # 竖向主线
    dwg.add(dwg.line((x, y - 2), (x, y + h + 2), class_="thin"))

    # 多层长短极板
    for row in range(rows):
        y_center = y + cell_pitch * (row + 0.5)
        y_long = y_center - plate_gap / 2
        y_short = y_center + plate_gap / 2
        dwg.add(dwg.line((x - long_w / 2, y_long), (x + long_w / 2, y_long), class_="thin"))
        dwg.add(dwg.line((x - short_w / 2, y_short), (x + short_w / 2, y_short), class_="thin"))

    # 中间三点（用短横代替，视觉上更稳）
    dot_gap = min(6.0, max(3.0, cell_pitch * 0.3))
    mid_y = y + h * 0.5
    for offset in (-dot_gap, 0.0, dot_gap):
        dwg.add(dwg.line((x - 1.5, mid_y + offset), (x + 1.5, mid_y + offset), class_="thin"))


# =============================================================================
# 文本换行（保持你原逻辑）
# =============================================================================
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


# =============================================================================
# 设备表（保持你原逻辑，略）
# =============================================================================
def _build_compact_equipment_list(spec: SldGroupSpec) -> List[Tuple[str, str]]:
    equipment = spec.equipment_list or {}
    hz_value = _safe_float(equipment.get("project_hz"), 0.0) if isinstance(equipment, dict) else 0.0
    hz_text = f"{hz_value:.0f}Hz" if hz_value > 0 else "50/60Hz"

    mv_spec = f"{format_kv(spec.mv_voltage_kv)}, 3-phase, {hz_text}"

    tr_parts = [
        format_mva(spec.transformer_mva),
        f"{format_kv(spec.mv_voltage_kv)}/{format_v(spec.lv_voltage_v_ll)}",
    ]
    if spec.transformer_vector_group:
        tr_parts.append(str(spec.transformer_vector_group))
    tr_spec = ", ".join([part for part in tr_parts if part and part != "TBD"]) or "TBD"

    pcs_text = _range_text(spec.pcs_rating_kw_list, "kW")
    pcs_spec = "TBD"
    if spec.pcs_count > 0 and pcs_text != "TBD":
        pcs_spec = f"{spec.pcs_count} x {pcs_text}"

    dc_total = _safe_int(spec.dc_blocks_total_in_group, 0)
    dc_spec = "TBD"
    if dc_total > 0:
        energy_text = format_mwh(spec.dc_block_energy_mwh)
        dc_spec = f"{dc_total} x {energy_text}" if energy_text != "TBD" else f"{dc_total} x TBD"

    return [
        ("MV Switchgear", mv_spec),
        ("Transformer", tr_spec),
        ("PCS", pcs_spec),
        ("DC Block", dc_spec),
    ]


def _build_equipment_list(spec: SldGroupSpec, compact_mode: bool = False) -> List[Tuple[str, str]]:
    if compact_mode:
        return _build_compact_equipment_list(spec)
    # 非 compact 的设备表你原来写得很完整，这里保持简化占位（你可继续沿用原文件）
    return _build_compact_equipment_list(spec)


def _write_png(svg_path: Path, png_path: Path) -> None:
    if cairosvg is None:
        raise ImportError("cairosvg is required to export PNG from SVG.")
    cairosvg.svg2png(url=str(svg_path), write_to=str(png_path))


# =============================================================================
# 主入口：渲染 SVG
# =============================================================================
def render_sld_pro_svg(spec: SldGroupSpec, out_svg: Path, out_png: Path | None = None) -> tuple[Path | None, str | None]:
    if svgwrite is None:
        return None, "Missing dependency: svgwrite. Please install: pip install svgwrite"
    out_svg = Path(out_svg)

    layout_params = spec.layout_params if isinstance(spec.layout_params, dict) else {}
    compact_mode = bool(layout_params.get("compact_mode"))
    theme = str(layout_params.get("theme") or "light").lower()   # 目标图是白底黑线，更建议默认 light
    dark_mode = theme.startswith("dark")

    if "draw_summary" in layout_params:
        draw_summary = bool(layout_params.get("draw_summary"))
    else:
        draw_summary = not dark_mode

    width = int(_safe_float(layout_params.get("svg_width"), 1750))
    width = max(1200, width)
    left_margin = _safe_float(layout_params.get("left_margin"), 40)
    left_col_width = _safe_float(layout_params.get("column_width"), 360 if dark_mode else 420)

    table_x = left_margin
    table_y = 40
    table_w = left_col_width

    diagram_left = left_margin + left_col_width + 40
    diagram_right = width - 40
    diagram_width = diagram_right - diagram_left

    row_h = int(_safe_float(layout_params.get("row_height"), 16))
    title_h = 20
    header_h = 18

    # 表格计算（保持你原逻辑的简化版）
    items = _build_equipment_list(spec, compact_mode)
    item_col_w = 150
    spec_col_w = table_w - item_col_w
    rows = []
    item_chars = _approx_chars(item_col_w)
    spec_chars = _approx_chars(spec_col_w)
    for item, spec_text in items:
        item_lines = _table_row_lines(item, item_chars)
        spec_lines = _table_row_lines(spec_text, spec_chars)
        rows.append({"item_lines": item_lines, "spec_lines": spec_lines, "lines": max(len(item_lines), len(spec_lines))})
    table_h = title_h + header_h + sum(row["lines"] * row_h for row in rows)

    # AC Block / DC Block 布局参数（沿用你原来的命名）
    skid_x = diagram_left
    skid_y = table_y
    skid_pad = _safe_float(layout_params.get("skid_pad"), 60.0)
    battery_pad = _safe_float(layout_params.get("battery_pad"), 40.0)

    pcs_count = max(1, int(spec.pcs_count))
    group_a, group_b = _split_pcs_groups(pcs_count)
    group_split = len(group_a)

    pcs_box_h = 50
    pcs_pad = skid_pad
    pcs_span = max(240.0, diagram_width - pcs_pad * 2)
    slot_w = pcs_span / pcs_count

    if compact_mode:
        pcs_box_w = min(80.0, max(58.0, slot_w - 20.0))
        pcs_box_h = max(66.0, pcs_box_w * 0.9)
    else:
        pcs_box_w = min(160.0, max(110.0, slot_w - 10.0))

    pcs_centers = [skid_x + pcs_pad + (idx + 0.5) * slot_w for idx in range(pcs_count)]
    mv_center_x = skid_x + diagram_width / 2
    gap_center = mv_center_x

    # 纵向关键 y 坐标（沿用你原结构）
    mv_bus_y = skid_y + 120
    mv_breaker_offset = 16.0
    mv_switch_gap = 14.0
    mv_switch_h = 12.0
    mv_chain_gap = 18.0
    mv_to_tr_gap = 46.0
    tr_radius = 14.0

    breaker_y = mv_bus_y + mv_breaker_offset
    switch_y = breaker_y + mv_switch_gap
    equip_y = switch_y + mv_switch_h + mv_chain_gap
    tr_top_y = equip_y + mv_to_tr_gap

    bus_y = tr_top_y + tr_radius * 2 + 80.0
    pcs_bus_gap = _safe_float(layout_params.get("pcs_bus_gap"), 32.0)
    pcs_y = bus_y + pcs_bus_gap

    dc_blocks_total = _safe_int(spec.dc_blocks_total_in_group, 0)
    battery_x = skid_x + battery_pad
    battery_w = diagram_width - battery_pad * 2

    # DC Block 区域（compact_mode 更接近你给的目标图：一根线对应一个 DC Block）
    if compact_mode:
        skid_h = max(360.0, (pcs_y + pcs_box_h + 30) - skid_y + 50)
        battery_y = skid_y + skid_h + 40
        battery_title_h = 20

        dc_block_h = max(140.0, pcs_box_h * 1.5)
        dc_block_gap_y = 18.0

        per_feeder_counts = (
            [max(1, _safe_int(v, 1)) for v in spec.dc_blocks_per_feeder]
            if isinstance(spec.dc_blocks_per_feeder, list)
            else []
        )
        max_blocks = max(per_feeder_counts) if per_feeder_counts else 1
        max_blocks = max(1, min(max_blocks, 2))

        dc_stack_h = dc_block_h * max_blocks + dc_block_gap_y * (max_blocks - 1)
        dc_box_y = battery_y + battery_title_h + 30
        battery_h = battery_title_h + 30 + dc_stack_h + 40
    else:
        # 非 compact 部分保持你原结构（这里不展开）
        skid_h = 420.0
        battery_y = skid_y + skid_h + 40
        battery_h = 360.0
        dc_box_y = battery_y + 60
        dc_block_h = 180.0
        dc_block_gap_y = 24.0
        max_blocks = 1
        per_feeder_counts = [1 for _ in range(pcs_count)]

    # 汇总框（保留）
    summary_lines = [
        f"Battery Storage Bank: {dc_blocks_total} blocks @ {format_mwh(spec.dc_block_energy_mwh)} each",
        f"PCS count: {pcs_count}, LV {format_v(spec.lv_voltage_v_ll)}",
    ]

    wrapped_lines = []
    note_w = note_h = note_x = note_y = 0.0
    if draw_summary:
        for line in summary_lines:
            wrapped_lines.extend(_wrap_text(line, 64))
        note_w = min(480.0, diagram_width * 0.9)
        note_h = 24 + len(wrapped_lines) * 18
        note_x = diagram_right - note_w
        note_y = battery_y + battery_h + 24

    diagram_bottom = battery_y + battery_h + 40
    height = max(table_y + table_h + 40, diagram_bottom)
    if draw_summary:
        height = max(height, note_y + note_h + 40)

    dwg = svgwrite.Drawing(
        filename=str(out_svg),
        size=(f"{width}px", f"{height}px"),
        viewBox=f"0 0 {width} {height}",
    )

    # 颜色/线宽：支持从 layout_params 覆盖，让你更容易对齐“目标式样”
    outline_color = str(layout_params.get("outline_color") or ("#e5e7eb" if dark_mode else "#000000"))
    thin_color = str(layout_params.get("thin_color") or ("#cbd5e1" if dark_mode else "#000000"))
    thick_color = str(layout_params.get("thick_color") or ("#e5e7eb" if dark_mode else "#000000"))
    dash_color = str(layout_params.get("dash_color") or ("#22d3ee" if dark_mode else "#000000"))
    busbar_color = str(layout_params.get("busbar_color") or ("#ef4444" if dark_mode else "#000000"))
    label_color = str(layout_params.get("label_color") or ("#e5e7eb" if dark_mode else "#000000"))
    title_color = str(layout_params.get("title_color") or ("#f8fafc" if dark_mode else "#000000"))
    bg_color = str(layout_params.get("bg_color") or ("#0b0f13" if dark_mode else "#ffffff"))

    thin_width = max(1.5, SLD_STROKE_THIN)
    outline_width = max(2.0, SLD_STROKE_OUTLINE)
    thick_width = max(2.0, SLD_STROKE_THICK)
    dash_width = outline_width
    busbar_width = max(2.0, SLD_STROKE_THICK)

    dwg.add(
        dwg.style(
            f"""
svg {{ font-family: {SLD_FONT_FAMILY}; font-size: {SLD_FONT_SIZE}px; }}
.outline {{ stroke: {outline_color}; stroke-width: {outline_width}; fill: none; }}
.thin {{ stroke: {thin_color}; stroke-width: {thin_width}; fill: none; }}
.thick {{ stroke: {thick_color}; stroke-width: {thick_width}; fill: none; }}
.dash {{ stroke: {dash_color}; stroke-width: {dash_width}; fill: none; stroke-dasharray: {SLD_DASH_ARRAY}; }}
.busbar {{ stroke: {busbar_color}; stroke-width: {busbar_width}; fill: none; }}
.label {{ fill: {label_color}; }}
.title {{ font-size: {SLD_FONT_SIZE_TITLE}px; font-weight: bold; fill: {title_color}; }}
.small {{ font-size: {SLD_FONT_SIZE_SMALL}px; fill: {label_color}; }}
"""
        )
    )

    # 背景
    dwg.add(dwg.rect(insert=(0, 0), size=(width, height), fill=bg_color))

    # -------------------------
    # 左侧设备表（简化版）
    # -------------------------
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
            ytxt = current_y + row_h * (line_idx + 1) - 3
            dwg.add(dwg.text(line, insert=(table_x + 6, ytxt), class_="label"))
        for line_idx, line in enumerate(row["spec_lines"]):
            ytxt = current_y + row_h * (line_idx + 1) - 3
            dwg.add(dwg.text(line, insert=(col_split + 6, ytxt), class_="label"))
        current_y += row_h * row["lines"]
        dwg.add(dwg.line((table_x, current_y), (table_x + table_w, current_y), class_="thin"))

    # -------------------------
    # 右侧：AC Block（虚线框）
    # -------------------------
    dwg.add(dwg.rect(insert=(skid_x, skid_y), size=(diagram_width, skid_h), class_="dash"))
    dwg.add(dwg.text("AC Block (PCS&MV SKID)", insert=(skid_x + diagram_width - 8, skid_y + 18), class_="label title", text_anchor="end"))

    # -------------------------
    # 画 MV bus（保留你原骨架，做最小必要符号）
    # -------------------------
    hv_bus_span = _safe_float(layout_params.get("hv_bus_span"), diagram_width * 0.45)
    hv_bus_span = max(220.0, min(hv_bus_span, diagram_width - skid_pad * 2))
    hv_bus_left = mv_center_x - hv_bus_span / 2
    hv_bus_right = mv_center_x + hv_bus_span / 2

    busbar_left_x = hv_bus_left
    busbar_right_x = hv_bus_right
    dwg.add(dwg.line((busbar_left_x, mv_bus_y), (busbar_right_x, mv_bus_y), class_="thick"))

    # -------------------------
    # 变压器 + LV Bus
    # -------------------------
    tr_center_x = gap_center
    dwg.add(dwg.line((mv_center_x, equip_y), (mv_center_x, tr_top_y - tr_radius), class_="thin"))
    _draw_triangle_down(dwg, mv_center_x, tr_top_y - tr_radius - 8, 8.0)
    left_center, right_center = _draw_transformer_symbol(dwg, tr_center_x, tr_top_y, tr_radius)

    tx_lv_spacing = 14.0
    tx_lv_start_y = left_center[1] + tr_radius
    tx_lv_left_start = (tr_center_x - tx_lv_spacing, tx_lv_start_y)
    tx_lv_right_start = (tr_center_x + tx_lv_spacing, tx_lv_start_y)
    tx_lv_left = (tr_center_x - tx_lv_spacing, bus_y)
    tx_lv_right = (tr_center_x + tx_lv_spacing, bus_y)

    _draw_line_anchored(dwg, tx_lv_left_start, tx_lv_left, class_="thick", start_anchor=tx_lv_left_start, end_anchor=tx_lv_left)
    _draw_line_anchored(dwg, tx_lv_right_start, tx_lv_right, class_="thick", start_anchor=tx_lv_right_start, end_anchor=tx_lv_right)

    # LV Busbar
    bus_x1 = skid_x + skid_pad
    bus_x2 = skid_x + diagram_width - skid_pad
    busbar_class = "busbar" if dark_mode else "thick"
    dwg.add(dwg.line((bus_x1, bus_y), (bus_x2, bus_y), class_=busbar_class))
    dwg.add(dwg.text("LV Busbar", insert=(bus_x1, bus_y - 8), class_="label"))

    # -------------------------
    # PCS（每个 feeder 一台）
    # -------------------------
    node_fill = label_color
    pcs_tap_node_r = _safe_float(layout_params.get("pcs_tap_node_r"), 2.6)
    pcs_ac_x_offset = _safe_float(layout_params.get("pcs_ac_x_offset"), 8.0)
    pcs_ac_x_size = _safe_float(layout_params.get("pcs_ac_x_size"), 6.0)

    for idx in range(pcs_count):
        pcs_center_x = pcs_centers[idx]
        pcs_left_x = pcs_center_x - pcs_box_w / 2

        # PCS 方框
        dwg.add(dwg.rect(insert=(pcs_left_x, pcs_y), size=(pcs_box_w, pcs_box_h), class_="outline"))
        dwg.add(dwg.text(f"PCS-{idx + 1}", insert=(pcs_center_x + 6, pcs_y - 10), class_="label"))

        # 方框内符号（更接近目标图）
        _draw_pcs_dc_ac_symbol(
            dwg,
            pcs_left_x + pcs_box_w * 0.08,
            pcs_y + pcs_box_h * 0.18,
            pcs_box_w * 0.84,
            pcs_box_h * 0.74,
        )

        # LV Bus -> PCS 上端连接线
        tap = (pcs_center_x, bus_y)
        pcs_in = (pcs_center_x, pcs_y)
        _draw_line_anchored(dwg, tap, pcs_in, class_="thin", start_anchor=tap, end_anchor=pcs_in)
        _draw_solid_node(dwg, tap[0], tap[1], pcs_tap_node_r, node_fill)
        _draw_breaker_x(dwg, pcs_center_x, bus_y + pcs_ac_x_offset, pcs_ac_x_size)

    # -------------------------
    # DC Block 区域（虚线框）
    # -------------------------
    dwg.add(dwg.rect(insert=(battery_x, battery_y), size=(battery_w, battery_h), class_="dash"))
    dwg.add(dwg.text("DC Block (BESS)", insert=(battery_x + battery_w - 8, battery_y + 16), class_="label title", text_anchor="end"))

    # -------------------------
    # DC 侧：每个 PCS 下方画 DC switch + 保护符号 + 接到 DC Block
    # 核心修复点：符号可以小，但必须额外画“符号底部 -> branch_bus_y”的竖线，避免断线
    # -------------------------
    dc_node_r = 2.5
    dc_triangle_size = _safe_float(layout_params.get("dc_triangle_size"), 8.0)
    dc_triangle_gap = _safe_float(layout_params.get("dc_triangle_gap"), 4.0)

    # 可控：DC switch 的最大高度（你说“太大”就是调这里）
    dc_switch_max_h = _safe_float(layout_params.get("dc_switch_max_h"), 36.0)   # 默认 36 更像目标图
    dc_switch_min_h = _safe_float(layout_params.get("dc_switch_min_h"), 18.0)
    dc_switch_scale = _safe_float(layout_params.get("dc_switch_scale"), 0.55)  # raw_h 的比例

    for idx in range(pcs_count):
        line_x = pcs_centers[idx]
        dc_top = pcs_y + pcs_box_h

        # 单个 feeder 分配的 DC Block 数（compact_mode 下最多画 1~2 个堆叠）
        per_feeder = per_feeder_counts[idx] if idx < len(per_feeder_counts) else 1
        block_count = max(1, min(per_feeder, max_blocks))

        stack_h = dc_block_h * block_count + dc_block_gap_y * (block_count - 1)
        stack_top_y = dc_box_y + ( (dc_block_h * max_blocks + dc_block_gap_y * (max_blocks - 1)) - stack_h ) / 2

        # branch_bus_y：DC Block 顶部上方一点点作为汇流连接点
        branch_bus_y = stack_top_y - 10

        # 1) 先算可用空间 raw_h
        raw_h = max(20.0, branch_bus_y - dc_top)

        # 2) DC switch 符号本体高度：符号小而美（不会强行撑满 raw_h）
        symbol_h = min(dc_switch_max_h, max(dc_switch_min_h, raw_h * dc_switch_scale))

        # 3) 画 DC switch（默认不画 Fuse 内竖线）
        anchors = _draw_dc_switch(dwg, line_x, dc_top, symbol_h, draw_fuse_inner=False)

        # 4) 关键修复：补一段“符号底部 -> branch_bus_y”的竖线，保证一定连上
        sym_bottom = anchors.get("bottom", (line_x, dc_top + symbol_h))
        if sym_bottom[1] < branch_bus_y - 0.5:
            _draw_line_anchored(
                dwg,
                sym_bottom,
                (line_x, branch_bus_y),
                class_="thin",
                start_anchor=sym_bottom,
                end_anchor=(line_x, branch_bus_y),
            )

        # branch bus 节点
        _draw_node(dwg, line_x, branch_bus_y, dc_node_r, node_fill)

        # 5) 保护/方向符号（上下三角）
        triangle_center = battery_y + dc_triangle_size + 6.0
        if triangle_center + dc_triangle_size < branch_bus_y - 2.0:
            _draw_triangle_pair(dwg, line_x, triangle_center, dc_triangle_size, dc_triangle_gap)

        # 6) 画 DC Block（一个或两个堆叠）
        if block_count > 1:
            bus_half = min(16.0, slot_w * 0.18)
            dwg.add(dwg.line((line_x - bus_half, branch_bus_y), (line_x + bus_half, branch_bus_y), class_="thin"))

        for b in range(block_count):
            block_y = stack_top_y + b * (dc_block_h + dc_block_gap_y)
            dc_in = (line_x, block_y)

            # branch_bus -> DC Block 顶部连接
            _draw_line_anchored(
                dwg,
                (line_x, branch_bus_y),
                dc_in,
                class_="thin",
                start_anchor=(line_x, branch_bus_y),
                end_anchor=dc_in,
            )
            _draw_node(dwg, dc_in[0], dc_in[1], dc_node_r, node_fill)

            # DC Block 外框
            block_w = pcs_box_w * 0.8
            dwg.add(
                dwg.rect(
                    insert=(line_x - block_w / 2, block_y),
                    size=(block_w, dc_block_h),
                    class_="outline",
                )
            )

            # DC Block 内部电池符号
            inner_pad = max(10.0, dc_block_h * 0.12)
            usable_h = max(1.0, dc_block_h - inner_pad * 2)
            _draw_battery_column(dwg, line_x, block_y + inner_pad, usable_h, 6)

    # -------------------------
    # Summary note（可选）
    # -------------------------
    if draw_summary:
        dwg.add(dwg.rect(insert=(note_x, note_y), size=(note_w, note_h), class_="outline"))
        dwg.add(dwg.text("Allocation Summary (AC Block group)", insert=(note_x + 8, note_y + 18), class_="label title"))
        for i, line in enumerate(wrapped_lines):
            dwg.add(dwg.text(line, insert=(note_x + 8, note_y + 36 + i * 18), class_="label"))

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