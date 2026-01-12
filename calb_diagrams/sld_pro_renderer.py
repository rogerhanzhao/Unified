# -*- coding: utf-8 -*-
"""
sld_pro_renderer.py
-------------------
用于渲染“专业版”单线图（SLD）SVG/PNG 的渲染器。

本文件特点：
1) 尽量保持你原有的绘制风格（svgwrite + class 样式）
2) 对 DC switch（开关+Fuse）符号做了重写：符合参考图、可控尺寸、可延长引线
3) 修复曾出现的 NameError：避免模块 import 时执行依赖局部变量的绘图语句
4) 增加中文注释，便于后续你/团队维护
"""

import math
from pathlib import Path
from typing import List, Tuple

try:  # pragma: no cover - optional dependency
    import svgwrite
except Exception:  # pragma: no cover
    svgwrite = None

try:
    import cairosvg
except Exception:  # pragma: no cover - optional dependency
    cairosvg = None

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

# =============================================================================
# 安全转换 / 格式化工具
# =============================================================================


def _safe_float(value, default=0.0) -> float:
    """把 value 安全转成 float，失败返回 default。"""
    try:
        return float(value)
    except Exception:
        return default


def _safe_int(value, default=0) -> int:
    """把 value 安全转成 int，失败返回 default。"""
    try:
        return int(value)
    except Exception:
        return default


def format_mva(value) -> str:
    v = _safe_float(value, 0.0)
    return "TBD" if v <= 0 else f"{v:.1f} MVA"


def format_kv(value) -> str:
    v = _safe_float(value, 0.0)
    return "TBD" if v <= 0 else f"{v:.1f} kV"


def format_v(value) -> str:
    v = _safe_float(value, 0.0)
    return "TBD" if v <= 0 else f"{v:.0f} V"


def format_percent(value) -> str:
    v = _safe_float(value, 0.0)
    return "TBD" if v <= 0 else f"{v:.1f}%"


def format_mwh(value) -> str:
    v = _safe_float(value, 0.0)
    return "TBD" if v <= 0 else f"{v:.3f} MWh"


def format_kv_plain(value) -> str:
    """kV 简写：如 35kV / 33.0kV"""
    v = _safe_float(value, 0.0)
    if v <= 0:
        return "TBD"
    if abs(v - round(v)) < 1e-3:
        return f"{int(round(v))}kV"
    return f"{v:.1f}kV"


def format_v_plain(value) -> str:
    """V 简写（你原来逻辑里 >=1000 仍用 V 显示，这里保持一致）"""
    v = _safe_float(value, 0.0)
    return "TBD" if v <= 0 else f"{v:.0f}V"


def _estimate_current_a(power_kw: float, voltage_v: float) -> float:
    """三相交流电流估算：I = P / (sqrt(3)*V)"""
    if power_kw <= 0 or voltage_v <= 0:
        return 0.0
    return power_kw * 1000.0 / (math.sqrt(3) * voltage_v)


def _estimate_dc_current_a(power_kw: float, voltage_v: float) -> float:
    """直流电流估算：I = P / V"""
    if power_kw <= 0 or voltage_v <= 0:
        return 0.0
    return power_kw * 1000.0 / voltage_v


def _pick_pcs_rating_kw(spec: SldGroupSpec) -> float:
    """从 pcs_rating_kw_list 里取第一个有效值。"""
    for rating in spec.pcs_rating_kw_list:
        if rating:
            return rating
    return 0.0


# =============================================================================
# 通用绘图基础元件（节点/线/符号）
# =============================================================================


def _draw_pcs_dc_ac_symbol(dwg, x: float, y: float, w: float, h: float) -> None:
    """
    PCS 方框内部的“DC/AC 转换”符号（对角线 + 左下 DC 双线 + 右上正弦波）
    """
    if w <= 0 or h <= 0:
        return

    # padding：保证符号不要贴边
    pad = min(w, h) * 0.12
    inner_x = x + pad
    inner_y = y + pad
    inner_w = max(1.0, w - pad * 2)
    inner_h = max(1.0, h - pad * 2)

    # 1) 对角转换斜线（IEC 常见表达）
    dwg.add(
        dwg.line(
            (inner_x, inner_y),
            (inner_x + inner_w, inner_y + inner_h),
            class_="thin",
        )
    )

    # 2) DC 双线（左下）
    dc_len = inner_w * 0.35
    dc_x1 = inner_x
    dc_x2 = inner_x + dc_len
    dc_y_base = inner_y + inner_h - inner_h * 0.18
    dc_gap = inner_h * 0.12
    dwg.add(dwg.line((dc_x1, dc_y_base), (dc_x2, dc_y_base), class_="thin"))
    dwg.add(dwg.line((dc_x1, dc_y_base - dc_gap), (dc_x2, dc_y_base - dc_gap), class_="thin"))

    # 3) AC 正弦波（右上）
    ac_x1 = inner_x + inner_w * 0.65
    ac_x2 = inner_x + inner_w
    wave_w = max(1.0, ac_x2 - ac_x1)
    wave_amp = inner_h * 0.12
    wave_mid_y = inner_y + inner_h * 0.18

    points = []
    steps = 6
    for idx in range(steps + 1):
        t = idx / steps
        px = ac_x1 + t * wave_w
        py = wave_mid_y + math.sin(t * math.pi * 2) * wave_amp
        points.append((px, py))
    dwg.add(dwg.polyline(points=points, class_="thin", fill="none"))


def _draw_breaker_x(dwg, x: float, y: float, size: float) -> None:
    """画一个 X（常用于断路器/隔离点标识）"""
    half = size * 0.5
    dwg.add(dwg.line((x - half, y - half), (x + half, y + half), class_="thin"))
    dwg.add(dwg.line((x - half, y + half), (x + half, y - half), class_="thin"))


def _draw_contact_bar(dwg, x: float, y: float, length: float, line_class: str = "thin") -> None:
    """画触点横杠（居中）。"""
    if length <= 0:
        return
    half = length / 2
    dwg.add(dwg.line((x - half, y), (x + half, y), class_=line_class))


def _draw_open_circle(dwg, x: float, y: float, r: float, line_class: str = "thin") -> None:
    """画空心圆（可用于端子/测点）"""
    if r <= 0:
        return
    dwg.add(dwg.circle(center=(x, y), r=r, class_=line_class))


def _draw_triangle_down(dwg, x: float, y: float, size: float) -> None:
    """画向下三角形"""
    half = size * 0.6
    points = [(x, y + size), (x - half, y), (x + half, y)]
    dwg.add(dwg.polygon(points=points, class_="thin", fill="none"))


def _draw_triangle_up(dwg, x: float, y: float, size: float) -> None:
    """画向上三角形"""
    half = size * 0.6
    points = [(x, y - size), (x - half, y), (x + half, y)]
    dwg.add(dwg.polygon(points=points, class_="thin", fill="none"))


def _draw_triangle_pair(dwg, x: float, y_center: float, size: float, gap: float) -> None:
    """画上下成对三角形（你图里类似二极管/方向组件符号）"""
    top_apex = y_center - gap / 2
    bottom_apex = y_center + gap / 2
    _draw_triangle_down(dwg, x, top_apex - size, size)
    _draw_triangle_up(dwg, x, bottom_apex + size, size)


def _draw_breaker_circle(dwg, x: float, y: float, r: float) -> None:
    """圆圈里画 X 的断路器符号"""
    if r <= 0:
        return
    dwg.add(dwg.circle(center=(x, y), r=r, class_="outline"))
    dwg.add(dwg.line((x - r * 0.7, y - r * 0.7), (x + r * 0.7, y + r * 0.7), class_="thin"))
    dwg.add(dwg.line((x - r * 0.7, y + r * 0.7), (x + r * 0.7, y - r * 0.7), class_="thin"))


def _draw_transformer_symbol(dwg, x: float, y: float, r: float) -> tuple[tuple[float, float], tuple[float, float]]:
    """
    画一个三绕组/三相变压器简图（你原版的三圆+三角）
    返回：左右两个圆心（用于后续引线定位）
    """
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


def _draw_node(dwg, x: float, y: float, r: float, fill: str) -> None:
    """空心节点（outline 样式）"""
    dwg.add(dwg.circle(center=(x, y), r=r, class_="outline", fill=fill))


def _draw_solid_node(dwg, x: float, y: float, r: float, fill: str) -> None:
    """实心节点（用于强显示连接点）"""
    dwg.add(dwg.circle(center=(x, y), r=r, fill=fill, stroke=fill, stroke_width=0.6))


def _snap_point(point: tuple[float, float], anchor: tuple[float, float], tol: float = 0.5) -> tuple[float, float]:
    """
    “吸附”点：如果点坐标跟 anchor 很接近（在 tol 内），则强制改为 anchor
    用于避免线端点因为浮点误差导致看起来没贴上。
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
    """画线（可选吸附起点/终点）"""
    if start_anchor is not None:
        start = _snap_point(start, start_anchor, tol)
    if end_anchor is not None:
        end = _snap_point(end, end_anchor, tol)
    dwg.add(dwg.line(start, end, class_=class_))


def _draw_ground(dwg, x: float, y: float) -> None:
    """接地符号"""
    dwg.add(dwg.line((x, y), (x, y + 6), class_="thin"))
    dwg.add(dwg.line((x - 6, y + 6), (x + 6, y + 6), class_="thin"))
    dwg.add(dwg.line((x - 4, y + 9), (x + 4, y + 9), class_="thin"))
    dwg.add(dwg.line((x - 2, y + 12), (x + 2, y + 12), class_="thin"))


def _draw_capacitor(dwg, x: float, y: float, w: float, gap: float) -> None:
    """电容符号（两条平行线）"""
    dwg.add(dwg.line((x - w / 2, y), (x + w / 2, y), class_="thin"))
    dwg.add(dwg.line((x - w / 2, y + gap), (x + w / 2, y + gap), class_="thin"))

# =============================================================================
# PCS-AC Switch
# =============================================================================
def _draw_ac_knife_switch(dwg, x: float, y: float, h: float, side: int = 1) -> dict[str, tuple[float, float]]:
    """
    AC 侧刀闸（简化 IEC 风格）：顶部固定触点横线 + 斜刀片（断开）
    x,y：符号顶部中心点
    h：符号高度
    side：1 表示刀片向右倾斜；-1 表示向左
    """
    if h <= 0:
        return {"top": (x, y), "bottom": (x, y)}

    contact_y = y + h * 0.25
    pivot_y = y + h * 0.55
    bottom_y = y + h

    contact_w = max(10.0, h * 0.55)
    blade_dx = side * (h * 0.30)   # 水平长度
    blade_dy = h * 0.22            # 竖向下落（角度）

    # 顶部引线到触点
    dwg.add(dwg.line((x, y), (x, contact_y), class_="thin"))
    # 固定触点横线
    dwg.add(dwg.line((x - contact_w/2, contact_y), (x + contact_w/2, contact_y), class_="thin"))

    # 主干到 pivot
    dwg.add(dwg.line((x, contact_y), (x, pivot_y), class_="thin"))
    # 断开刀片（从 pivot 斜向一侧）
    dwg.add(dwg.line((x, pivot_y), (x + blade_dx, pivot_y + blade_dy), class_="thin"))

    # 从 pivot 到底部引线（让它串联进回路）
    dwg.add(dwg.line((x, pivot_y), (x, bottom_y), class_="thin"))

    return {"top": (x, y), "bottom": (x, bottom_y), "contact": (x, contact_y), "pivot": (x, pivot_y)}
def _draw_ac_knife_switch_inline(
    dwg, x: float, y: float, h: float, side: int = 1
    ) -> dict[str, tuple[float, float]]:
    """
    画“目标图2风格”的 AC 刀闸：在主竖线上画一个斜刀片，不画固定触点横线。
    x,y：符号顶部中心点（从这里往下占用高度 h）
    side：1 刀片向右上挑；-1 刀片向左上挑
    """
    if h <= 0:
        return {"top": (x, y), "bottom": (x, y), "pivot": (x, y)}

    top_y = y
    pivot_y = y + h * 0.55
    bottom_y = y + h

    # 主竖线（符号内部这一段）
    dwg.add(dwg.line((x, top_y), (x, bottom_y), class_="thin"))

    # 斜刀片：从 pivot 向“上方侧边”挑起（开断状态）
    blade_dx = side * (h * 0.40)
    blade_dy = h * 0.28
    dwg.add(dwg.line((x, pivot_y), (x + blade_dx, pivot_y - blade_dy), class_="thin"))

    return {"top": (x, top_y), "pivot": (x, pivot_y), "bottom": (x, bottom_y)}
def _draw_arrow_box(dwg, x: float, y: float, w: float, h: float) -> None:
    dwg.add(dwg.rect(insert=(x - w / 2, y), size=(w, h), class_="outline"))
    dwg.add(dwg.line((x, y + 4), (x, y + h - 6), class_="thin"))
    dwg.add(dwg.line((x, y + h - 6), (x - 4, y + h - 10), class_="thin"))
    dwg.add(dwg.line((x, y + h - 6), (x + 4, y + h - 10), class_="thin"))
# =============================================================================
# DC Switch（开关 + Fuse）符号：重写版（关键修复点）
# =============================================================================
def _draw_dc_switch(
    dwg,
    x: float,
    y: float,
    h: float,
    *,
    lead_end_y: float | None = None,
) -> float:
    """
    画 DC switch（开刀闸 + 串联 Fuse）符号，并画顶部/底部引线。

    目标外观（对应你参考图）：
      - 顶部固定触点：短横杠（T 形触点的横杠部分）
      - 开刀闸：从 pivot 点向左上斜出，不接触顶部横杠（表示“断开”）
      - 从 pivot 向下的竖线接到 Fuse 顶部
      - Fuse：小矩形（按你最新要求：Fuse 内部不画两条竖线）
      - 底部引线：从 Fuse 底部延长到 lead_end_y（或 y+h）

    参数：
      x,y  : 顶部连接点坐标
      h    : 符号“名义高度”（决定内部比例）
      lead_end_y : 如果要把符号底部引线拉到某个 bus（例如 branch_bus_y），传这个值

    返回值：
      bottom_y：底部引线最终结束 y，用于调试/对齐
    """
    if h <= 0:
        return y

    # bottom_y：如果外部希望连接到 branch bus，就用 lead_end_y
    bottom_y = (y + h) if lead_end_y is None else max(lead_end_y, y + h * 0.6)

    # 垂直比例（按参考图调过）
    contact_y = y + h * 0.18
    pivot_y = y + h * 0.42
    fuse_top = y + h * 0.62
    fuse_h = max(8.0, min(h * 0.20, h * 0.30))
    
# 需求：fuse 高度变为原来的 2 倍
    fuse_h = fuse_h * 2.0

# 防止 fuse 太长把符号挤爆：限制 fuse 不超过总高度的一半（可再调）
    fuse_h = min(fuse_h, h * 0.55)
    fuse_bot = fuse_top + fuse_h

    # 保险：防止 h 很小时 fuse 顶到底太靠下
    if fuse_bot > y + h * 0.92:
        fuse_top = y + h * 0.55
        fuse_bot = fuse_top + fuse_h

    # 水平比例
    contact_w = max(10.0, min(h * 0.42, h * 0.60))
    fuse_w = max(8.0, fuse_h * 0.55)

    # 刀闸开口方向：左上
    # 刀闸“红线”长度：缩短 1/3 => 乘以 2/3
    blade_dx = h * 0.32 * (2.0 / 3.0)

    # 刀闸张开角度变小：竖向偏移也调小（你可在 0.06~0.10 之间试）
    blade_dy = h * 0.08

    # 刀闸尖端坐标（向左 + 向下）
    blade_tip_x = x - blade_dx
    blade_tip_y = contact_y + blade_dy

    # A) 顶部引线：x,y → contact_y
    _draw_line_anchored(
        dwg,
        (x, y),
        (x, contact_y),
        class_="thin",
        start_anchor=(x, y),
        end_anchor=(x, contact_y),
    )

    # B) 固定触点横杠（不画竖线连接到 pivot，留空表示断开）
    dwg.add(dwg.line((x - contact_w / 2, contact_y), (x + contact_w / 2, contact_y), class_="thin"))

    # C) pivot → fuse_top 的竖线（开关动触点杆）
    _draw_line_anchored(
        dwg,
        (x, pivot_y),
        (x, fuse_top),
        class_="thin",
        start_anchor=(x, pivot_y),
        end_anchor=(x, fuse_top),
    )

    # D) 斜刀闸（pivot → 左上 blade_tip）
    dwg.add(dwg.line((x, pivot_y), (blade_tip_x, blade_tip_y), class_="thin"))

    # E) Fuse 矩形（按要求不画内部竖线）
    dwg.add(dwg.rect(insert=(x - fuse_w / 2, fuse_top), size=(fuse_w, fuse_bot - fuse_top), class_="outline"))

    # F) Fuse 底部引线：fuse_bot → bottom_y（保证连接到 branch bus / DC Block）
    _draw_line_anchored(
        dwg,
        (x, fuse_bot),
        (x, bottom_y),
        class_="thin",
        start_anchor=(x, fuse_bot),
        end_anchor=(x, bottom_y),
    )

    return bottom_y


# =============================================================================
# 其他组合符号 / 文字排版工具
# =============================================================================


def _wrap_text(text: str, max_chars: int) -> List[str]:
    """按单词分行，近似控制每行字符数。"""
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
    """粗略估算某段宽度可容纳字符数（你原逻辑保留）"""
    return max(6, int(width_px / 7))


def _table_row_lines(text: str, max_chars: int) -> List[str]:
    value = str(text or "TBD")
    lines = _wrap_text(value, max_chars)
    return lines if lines else ["TBD"]


def _rmu_class_kv(mv_kv: float) -> float:
    """按常见 RMU 标准档位归类"""
    if mv_kv <= 24:
        return 24.0
    if mv_kv <= 36:
        return 36.0
    return round(mv_kv)


def _range_text(values: List[float], unit: str) -> str:
    """把一组数表示成 min-max"""
    if not values:
        return "TBD"
    minimum = min(values)
    maximum = max(values)
    if abs(maximum - minimum) < 1e-6:
        return f"{minimum:.0f} {unit}"
    return f"{minimum:.0f}-{maximum:.0f} {unit}"


def _split_pcs_groups(pcs_count: int) -> tuple[list[int], list[int]]:
    """把 PCS 分成 A/B 两组（用于 DC Busbar A/B）"""
    if pcs_count <= 0:
        return [], []
    split = int(math.ceil(pcs_count / 2))
    return list(range(1, split + 1)), list(range(split + 1, pcs_count + 1))


# =============================================================================
# Dark mode 设备清单（保持你原有结构）
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


def _build_dark_equipment_sections(spec: SldGroupSpec) -> list[tuple[str, list[str]]]:
    equipment = spec.equipment_list or {}
    rmu = equipment.get("rmu", {}) if isinstance(equipment.get("rmu"), dict) else {}
    transformer = equipment.get("transformer", {}) if isinstance(equipment.get("transformer"), dict) else {}
    lv_bus = equipment.get("lv_busbar", {}) if isinstance(equipment.get("lv_busbar"), dict) else {}
    cables = equipment.get("cables", {}) if isinstance(equipment.get("cables"), dict) else {}
    dc_fuse = equipment.get("dc_fuse", {}) if isinstance(equipment.get("dc_fuse"), dict) else {}

    hz_value = _safe_float(equipment.get("project_hz"), 0.0)
    hz_text = f"{hz_value:.0f}Hz" if hz_value > 0 else "50/60Hz"

    mv_cable_spec = cables.get("mv_cable_spec")
    if not mv_cable_spec:
        mv_kv_text = format_kv_plain(spec.mv_voltage_kv)
        mv_cable_spec = f"XLPE/Cu-{mv_kv_text}" if mv_kv_text != "TBD" else "TBD"

    lv_cable_spec = cables.get("lv_cable_spec") or "TBD"

    dc_voltage_v = _safe_float(equipment.get("dc_block_voltage_v"), 0.0)
    dc_voltage_text = f"{dc_voltage_v:.0f}V" if dc_voltage_v > 0 else "TBD"
    dc_cable_spec = cables.get("dc_cable_spec")
    if not dc_cable_spec:
        if dc_voltage_v > 0:
            dc_cable_spec = f"XLPE/Cu-DC-{dc_voltage_v / 1000.0:.1f}kV"
        else:
            dc_cable_spec = "TBD"

    rated_kv = _safe_float(rmu.get("rated_kv"), 0.0)
    if rated_kv <= 0:
        rated_kv = _rmu_class_kv(spec.mv_voltage_kv)
    rated_a = _safe_float(rmu.get("rated_a"), 0.0)
    short_ka = _safe_float(rmu.get("short_circuit_ka_3s"), 0.0)
    ct_ratio = rmu.get("ct_ratio") or "TBD"
    ct_class = rmu.get("ct_class") or "TBD"
    ct_va = _safe_float(rmu.get("ct_va"), 0.0)
    ct_va_text = f"{ct_va:.0f}VA" if ct_va > 0 else "TBD VA"

    kv_text = f"{rated_kv:.0f}kV" if rated_kv > 0 else "TBD kV"
    a_text = f"{rated_a:.0f}A" if rated_a > 0 else "TBD A"
    ka_text = f"{short_ka:.1f}kA/3s" if short_ka > 0 else "TBD kA/3s"
    rmu_lines = [
        f"LBS: {kv_text}, {a_text}, {ka_text}",
        f"CB: {kv_text}, {a_text}, {ka_text}",
        f"CT: {ct_ratio}, {ct_class}, {ct_va_text}",
        "With DS, ES, & Live Display",
    ]

    tr_lines = []
    tr_kva = spec.transformer_mva * 1000.0 if spec.transformer_mva > 0 else 0.0
    tr_line1 = f"{tr_kva:.0f} kVA" if tr_kva > 0 else "TBD kVA"
    vector = transformer.get("vector_group") or spec.transformer_vector_group
    if vector:
        tr_line1 = f"{tr_line1}, {vector}"
    tr_lines.append(tr_line1)

    tap_range = transformer.get("tap_range")
    mv_lv_text = f"{format_kv_plain(spec.mv_voltage_kv)}/{format_v_plain(spec.lv_voltage_v_ll)}"
    if tap_range:
        mv_lv_text = f"{format_kv_plain(spec.mv_voltage_kv)}{tap_range}/{format_v_plain(spec.lv_voltage_v_ll)}"
    tr_lines.append(mv_lv_text)

    uk = transformer.get("uk_percent")
    if uk is None:
        uk = spec.transformer_uk_percent
    cooling = transformer.get("cooling")
    tr_tail = []
    if uk:
        tr_tail.append(f"Ud={format_percent(uk)}")
    if cooling:
        tr_tail.append(str(cooling))
    tr_lines.append(", ".join(tr_tail) if tr_tail else "TBD")

    lv_rated_a = _safe_float(lv_bus.get("rated_a"), 0.0)
    if lv_rated_a <= 0 and spec.transformer_mva > 0:
        lv_rated_a = _estimate_current_a(spec.transformer_mva * 1000.0, spec.lv_voltage_v_ll)
    lv_rated_a = round(lv_rated_a / 10.0) * 10 if lv_rated_a > 0 else 0.0
    lv_ka = _safe_float(lv_bus.get("short_circuit_ka"), 0.0)
    lv_rated_text = f"{lv_rated_a:.0f}A" if lv_rated_a > 0 else "TBD A"
    lv_ka_text = f"{lv_ka:.1f}kA" if lv_ka > 0 else "TBD kA"
    copper_line = f"AC{format_v_plain(spec.lv_voltage_v_ll)}, {lv_rated_text}, {lv_ka_text}"

    pcs_rating_kw = _pick_pcs_rating_kw(spec)
    pcs_rating_text = f"{pcs_rating_kw:.0f}kW" if pcs_rating_kw > 0 else "TBD"
    pcs_count = max(1, _safe_int(spec.pcs_count, 1))

    cb_current = _estimate_current_a(pcs_rating_kw, spec.lv_voltage_v_ll)
    cb_current = round(cb_current / 10.0) * 10 if cb_current > 0 else 0.0
    cb_current_text = f"{cb_current:.0f}A" if cb_current > 0 else "TBD A"
    cb_ka_text = lv_ka_text if lv_ka > 0 else "TBD kA"
    pcs_lines = [
        f"CB: AC{format_v_plain(spec.lv_voltage_v_ll)}, {cb_current_text}, {cb_ka_text}",
        f"PCS-{pcs_rating_text} x {pcs_count}",
        f"AC{format_v_plain(spec.lv_voltage_v_ll)}/{hz_text}, DC{dc_voltage_text}",
    ]

    dc_current = _estimate_dc_current_a(pcs_rating_kw, dc_voltage_v)
    if dc_voltage_v > 0 and dc_current > 0:
        pcs_lines.append(f"DS: DC{dc_voltage_text}, {dc_current:.0f}A")
    else:
        pcs_lines.append("DS: TBD")

    fuse_spec = dc_fuse.get("fuse_spec") or ""
    if fuse_spec:
        pcs_lines.append(f"FUSE: {fuse_spec}")
    elif dc_voltage_v > 0:
        pcs_lines.append(f"FUSE: DC{dc_voltage_text}, TBD")
    else:
        pcs_lines.append("FUSE: TBD")

    dc_blocks_total = _safe_int(spec.dc_blocks_total_in_group, 0)
    bess_line = f"1~{dc_blocks_total} BESS" if dc_blocks_total > 0 else "BESS TBD"

    sections = [
        ("Power Cable", [mv_cable_spec]),
        ("Ring Main Unit (SF6)", rmu_lines),
        ("Power Cable", [lv_cable_spec]),
        ("Step-up Transformer (OIL)", tr_lines),
        ("Connecting Copper Tape", [copper_line]),
        ("Power Converter System (PCS)", pcs_lines),
        ("Power Cable", [dc_cable_spec]),
        ("Battery Storage Bank (BAT)", [bess_line]),
    ]
    return sections


def _build_equipment_list(spec: SldGroupSpec, compact_mode: bool = False) -> List[Tuple[str, str]]:
    """非 dark_mode 的设备清单（保持你原结构）"""
    if compact_mode:
        return _build_compact_equipment_list(spec)

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


# =============================================================================
# PNG 导出
# =============================================================================


def _write_png(svg_path: Path, png_path: Path) -> None:
    """SVG → PNG（依赖 cairosvg）"""
    if cairosvg is None:
        raise ImportError("cairosvg is required to export PNG from SVG.")
    cairosvg.svg2png(url=str(svg_path), write_to=str(png_path))


# =============================================================================
# 主渲染入口：render_sld_pro_svg
# =============================================================================


def render_sld_pro_svg(
    spec: SldGroupSpec, out_svg: Path, out_png: Path | None = None
) -> tuple[Path | None, str | None]:
    """
    渲染 SLD Pro SVG（可选输出 PNG）。
    返回：(out_svg_path, png_warning_message)
    """
    if svgwrite is None:
        return None, "Missing dependency: svgwrite. Please install: pip install svgwrite"

    out_svg = Path(out_svg)

    # ---------------------------
    # layout_params：所有可调参数集中在这里
    # ---------------------------
    layout_params = spec.layout_params if isinstance(spec.layout_params, dict) else {}
    compact_mode = bool(layout_params.get("compact_mode"))
    theme = str(layout_params.get("theme") or "light").lower()
    dark_mode = theme.startswith("dark")

    # dark_mode 默认不画 summary（你原逻辑保留，可手动 override）
    if "draw_summary" in layout_params:
        draw_summary = bool(layout_params.get("draw_summary"))
    else:
        draw_summary = not dark_mode

    # SVG 尺寸/列布局
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

    # ---------------------------------------
    # 设备清单区域高度计算
    # ---------------------------------------
    item_col_w = 150
    spec_col_w = table_w - item_col_w
    rows = []
    dark_sections = []
    dark_section_gap = 0
    dark_list_pad_y = 0
    dark_detail_indent = 0

    if dark_mode:
        max_chars = _approx_chars(table_w - 28)
        dark_section_gap = 6
        dark_list_pad_y = 12
        dark_detail_indent = 12
        for title, lines in _build_dark_equipment_sections(spec):
            wrapped_lines = []
            for line in lines:
                wrapped_lines.extend(_wrap_text(line, max_chars))
            dark_sections.append({"title": title, "lines": wrapped_lines})
        if not dark_sections:
            dark_sections = [{"title": "Equipment List", "lines": ["TBD"]}]
        total_lines = sum(1 + len(section["lines"]) for section in dark_sections)
        table_h = dark_list_pad_y * 2 + total_lines * row_h + (len(dark_sections) - 1) * dark_section_gap
    else:
        items = _build_equipment_list(spec, compact_mode)
        item_chars = _approx_chars(item_col_w)
        spec_chars = _approx_chars(spec_col_w)
        for item, spec_text in items:
            item_lines = _table_row_lines(item, item_chars)
            spec_lines = _table_row_lines(spec_text, spec_chars)
            rows.append({"item_lines": item_lines, "spec_lines": spec_lines, "lines": max(len(item_lines), len(spec_lines))})
        table_h = title_h + header_h + sum(row["lines"] * row_h for row in rows)

    # ---------------------------------------
    # 图形布局参数（你原结构保留，只做少量整理）
    # ---------------------------------------
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

    # MV/LV 链条 y 坐标
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

    # LV busbar y
    bus_y = tr_top_y + tr_radius * 2 + 80.0
    pcs_bus_gap = _safe_float(layout_params.get("pcs_bus_gap"), 32.0)
    pcs_y = bus_y + pcs_bus_gap

    dc_blocks_total = _safe_int(spec.dc_blocks_total_in_group, 0)
    battery_x = skid_x + battery_pad
    battery_w = diagram_width - battery_pad * 2

    # ---------------------------------------
    # DC Block 区域布局
    # ---------------------------------------
    if compact_mode:
        dc_bus_y = pcs_y + pcs_box_h + 30
        skid_h = max(360.0, dc_bus_y - skid_y + 50)

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

        allocation_parts = [
            f"F{idx + 1}={spec.dc_blocks_per_feeder[idx] if idx < len(spec.dc_blocks_per_feeder) else 0}"
            for idx in range(pcs_count)
        ]
        allocation_text = ", ".join(allocation_parts) if allocation_parts else "TBD"
        summary_lines = [
            f"Battery Storage Bank: {dc_blocks_total} blocks @ {format_mwh(spec.dc_block_energy_mwh)} each",
            f"PCS count: {pcs_count}, LV {format_v(spec.lv_voltage_v_ll)}",
            f"Allocation: {allocation_text}",
        ]
    else:
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

        show_individual_blocks = 0 < dc_blocks_total <= 6
        blocks_to_draw = dc_blocks_total if show_individual_blocks else 1
        block_cols = min(3, blocks_to_draw) if show_individual_blocks else 1
        block_rows = int(math.ceil(blocks_to_draw / block_cols)) if show_individual_blocks else 1
        block_gap_x = 20.0
        block_gap_y = 16.0
        block_area_w = max(220.0, battery_w - 80.0)
        dc_box_w = min(160.0, max(110.0, (block_area_w - (block_cols - 1) * block_gap_x) / block_cols))
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

    # ---------------------------------------
    # Summary note（右下角）
    # ---------------------------------------
    wrapped_lines = []
    note_w = note_h = note_x = note_y = 0.0
    if draw_summary:
        for line in summary_lines:
            wrapped_lines.extend(_wrap_text(line, 64))
        note_w = min(480.0, diagram_width * 0.9)
        note_h = 24 + len(wrapped_lines) * 18
        note_x = diagram_right - note_w
        note_y = battery_y + battery_h + 24

    # SVG 画布高度
    diagram_bottom = battery_y + battery_h + 40
    height = max(table_y + table_h + 40, diagram_bottom)
    if draw_summary:
        height = max(height, note_y + note_h + 40)

    # ---------------------------------------
    # 初始化 SVG
    # ---------------------------------------
    dwg = svgwrite.Drawing(
        filename=str(out_svg),
        size=(f"{width}px", f"{height}px"),
        viewBox=f"0 0 {width} {height}",
    )

    # 颜色/样式（light vs dark）
    outline_color = "#e5e7eb" if dark_mode else "#000000"
    thin_color = "#cbd5e1" if dark_mode else "#000000"
    thick_color = "#e5e7eb" if dark_mode else "#000000"
    dash_color = "#22d3ee" if dark_mode else "#000000"
    busbar_color = "#ef4444" if dark_mode else "#000000"
    label_color = "#e5e7eb" if dark_mode else "#000000"
    title_color = "#f8fafc" if dark_mode else "#000000"
    bg_color = "#0b0f13" if dark_mode else "#ffffff"

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
    dwg.add(dwg.rect(insert=(0, 0), size=(width, height), fill=bg_color))

    # ---------------------------------------
    # 左侧设备清单绘制
    # ---------------------------------------
    if dark_mode:
        list_pad_x = 10
        dwg.add(dwg.rect(insert=(table_x, table_y), size=(table_w, table_h), class_="outline"))
        current_y = table_y + 12
        for idx, section in enumerate(dark_sections):
            current_y += row_h
            dwg.add(dwg.text(section["title"], insert=(table_x + list_pad_x, current_y - 3), class_="label title"))
            for line in section["lines"]:
                current_y += row_h
                dwg.add(
                    dwg.text(
                        line,
                        insert=(table_x + list_pad_x + 12, current_y - 3),
                        class_="label small",
                    )
                )
            if idx < len(dark_sections) - 1:
                current_y += 6
                sep_y = current_y - 3
                dwg.add(dwg.line((table_x, sep_y), (table_x + table_w, sep_y), class_="thin"))
    else:
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

    # ---------------------------------------
    # 右侧框：AC Block（PCS&MV SKID）
    # ---------------------------------------
    dwg.add(dwg.rect(insert=(skid_x, skid_y), size=(diagram_width, skid_h), class_="dash"))
    if dark_mode:
        dwg.add(dwg.text("AC Block (PCS&MV SKID)", insert=(skid_x + diagram_width - 8, skid_y + 18), class_="label title", text_anchor="end"))
    else:
        dwg.add(dwg.text("PCS&MVT SKID (AC Block)", insert=(skid_x + 8, skid_y + 18), class_="label title"))

    # MV labels（保持你原逻辑）
    mv_labels = spec.equipment_list.get("mv_labels") if isinstance(spec.equipment_list, dict) else {}
    to_switchgear = mv_labels.get("to_switchgear") if isinstance(mv_labels, dict) else None
    to_other_rmu = mv_labels.get("to_other_rmu") if isinstance(mv_labels, dict) else None
    if not to_switchgear:
        to_switchgear = f"To {format_kv_plain(spec.mv_voltage_kv)} Switchgear" if dark_mode else f"To {format_kv(spec.mv_voltage_kv)} Switchgear"
    if not to_other_rmu:
        to_other_rmu = "To Other RMU"

    hv_bus_span = _safe_float(layout_params.get("hv_bus_span"), diagram_width * 0.45)
    hv_bus_span = max(220.0, min(hv_bus_span, diagram_width - skid_pad * 2))
    hv_bus_left = mv_center_x - hv_bus_span / 2
    hv_bus_right = mv_center_x + hv_bus_span / 2

    terminal_y = skid_y + max(56.0, skid_pad)
    terminal_left_x = hv_bus_left
    terminal_right_x = hv_bus_right
    dwg.add(dwg.text(to_switchgear, insert=(terminal_left_x - 10, terminal_y - 18), class_="label"))
    dwg.add(dwg.text(to_other_rmu, insert=(terminal_right_x + 10, terminal_y - 18), class_="label", text_anchor="end"))

    # 画 MV busbar
    busbar_left_x = hv_bus_left
    busbar_right_x = hv_bus_right
    dwg.add(dwg.line((busbar_left_x, mv_bus_y), (busbar_right_x, mv_bus_y), class_="thick"))

    # 下面这部分（RMU、MV chain、Transformer、LV busbar、PCS）基本保持你原实现
    # 为了可运行性，这里继续复用你原绘制结构（略做注释与轻微整理）

    node_fill = label_color
    switch_contact_r = _safe_float(layout_params.get("switch_contact_r"), 2.4)
    switch_contact_bar_len = _safe_float(layout_params.get("switch_contact_bar_len"), 10.0)
    switch_contact_circle_r = _safe_float(layout_params.get("switch_contact_circle_r"), 0.0)
    switch_contact_circle_gap = _safe_float(layout_params.get("switch_contact_circle_gap"), 1.0)
    ground_contact_bar_len = _safe_float(layout_params.get("ground_switch_contact_bar_len"), switch_contact_bar_len)
    mv_bus_node_r = _safe_float(layout_params.get("mv_bus_node_r"), 3.0)
    mv_bus_x_offset = _safe_float(layout_params.get("mv_bus_x_offset"), 8.0)
    mv_bus_x_size = _safe_float(layout_params.get("mv_bus_x_size"), 6.0)

    # ---------------------------
    # 复用你原来的“开关链条”绘制函数
    # ---------------------------
    def _draw_open_switches_vertical(
        dwg,
        x: float,
        y_top: float,
        y_bottom: float,
        switches: list[dict],
        line_class: str,
        contact_style: str,
        contact_r: float,
        contact_fill: str,
    ) -> None:
        """沿竖直方向画一串开关/隔离点（你原逻辑，轻微注释）"""
        if y_bottom < y_top:
            y_top, y_bottom = y_bottom, y_top
        current_y = y_top
        for sw in sorted(switches, key=lambda item: item.get("y", 0.0)):
            pivot_y = _safe_float(sw.get("y"), current_y)
            pivot_y = min(max(pivot_y, current_y + 1.0), y_bottom - 1.0)

            gap = max(4.0, _safe_float(sw.get("gap"), 6.0))
            blade_dx = max(6.0, _safe_float(sw.get("blade_dx"), gap * 1.2))
            blade_dy = max(3.0, _safe_float(sw.get("blade_dy"), gap * 0.6))
            contact_bar_len = _safe_float(sw.get("contact_bar_len"), 0.0)
            contact_circle_r = _safe_float(sw.get("contact_circle_r"), 0.0)
            contact_circle_gap = _safe_float(sw.get("contact_circle_gap"), 1.0)

            _draw_line_anchored(dwg, (x, current_y), (x, pivot_y), class_=line_class, start_anchor=(x, current_y), end_anchor=(x, pivot_y))
            dwg.add(dwg.line((x, pivot_y), (x + blade_dx, pivot_y + blade_dy), class_=line_class))

            contact_y = min(y_bottom, pivot_y + gap)
            # contact_style 目前只支持 cross/dot；其他值=不画触点
            if contact_style == "cross":
                _draw_breaker_x(dwg, x, contact_y, contact_r * 2.0)
            elif contact_style == "dot":
                _draw_solid_node(dwg, x, contact_y, contact_r, contact_fill)

            if contact_bar_len > 0:
                _draw_contact_bar(dwg, x, contact_y, contact_bar_len, line_class)
            if contact_circle_r > 0:
                circle_y = contact_y - contact_circle_gap - contact_circle_r
                _draw_open_circle(dwg, x, circle_y, contact_circle_r, line_class)

            current_y = contact_y

        if current_y < y_bottom:
            _draw_line_anchored(dwg, (x, current_y), (x, y_bottom), class_=line_class, start_anchor=(x, current_y), end_anchor=(x, y_bottom))

    def _draw_breaker_with_isolators(dwg, x: float, y: float, r: float, bar_len: float, bar_gap: float, line_class: str) -> None:
        """断路器（圆圈X）上下加隔离横杠"""
        half = bar_len / 2
        dwg.add(dwg.line((x - half, y - bar_gap), (x + half, y - bar_gap), class_=line_class))
        dwg.add(dwg.line((x - half, y + bar_gap), (x + half, y + bar_gap), class_=line_class))
        _draw_breaker_circle(dwg, x, y, r)

    # ---------------------------
    # Incoming RMU lines（两侧）
    # ---------------------------
    incoming_span = mv_bus_y - terminal_y
    incoming_breaker_y = terminal_y + incoming_span * 0.35
    incoming_ground_y = terminal_y + incoming_span * 0.60
    incoming_disconnector_offset = _safe_float(layout_params.get("rmu_disconnector_offset"), 16.0)
    incoming_disconnector_y = mv_bus_y - incoming_disconnector_offset

    incoming_gap = _safe_float(layout_params.get("rmu_switch_gap"), 7.0)
    incoming_blade_dx = abs(_safe_float(layout_params.get("rmu_switch_blade_dx"), 10.0))
    incoming_breaker_r = _safe_float(layout_params.get("rmu_breaker_r"), 6.0)
    incoming_bar_len = _safe_float(layout_params.get("rmu_breaker_bar_len"), 14.0)
    incoming_bar_gap = _safe_float(layout_params.get("rmu_breaker_bar_gap"), 6.0)
    incoming_ground_branch = _safe_float(layout_params.get("rmu_ground_branch"), 16.0)
    incoming_ground_len = _safe_float(layout_params.get("rmu_ground_len"), 18.0)
    incoming_ground_gap = _safe_float(layout_params.get("rmu_ground_gap"), 6.0)
    incoming_ground_blade_dx = abs(_safe_float(layout_params.get("rmu_ground_blade_dx"), 8.0))

    for idx, tap_x in enumerate((terminal_left_x, terminal_right_x)):
        blade_dx = incoming_blade_dx if idx == 0 else -incoming_blade_dx
        _draw_open_switches_vertical(
            dwg,
            tap_x,
            terminal_y,
            mv_bus_y,
            [{"y": incoming_disconnector_y, "gap": incoming_gap, "blade_dx": blade_dx}],
            line_class="thin",
            contact_style="none",
            contact_r=switch_contact_r,
            contact_fill=node_fill,
        )
        _draw_breaker_with_isolators(dwg, tap_x, incoming_breaker_y, incoming_breaker_r, incoming_bar_len, incoming_bar_gap, "thin")

        branch_dir = -1.0 if idx == 0 else 1.0
        branch_x = tap_x + branch_dir * incoming_ground_branch
        dwg.add(dwg.line((tap_x, incoming_ground_y), (branch_x, incoming_ground_y), class_="thin"))
        _draw_open_switches_vertical(
            dwg,
            branch_x,
            incoming_ground_y,
            incoming_ground_y + incoming_ground_len,
            [{"y": incoming_ground_y + incoming_ground_len * 0.35, "gap": incoming_ground_gap, "blade_dx": branch_dir * incoming_ground_blade_dx, "contact_bar_len": ground_contact_bar_len}],
            line_class="thin",
            contact_style="none",
            contact_r=switch_contact_r,
            contact_fill=node_fill,
        )
        _draw_ground(dwg, branch_x, incoming_ground_y + incoming_ground_len + 2.0)

    dwg.add(dwg.text("RMU", insert=(terminal_left_x - 26, terminal_y + 10), class_="label"))

    # ---------------------------
    # MV center chain
    # ---------------------------
    mv_disconnector_offset = _safe_float(layout_params.get("mv_disconnector_offset"), 14.0)
    mv_disconnector_y = mv_bus_y + mv_disconnector_offset

    mv_breaker_r = _safe_float(layout_params.get("mv_breaker_r"), 6.0)
    mv_bar_len = _safe_float(layout_params.get("mv_breaker_bar_len"), 14.0)
    mv_bar_gap = _safe_float(layout_params.get("mv_breaker_bar_gap"), 6.0)

    mv_ground_offset = _safe_float(layout_params.get("mv_ground_offset"), 14.0)
    mv_ground_y = mv_bus_y + mv_ground_offset
    mv_ground_branch = _safe_float(layout_params.get("mv_ground_branch"), 16.0)
    mv_ground_len = _safe_float(layout_params.get("mv_ground_len"), 18.0)
    mv_ground_gap = _safe_float(layout_params.get("mv_ground_gap"), 6.0)
    mv_ground_blade_dx = abs(_safe_float(layout_params.get("mv_ground_blade_dx"), 8.0))
    mv_ground_y = min(max(mv_ground_y, mv_disconnector_y + 6.0), breaker_y - 6.0)

    _draw_open_switches_vertical(
        dwg,
        mv_center_x,
        mv_bus_y,
        equip_y,
        [{"y": mv_disconnector_y, "gap": mv_ground_gap, "blade_dx": -abs(mv_ground_blade_dx), "contact_bar_len": switch_contact_bar_len, "contact_circle_r": switch_contact_circle_r, "contact_circle_gap": switch_contact_circle_gap}],
        line_class="thin",
        contact_style="none",
        contact_r=switch_contact_r,
        contact_fill=node_fill,
    )

    _draw_solid_node(dwg, mv_center_x, mv_bus_y, mv_bus_node_r, node_fill)
    _draw_breaker_x(dwg, mv_center_x, mv_bus_y + mv_bus_x_offset, mv_bus_x_size)

    _draw_breaker_with_isolators(dwg, mv_center_x, breaker_y, mv_breaker_r, mv_bar_len, mv_bar_gap, "thin")

    branch_x = mv_center_x - mv_ground_branch
    dwg.add(dwg.line((mv_center_x, mv_ground_y), (branch_x, mv_ground_y), class_="thin"))
    _draw_open_switches_vertical(
        dwg,
        branch_x,
        mv_ground_y,
        mv_ground_y + mv_ground_len,
        [{"y": mv_ground_y + mv_ground_len * 0.35, "gap": mv_ground_gap, "blade_dx": -abs(mv_ground_blade_dx), "contact_bar_len": ground_contact_bar_len}],
        line_class="thin",
        contact_style="none",
        contact_r=switch_contact_r,
        contact_fill=node_fill,
    )
    _draw_ground(dwg, branch_x, mv_ground_y + mv_ground_len + 2.0)

    # ---------------------------
    # MV equipment row（避雷器、CT、电容/开关）
    # ---------------------------
    equip_span = 60.0
    dwg.add(dwg.line((mv_center_x - equip_span, equip_y), (mv_center_x + equip_span, equip_y), class_="thin"))

    left_box_x = mv_center_x - equip_span
    _draw_arrow_box(dwg, left_box_x, equip_y + 6, 14.0, 22.0)
    _draw_ground(dwg, left_box_x, equip_y + 30)

    ct_y = equip_y + 10
    for offset in (-12, 0, 12):
        dwg.add(dwg.circle(center=(mv_center_x + offset, ct_y), r=3.5, class_="outline"))

    right_x = mv_center_x + equip_span
    _draw_capacitor(dwg, right_x, equip_y + 4, 14.0, 5.0)
    _draw_breaker_circle(dwg, right_x, equip_y + 16, 6.0)
    _draw_ground(dwg, right_x, equip_y + 26)

    # ---------------------------
    # Transformer + LV busbar
    # ---------------------------
    tr_center_x = gap_center
    dwg.add(dwg.line((mv_center_x, equip_y), (mv_center_x, tr_top_y - tr_radius), class_="thin"))
    _draw_triangle_down(dwg, mv_center_x, tr_top_y - tr_radius - 8, 8.0)
    left_center, right_center = _draw_transformer_symbol(dwg, tr_center_x, tr_top_y, tr_radius)

    tx_lv_spacing = _safe_float(layout_params.get("tx_lv_spacing"), 14.0)
    requested_gap = _safe_float(layout_params.get("lv_bus_gap"), 0.0)
    if requested_gap <= 0:
        requested_gap = _safe_float(layout_params.get("lv_bus_coupler_r"), 0.0) * 2
    if requested_gap > 0:
        tx_lv_spacing = requested_gap / 2
    tx_lv_spacing = min(18.0, max(12.0, tx_lv_spacing))

    tx_lv_start_y = left_center[1] + tr_radius
    tx_lv_left_start = (tr_center_x - tx_lv_spacing, tx_lv_start_y)
    tx_lv_right_start = (tr_center_x + tx_lv_spacing, tx_lv_start_y)
    tx_lv_left = (tr_center_x - tx_lv_spacing, bus_y)
    tx_lv_right = (tr_center_x + tx_lv_spacing, bus_y)

    _draw_line_anchored(dwg, tx_lv_left_start, tx_lv_left, class_="thick", start_anchor=tx_lv_left_start, end_anchor=tx_lv_left)
    _draw_line_anchored(dwg, tx_lv_right_start, tx_lv_right, class_="thick", start_anchor=tx_lv_right_start, end_anchor=tx_lv_right)

    # Transformer text
    tr_text_x = tr_center_x + tr_radius * 2 + 90
    tr_text_y = max(tr_top_y - tr_radius - 6, equip_y + 8)
    tr_lines = [
        "Transformer",
        f"{format_kv(spec.mv_voltage_kv)}/{format_v(spec.lv_voltage_v_ll)}",
        format_mva(spec.transformer_mva),
    ]
    if spec.transformer_vector_group:
        tr_lines.append(str(spec.transformer_vector_group))
    if spec.transformer_uk_percent:
        tr_lines.append(f"Uk={format_percent(spec.transformer_uk_percent)}")
    cooling = spec.equipment_list.get("transformer", {}).get("cooling") if isinstance(spec.equipment_list, dict) else None
    if cooling:
        tr_lines.append(str(cooling))
    for idx, line in enumerate(tr_lines):
        dwg.add(dwg.text(line, insert=(tr_text_x, tr_text_y + idx * 16), class_="label"))

    # LV busbar line(s)
    bus_x1 = skid_x + skid_pad
    bus_x2 = skid_x + diagram_width - skid_pad
    busbar_class = "busbar" if dark_mode else "thick"

    lv_bus_split = bool(layout_params.get("lv_bus_split", True))
    if lv_bus_split:
        dwg.add(dwg.line((bus_x1, bus_y), (tx_lv_left[0], bus_y), class_=busbar_class))
        dwg.add(dwg.line((tx_lv_right[0], bus_y), (bus_x2, bus_y), class_=busbar_class))
    else:
        dwg.add(dwg.line((bus_x1, bus_y), (bus_x2, bus_y), class_=busbar_class))
    dwg.add(dwg.text("LV Busbar", insert=(bus_x1, bus_y - 8), class_="label"))

    # ---------------------------
    # PCS box + AC tap
    # ---------------------------
    pcs_label_offset = _safe_float(layout_params.get("pcs_label_offset"), 10.0)
    lv_tap_nodes = bool(layout_params.get("lv_tap_nodes", False))
    lv_node_r = 3.0
    pcs_tap_node_r = _safe_float(layout_params.get("pcs_tap_node_r"), 2.6)
    pcs_ac_x_offset = _safe_float(layout_params.get("pcs_ac_x_offset"), 8.0)
    pcs_ac_x_size = _safe_float(layout_params.get("pcs_ac_x_size"), 6.0)
    pcs_ac_switch_offset = _safe_float(layout_params.get("pcs_ac_switch_offset"), 18.0)
    pcs_ac_switch_gap = _safe_float(layout_params.get("pcs_ac_switch_gap"), 5.0)
    pcs_ac_switch_blade_dx = _safe_float(layout_params.get("pcs_ac_switch_blade_dx"), 10.0)

    _draw_solid_node(dwg, tx_lv_left[0], tx_lv_left[1], lv_node_r, node_fill)
    _draw_solid_node(dwg, tx_lv_right[0], tx_lv_right[1], lv_node_r, node_fill)

    for idx in range(pcs_count):
        pcs_center_x = pcs_centers[idx]
        pcs_left_x = pcs_center_x - pcs_box_w / 2

        dwg.add(dwg.rect(insert=(pcs_left_x, pcs_y), size=(pcs_box_w, pcs_box_h), class_="outline"))

        if compact_mode:
            label_y = bus_y + pcs_label_offset
            label_x = pcs_center_x + 6
            dwg.add(dwg.text(f"PCS-{idx + 1}", insert=(label_x, label_y), class_="label", text_anchor="start"))
            _draw_pcs_dc_ac_symbol(dwg, pcs_left_x + pcs_box_w * 0.08, pcs_y + pcs_box_h * 0.18, pcs_box_w * 0.84, pcs_box_h * 0.74)
        else:
            dwg.add(dwg.text(f"PCS-{idx + 1}", insert=(pcs_center_x + 6, pcs_y + 20), class_="label", text_anchor="start"))
            rating = spec.pcs_rating_kw_list[idx] if idx < len(spec.pcs_rating_kw_list) else 0.0
            rating_text = f"{rating:.0f} kW" if rating else "TBD"
            dwg.add(dwg.text(rating_text, insert=(pcs_center_x + 6, pcs_y + 38), class_="label", text_anchor="start"))

                # ---------------------------
        # ---------------------------
               # ---------------------------
        # AC tap chain（目标：图2那种竖直串联：● → X → 刀闸 → PCS）
        # ---------------------------

        tap = (pcs_center_x, bus_y)     # 母排连接点
        pcs_in = (pcs_center_x, pcs_y)  # PCS 方框上边缘

        # 1) 母排节点（实心点）
        _draw_solid_node(dwg, tap[0], tap[1], pcs_tap_node_r, node_fill)

        # 2) X（米字）位置：先定义，避免 NameError
        x_mark_y = bus_y + pcs_ac_x_offset
        _draw_line_anchored(
            dwg, tap, (pcs_center_x, x_mark_y),
            class_="thin",
            start_anchor=tap, end_anchor=(pcs_center_x, x_mark_y),
        )
        _draw_breaker_x(dwg, pcs_center_x, x_mark_y, pcs_ac_x_size)

        # 3) 刀闸放在 X 下面（竖直串联，不要任何侧向横线）
        knife_top_y = x_mark_y + max(5.0, pcs_ac_switch_offset)

        # 刀闸高度（可用 layout_params 覆盖）
        knife_h = _safe_float(layout_params.get("pcs_ac_knife_h"), 22.0)
        knife_h = max(14.0, min(28.0, knife_h))

        # 防止刀闸/引线压到 PCS 框：把刀闸底部限制在 pcs_y - 2 之上
        max_bottom = pcs_y - 2.0
        if knife_top_y + knife_h > max_bottom:
            knife_h = max(10.0, max_bottom - knife_top_y)

        # X → 刀闸顶部
        _draw_line_anchored(
            dwg,
            (pcs_center_x, x_mark_y),
            (pcs_center_x, knife_top_y),
            class_="thin",
            start_anchor=(pcs_center_x, x_mark_y),
            end_anchor=(pcs_center_x, knife_top_y),
        )

        # 刀片方向：让刀片“向外”开，避免压到 PCS 文本（左边的向左，右边的向右）
        side = -1 if pcs_center_x < mv_center_x else 1

        anchors = _draw_ac_knife_switch_inline(dwg, pcs_center_x, knife_top_y, knife_h, side=side)

        # 刀闸底部 → PCS 顶部
        _draw_line_anchored(
            dwg,
            anchors["bottom"],
            pcs_in,
            class_="thin",
            start_anchor=anchors["bottom"],
            end_anchor=pcs_in,
        )

    # =============================================================================
    # 下方：Battery Storage Bank（compact_mode vs full）
    # =============================================================================
    if compact_mode:
        # battery 边框
        dwg.add(dwg.rect(insert=(battery_x, battery_y), size=(battery_w, battery_h), class_="dash"))
        if dark_mode:
            dwg.add(dwg.text("DC Block (BESS)", insert=(battery_x + battery_w - 8, battery_y + 16), class_="label title", text_anchor="end"))
        else:
            dwg.add(dwg.text("Battery Storage Bank", insert=(battery_x + 8, battery_y + 16), class_="label title"))

        dc_node_r = 2.5
        dc_triangle_size = _safe_float(layout_params.get("dc_triangle_size"), 8.0)
        dc_triangle_gap = _safe_float(layout_params.get("dc_triangle_gap"), 4.0)

        # 你可以通过 layout_params 强制 DC switch 高度（不用改代码）
        forced_symbol_h = _safe_float(layout_params.get("dc_switch_symbol_h"), 0.0)

        for idx in range(pcs_count):
            line_x = pcs_centers[idx]
            dc_top = pcs_y + pcs_box_h

            per_feeder = per_feeder_counts[idx] if idx < len(per_feeder_counts) else 1
            block_count = max(1, min(per_feeder, max_blocks))

            stack_h = dc_block_h * block_count + dc_block_gap_y * (block_count - 1)
            stack_top_y = dc_box_y + (dc_stack_h - stack_h) / 2

            # branch bus：放在 DC block stack 上方一点点（你原逻辑）
            branch_bus_y = stack_top_y - 10

            # 自动估算符号高度（按可用空间）
            raw_h = branch_bus_y - dc_top
            auto_symbol_h = min(50.0, max(20.0, raw_h * 1.0))
            symbol_h = forced_symbol_h if forced_symbol_h > 0 else auto_symbol_h

            # 关键：把 DC switch 的底部引线直接拉到 branch_bus_y，保证 Fuse → DC Block 连起来
            _draw_dc_switch(dwg, line_x, dc_top, symbol_h, lead_end_y=branch_bus_y)

            # branch bus node
            _draw_node(dwg, line_x, branch_bus_y, dc_node_r, node_fill)

            # 中间三角对（可选）
            triangle_center = battery_y + dc_triangle_size + 6.0
            if triangle_center + dc_triangle_size < branch_bus_y - 2.0:
                _draw_triangle_pair(dwg, line_x, triangle_center, dc_triangle_size, dc_triangle_gap)

            # 多 DC block 时画一小段横母线
            if block_count > 1:
                bus_half = min(16.0, slot_w * 0.18)
                dwg.add(dwg.line((line_x - bus_half, branch_bus_y), (line_x + bus_half, branch_bus_y), class_="thin"))

            # 逐个 DC block 引下去
            for b in range(block_count):
                block_y = stack_top_y + b * (dc_block_h + dc_block_gap_y)
                dc_in = (line_x, block_y)

                _draw_line_anchored(dwg, (line_x, branch_bus_y), dc_in, class_="thin", start_anchor=(line_x, branch_bus_y), end_anchor=dc_in)
                _draw_node(dwg, dc_in[0], dc_in[1], dc_node_r, node_fill)

                # DC block 外框
                dwg.add(dwg.rect(insert=(line_x - pcs_box_w * 0.4, block_y), size=(pcs_box_w * 0.8, dc_block_h), class_="outline"))

                # 内部电芯列（保持你原来风格）
                inner_pad = max(10.0, dc_block_h * 0.12)
                usable_h = max(1.0, dc_block_h - inner_pad * 2)
                _draw_battery_column(dwg, line_x, block_y + inner_pad, usable_h, 6)

    else:
        # full mode：保留你原来的 DC BUSBAR A/B、Circuit A/B、block grid 逻辑
        busbar_class = "busbar" if dark_mode else "thick"

        dc_bus_a_y = pcs_y + pcs_box_h + 28
        dc_bus_b_y = dc_bus_a_y + 22
        dwg.add(dwg.line((bus_x1, dc_bus_a_y), (bus_x2, dc_bus_a_y), class_=busbar_class))
        dwg.add(dwg.text("DC BUSBAR A", insert=(bus_x1, dc_bus_a_y - 8), class_="label"))
        dwg.add(dwg.line((bus_x1, dc_bus_b_y), (bus_x2, dc_bus_b_y), class_=busbar_class))
        dwg.add(dwg.text("DC BUSBAR B", insert=(bus_x1, dc_bus_b_y - 8), class_="label"))

        dc_node_r = 2.5
        for idx in range(pcs_count):
            line_x = pcs_centers[idx]
            target_bus_y = dc_bus_a_y if idx < group_split else dc_bus_b_y
            pcs_out = (line_x, pcs_y + pcs_box_h)
            target = (line_x, target_bus_y)
            _draw_line_anchored(dwg, pcs_out, target, class_="thin", start_anchor=pcs_out, end_anchor=target)
            _draw_node(dwg, target[0], target[1], dc_node_r, node_fill)

        # battery 框
        dwg.add(dwg.rect(insert=(battery_x, battery_y), size=(battery_w, battery_h), class_="dash"))
        if dark_mode:
            dwg.add(dwg.text("DC Block (BESS)", insert=(battery_x + battery_w - 8, battery_y + 16), class_="label title", text_anchor="end"))
        else:
            dwg.add(dwg.text("Battery Storage Bank", insert=(battery_x + 8, battery_y + 16), class_="label title"))

        # circuit lines
        circuit_x1 = battery_x + 60
        circuit_x2 = battery_x + battery_w - 60
        dc_circuit_a_y = battery_y + battery_title_h + 18
        dc_circuit_b_y = dc_circuit_a_y + 18

        dwg.add(dwg.line((circuit_x1, dc_circuit_a_y), (circuit_x2, dc_circuit_a_y), class_="thin"))
        dwg.add(dwg.text("Circuit A", insert=(circuit_x1, dc_circuit_a_y - 6), class_="small"))
        dwg.add(dwg.line((circuit_x1, dc_circuit_b_y), (circuit_x2, dc_circuit_b_y), class_="thin"))
        dwg.add(dwg.text("Circuit B", insert=(circuit_x1, dc_circuit_b_y - 6), class_="small"))

        link_x = bus_x2 - 40
        dwg.add(dwg.line((link_x, dc_bus_a_y), (link_x, dc_circuit_a_y), class_="thin"))
        dwg.add(dwg.line((link_x, dc_bus_b_y), (link_x, dc_circuit_b_y), class_="thin"))

        # blocks
        show_individual_blocks = 0 < dc_blocks_total <= 6
        blocks_to_draw = dc_blocks_total if show_individual_blocks else 1
        block_cols = min(3, blocks_to_draw) if show_individual_blocks else 1
        block_rows = int(math.ceil(blocks_to_draw / block_cols)) if show_individual_blocks else 1
        block_gap_x = 20.0
        block_gap_y = 16.0
        block_area_w = max(220.0, battery_w - 80.0)
        dc_box_w = min(160.0, max(110.0, (block_area_w - (block_cols - 1) * block_gap_x) / block_cols))
        dc_box_h = 54
        block_grid_w = block_cols * dc_box_w + max(0, block_cols - 1) * block_gap_x
        block_grid_h = block_rows * dc_box_h + max(0, block_rows - 1) * block_gap_y
        dc_box_x_start = battery_x + (battery_w - block_grid_w) / 2
        dc_box_y = dc_circuit_b_y + 24

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

    # ---------------------------------------
    # 右下角 summary note
    # ---------------------------------------
    if draw_summary:
        dwg.add(dwg.rect(insert=(note_x, note_y), size=(note_w, note_h), class_="outline"))
        dwg.add(dwg.text("Allocation Summary (AC Block group)", insert=(note_x + 8, note_y + 18), class_="label title"))
        for idx, line in enumerate(wrapped_lines):
            dwg.add(dwg.text(line, insert=(note_x + 8, note_y + 36 + idx * 18), class_="label"))

    # 保存 SVG
    out_svg.parent.mkdir(parents=True, exist_ok=True)
    dwg.save()

    # 可选输出 PNG
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


# =============================================================================
# Battery column（保持你原图风格的“电芯列”）
# =============================================================================


def _draw_battery_column(dwg, x: float, y: float, h: float, rows: int) -> None:
    """DC Block 内部的小电芯列：长短横条 + 中间三个小点"""
    if rows <= 0 or h <= 0:
        return
    cell_pitch = h / rows
    long_w = max(8.0, min(16.0, cell_pitch * 0.9))
    short_w = long_w * 0.6
    plate_gap = min(4.0, max(2.0, cell_pitch * 0.2))

    dwg.add(dwg.line((x, y - 2), (x, y + h + 2), class_="thin"))

    for row in range(rows):
        y_center = y + cell_pitch * (row + 0.5)
        y_long = y_center - plate_gap / 2
        y_short = y_center + plate_gap / 2
        dwg.add(dwg.line((x - long_w / 2, y_long), (x + long_w / 2, y_long), class_="thin"))
        dwg.add(dwg.line((x - short_w / 2, y_short), (x + short_w / 2, y_short), class_="thin"))

    dot_gap = min(6.0, max(3.0, cell_pitch * 0.3))
    mid_y = y + h * 0.5
    for offset in (-dot_gap, 0.0, dot_gap):
        dwg.add(dwg.line((x - 1.5, mid_y + offset), (x + 1.5, mid_y + offset), class_="thin"))
