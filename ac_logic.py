from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


AC_BLOCK_CANDIDATES: List[Dict[str, float]] = [
    {"pcs_units": 2, "pcs_unit_kw": 1250, "ac_block_mw": 2.5},
    {"pcs_units": 2, "pcs_unit_kw": 1725, "ac_block_mw": 3.45},
    {"pcs_units": 4, "pcs_unit_kw": 1250, "ac_block_mw": 5.0},
    {"pcs_units": 4, "pcs_unit_kw": 1725, "ac_block_mw": 6.9},
]


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

    return {
        "clearance_mm": clearance_mm,
        "aisle_mm": aisle_mm,
        "future_space_ratio": future_space_ratio,
        "blocks": blocks,
    }


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
    ]

    return {
        "available_mva": available_mva,
        "poi_mva": poi_mva,
        "margin_mw": margin_mw,
        "highest_voltage_kv": highest_voltage_kv,
        "fault_equivalent_mva": fault_mva,
        "scenarios": scenarios,
    }
