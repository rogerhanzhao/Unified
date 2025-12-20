from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


AC_BLOCK_CANDIDATES: List[Dict[str, float]] = [
    {"pcs_units": 2, "pcs_unit_kw": 1250, "ac_block_mw": 2.5},
    {"pcs_units": 2, "pcs_unit_kw": 1725, "ac_block_mw": 3.45},
    {"pcs_units": 4, "pcs_unit_kw": 1250, "ac_block_mw": 5.0},
    {"pcs_units": 4, "pcs_unit_kw": 1725, "ac_block_mw": 6.9},
]


def _get_matplotlib():
    try:
        import matplotlib.pyplot as plt  # type: ignore
        from matplotlib.patches import FancyBboxPatch, Rectangle  # type: ignore
    except Exception as exc:  # pragma: no cover - import guard
        raise ImportError(
            "matplotlib is required to render SLD and layout visuals. "
            "Install matplotlib in the Streamlit environment to enable plotting."
        ) from exc
    return plt, FancyBboxPatch, Rectangle


def find_ac_block_container_only(
    poi_mw: float,
    container_cnt: int,
    *,
    search_extra: int = 40,
) -> Optional[Dict[str, Any]]:
    """Find an AC Block configuration assuming only container DC blocks."""
    if container_cnt <= 0:
        return None

    best: Optional[Dict[str, Any]] = None
    best_score: Optional[tuple] = None

    for cand in AC_BLOCK_CANDIDATES:
        p_ac = cand["ac_block_mw"]
        n_min = max(1, int(-(-poi_mw // p_ac)))  # ceil divide without math dependency

        for ac_qty in range(n_min, n_min + search_extra + 1):
            if container_cnt % ac_qty != 0:
                continue
            dc_per_block = container_cnt // ac_qty
            # Exclude exactly 3 DC Blocks per AC Block (design rule)
            if dc_per_block == 3:
                continue
            total_ac = ac_qty * p_ac
            if total_ac < poi_mw:
                continue
            oversize = total_ac - poi_mw
            score = (oversize, ac_qty)
            if best_score is None or score < best_score:
                best_score = score
                best = {
                    "strategy": "container_only",
                    "ac_block_qty": ac_qty,
                    "ac_block_rated_mw": p_ac,
                    "pcs_units": cand["pcs_units"],
                    "pcs_unit_kw": cand["pcs_unit_kw"],
                    "dc_blocks_per_block": dc_per_block,
                    "total_ac_mw": total_ac,
                    "oversize_mw": oversize,
                }
    return best


def find_ac_block_mixed(
    poi_mw: float,
    container_cnt: int,
    cabinet_cnt: int,
    *,
    search_extra: int = 40,
) -> Optional[Dict[str, Any]]:
    """Find an AC Block configuration allowing mixed DC blocks (containers + cabinets)."""
    dc_total = container_cnt + cabinet_cnt
    if dc_total <= 0:
        return None

    best: Optional[Dict[str, Any]] = None
    best_score: Optional[tuple] = None

    for cand in AC_BLOCK_CANDIDATES:
        p_ac = cand["ac_block_mw"]
        n_min = max(1, int(-(-poi_mw // p_ac)))

        for ac_qty in range(n_min, n_min + search_extra + 1):
            cont_per_block = container_cnt // ac_qty
            cab_per_block = cabinet_cnt // ac_qty
            cont_rem = container_cnt % ac_qty
            cab_rem = cabinet_cnt % ac_qty
            base_dc_each = cont_per_block + cab_per_block
            if base_dc_each == 0 and (cont_rem + cab_rem) == 0:
                continue
            max_dc_each = base_dc_each + (1 if cont_rem > 0 or cab_rem > 0 else 0)
            # Exclude any configuration with exactly 3 DC per block
            if base_dc_each == 3 or max_dc_each == 3:
                continue
            total_dc_calc = (cont_per_block * ac_qty + cont_rem) + (cab_per_block * ac_qty + cab_rem)
            if total_dc_calc != dc_total:
                continue
            total_ac = ac_qty * p_ac
            if total_ac < poi_mw:
                continue
            oversize = total_ac - poi_mw
            score = (oversize, max_dc_each - base_dc_each, ac_qty)
            if best_score is None or score < best_score:
                best_score = score
                best = {
                    "strategy": "mixed",
                    "ac_block_qty": ac_qty,
                    "ac_block_rated_mw": p_ac,
                    "pcs_units": cand["pcs_units"],
                    "pcs_unit_kw": cand["pcs_unit_kw"],
                    "container_per_block": cont_per_block,
                    "cabinet_per_block": cab_per_block,
                    "container_rem": cont_rem,
                    "cabinet_rem": cab_rem,
                    "dc_blocks_per_block_base": base_dc_each,
                    "dc_blocks_per_block_max": max_dc_each,
                    "total_ac_mw": total_ac,
                    "oversize_mw": oversize,
                }
    return best


@dataclass
class BlockLayout:
    label: str
    footprint_width_m: float
    footprint_depth_m: float
    reserved_corridor_mm: int
    future_space_m: float
    components: List[Dict[str, Any]] = field(default_factory=list)


def build_ac_block_layout(
    ac_result: Dict[str, Any],
    stage13: Dict[str, Any],
    *,
    clearance_mm: int = 300,
    aisle_mm: int = 1200,
    future_space_ratio: float = 0.15,
) -> Dict[str, Any]:
    """Generate a simple SLD-friendly layout description for AC Blocks."""
    blocks: List[BlockLayout] = []
    dc_total = stage13.get("container_count", 0) + stage13.get("cabinet_count", 0)
    busbars = max(1, int(stage13.get("busbars_needed", 1)))
    dc_per_busbar = dc_total / busbars if busbars else dc_total

    base_width = 6.0 + ac_result.get("pcs_units", 0) * 0.6
    base_depth = 5.5
    future_space = base_width * future_space_ratio
    corridor_m = aisle_mm / 1000.0

    for idx in range(ac_result.get("ac_block_qty", 0)):
        components = [
            {
                "name": "PCS Cluster",
                "quantity": ac_result.get("pcs_units", 0),
                "detail": f"{ac_result.get('pcs_units', 0)} × {ac_result.get('pcs_unit_kw', 0)} kW",
                "clearance_mm": clearance_mm,
            },
            {
                "name": "MV Transformer",
                "quantity": 1,
                "detail": "Dedicated MV/LV transformer with 2 × LV feeders",
                "clearance_mm": clearance_mm,
            },
            {
                "name": "RMU / Switchgear",
                "quantity": 1,
                "detail": "Feeder & tie breakers with visible isolation",
                "clearance_mm": clearance_mm,
            },
            {
                "name": "DC Busbars",
                "quantity": 2,
                "detail": f"Busbars with ≈{dc_per_busbar:.1f} DC blocks each",
                "clearance_mm": clearance_mm,
            },
        ]

        blocks.append(
            BlockLayout(
                label=f"AC Block {idx + 1}",
                footprint_width_m=base_width,
                footprint_depth_m=base_depth,
                reserved_corridor_mm=aisle_mm,
                future_space_m=future_space,
                components=components,
            )
        )

    total_width = sum(block.footprint_width_m + corridor_m for block in blocks) + (blocks[-1].future_space_m if blocks else 0.0)
    max_depth = max((block.footprint_depth_m for block in blocks), default=0.0)

    return {
        "clearance_mm": clearance_mm,
        "aisle_mm": aisle_mm,
        "future_space_ratio": future_space_ratio,
        "total_width_m": total_width,
        "max_depth_m": max_depth,
        "blocks": blocks,
    }


def _draw_component_box(ax: Any, center: Tuple[float, float], text: str, box_cls: Any, *, color: str = "#cfe2ff") -> None:
    """Utility to draw a rounded component box with centered text."""
    x, y = center
    width, height = 1.2, 0.6
    box = box_cls(
        (x - width / 2, y - height / 2),
        width,
        height,
        boxstyle="round,pad=0.1,rounding_size=0.08",
        linewidth=1.2,
        facecolor=color,
        edgecolor="#0d6efd",
    )
    ax.add_patch(box)
    ax.text(x, y, text, ha="center", va="center", fontsize=10, weight="bold")


def build_block_sld(ac_result: Dict[str, Any], stage13: Dict[str, Any]) -> Any:
    """Create a simplified block-level SLD showing RMU → Transformer → PCS → DC Busbar → DC Block."""
    plt, FancyBboxPatch, _ = _get_matplotlib()
    fig, ax = plt.subplots(figsize=(9, 3))
    ax.axis("off")

    pcs_units = ac_result.get("pcs_units", 0)
    pcs_unit_kw = ac_result.get("pcs_unit_kw", 0)
    dc_total = stage13.get("container_count", 0) + stage13.get("cabinet_count", 0)
    busbars = stage13.get("busbars_needed", 2) or 2

    nodes = {
        "RMU": (-1, 0),
        "Transformer": (1, 0),
        "PCS": (3, 0),
        "AC Busbar": (5, 0),
        "DC Busbar": (7, 0),
        "DC Blocks": (9, 0),
    }

    _draw_component_box(ax, nodes["RMU"], "RMU / SWG", FancyBboxPatch)
    _draw_component_box(ax, nodes["Transformer"], "MV / LV TX", FancyBboxPatch)
    _draw_component_box(ax, nodes["PCS"], f"PCS\n{pcs_units} × {pcs_unit_kw} kW", FancyBboxPatch)
    _draw_component_box(ax, nodes["AC Busbar"], "AC Busbar", FancyBboxPatch)
    _draw_component_box(ax, nodes["DC Busbar"], f"DC Busbars\n{busbars} section(s)", FancyBboxPatch)
    _draw_component_box(ax, nodes["DC Blocks"], f"DC Blocks\n{dc_total} units", FancyBboxPatch)

    order = ["RMU", "Transformer", "PCS", "AC Busbar", "DC Busbar", "DC Blocks"]
    for left, right in zip(order, order[1:]):
        x0, y0 = nodes[left]
        x1, y1 = nodes[right]
        ax.annotate(
            "",
            xy=(x1 - 0.7, y1),
            xytext=(x0 + 0.7, y0),
            arrowprops=dict(arrowstyle="->", linewidth=1.4, color="#495057"),
        )

    ax.set_xlim(-2, 10)
    ax.set_ylim(-1.5, 1.5)
    ax.set_title("Block-Level Single Line Diagram (SLD)", fontsize=12, weight="bold")
    return fig


def build_block_layout_figure(layout: Dict[str, Any]) -> Any:
    """Visualize physical placement of AC Blocks with corridors and future expansion space."""
    plt, _, Rectangle = _get_matplotlib()
    fig, ax = plt.subplots(figsize=(10, 3 + len(layout.get("blocks", [])) * 0.5))
    ax.set_aspect("equal")
    ax.axis("off")

    x_cursor = 0.5
    corridor_m = layout.get("aisle_mm", 1200) / 1000.0

    for block in layout.get("blocks", []):
        rect = Rectangle(
            (x_cursor, 0.5),
            block.footprint_width_m,
            block.footprint_depth_m,
            linewidth=1.4,
            edgecolor="#0d6efd",
            facecolor="#e7f1ff",
        )
        ax.add_patch(rect)
        ax.text(
            x_cursor + block.footprint_width_m / 2,
            0.5 + block.footprint_depth_m / 2 + 0.2,
            block.label,
            ha="center",
            va="center",
            fontsize=10,
            weight="bold",
        )

        component_y = 0.5 + block.footprint_depth_m / 2 - 0.4
        for idx, comp in enumerate(block.components):
            ax.text(
                x_cursor + block.footprint_width_m / 2,
                component_y - idx * 0.35,
                f"{comp['name']} (≥{comp['clearance_mm']} mm)",
                ha="center",
                va="center",
                fontsize=8.5,
            )

        # Reserved corridor
        corridor_rect = Rectangle(
            (x_cursor + block.footprint_width_m, 0.5),
            corridor_m,
            block.footprint_depth_m,
            linewidth=1.0,
            edgecolor="#adb5bd",
            facecolor="#f8f9fa",
            linestyle="--",
        )
        ax.add_patch(corridor_rect)
        ax.text(
            x_cursor + block.footprint_width_m + corridor_m / 2,
            0.5 + block.footprint_depth_m + 0.1,
            f"Corridor {block.reserved_corridor_mm} mm",
            ha="center",
            va="bottom",
            fontsize=8,
            color="#6c757d",
        )

        # Future space shading
        future_rect = Rectangle(
            (x_cursor + block.footprint_width_m + corridor_m, 0.5),
            block.future_space_m,
            block.footprint_depth_m,
            linewidth=0.0,
            facecolor="#ffe8cc",
            alpha=0.7,
        )
        ax.add_patch(future_rect)
        ax.text(
            x_cursor + block.footprint_width_m + corridor_m + block.future_space_m / 2,
            0.5 + block.footprint_depth_m / 2,
            "Future\nallowance",
            ha="center",
            va="center",
            fontsize=8.5,
            color="#d9480f",
            weight="bold",
        )

        x_cursor += block.footprint_width_m + corridor_m + block.future_space_m + 0.5

    ax.set_xlim(0, max(x_cursor, 5))
    ax.set_ylim(0, max(layout.get("max_depth_m", 0.0) + 1.5, 3))
    ax.set_title("AC Block Layout (not to scale)", fontsize=12, weight="bold")
    return fig


def simulate_ac_power_flow(
    ac_result: Dict[str, Any],
    *,
    poi_mw: float,
    highest_voltage_kv: float,
    dc_fault_equivalent_mva: float,
    power_factor: float = 0.98,
    transformer_efficiency: float = 0.985,
) -> Dict[str, Any]:
    """Simulate normal and faulted AC power flow for Stage 4."""
    total_capacity_mw = float(ac_result.get("total_ac_mw", 0.0))
    available_mva = total_capacity_mw / max(power_factor, 0.01)
    poi_mva = poi_mw / max(power_factor, 0.01)
    margin_mw = total_capacity_mw - poi_mw

    normal_export_mw = min(total_capacity_mw * transformer_efficiency, poi_mw)
    overload_headroom_mw = max(margin_mw, 0.0)
    fault_mva = dc_fault_equivalent_mva * 0.95

    scenarios = [
        {
            "name": "Normal Operation",
            "ac_flow_mw": normal_export_mw,
            "ac_flow_mva": normal_export_mw / max(power_factor, 0.01),
            "status": "OK" if normal_export_mw >= poi_mw else "Limited",
        },
        {
            "name": "POI Overload Check",
            "ac_flow_mw": min(total_capacity_mw, poi_mw + overload_headroom_mw * 0.5),
            "ac_flow_mva": min(total_capacity_mw, poi_mw + overload_headroom_mw * 0.5) / max(power_factor, 0.01),
            "status": "OK" if margin_mw >= 0 else "Overload",
        },
        {
            "name": "DC Fault Equivalent",
            "ac_flow_mw": fault_mva * power_factor,
            "ac_flow_mva": fault_mva,
            "status": "Check Protections",
        },
        {
            "name": "Single Transformer Outage",
            "ac_flow_mw": max(total_capacity_mw - (ac_result.get("ac_block_rated_mw", 0.0) or 0.0), 0.0),
            "ac_flow_mva": max(total_capacity_mw - (ac_result.get("ac_block_rated_mw", 0.0) or 0.0), 0.0) / max(power_factor, 0.01),
            "status": "Redundant" if total_capacity_mw - poi_mw >= (ac_result.get("ac_block_rated_mw", 0.0) or 0.0) else "Limited",
        },
    ]

    return {
        "available_mva": available_mva,
        "poi_mva": poi_mva,
        "margin_mw": margin_mw,
        "highest_voltage_kv": highest_voltage_kv,
        "fault_equivalent_mva": fault_mva,
        "scenarios": scenarios,
    }
