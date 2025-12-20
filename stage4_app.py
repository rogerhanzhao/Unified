from __future__ import annotations

from typing import Any, Dict, Optional

import streamlit as st

from ac_logic import build_ac_block_layout, simulate_ac_power_flow
from dc_logic import estimate_dc_fault_equivalent


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def render_block_layout_tab(stage13: Dict[str, Any], ac_result: Optional[Dict[str, Any]]) -> None:
    """Render Stage 4 Step 2: block-level SLD and layout."""
    if not ac_result:
        st.info("Run Step 1 to generate an AC Block configuration before building the layout.")
        return

    layout = build_ac_block_layout(ac_result, stage13)
    st.subheader("Step 2 · Block SLD + Layout")
    st.caption("Layouts follow 田字格 spacing with minimum 300 mm clearances and future expansion corridors.")

    st.markdown(
        f"- Clearance: **{layout['clearance_mm']} mm**  \n"
        f"- Aisle / corridor: **{layout['aisle_mm']} mm**  \n"
        f"- Future allowance: **{int(layout['future_space_ratio'] * 100)}%** width reserved per block"
    )

    for block in layout["blocks"]:
        st.markdown(f"#### {block.label}")
        c1, c2, c3 = st.columns(3)
        c1.metric("Footprint (W × D, m)", f"{block.footprint_width_m:.1f} × {block.footprint_depth_m:.1f}")
        c2.metric("Reserved Corridor", f"{block.reserved_corridor_mm} mm")
        c3.metric("Future Space", f"{block.future_space_m:.1f} m")

        with st.expander("Components and clearances", expanded=True):
            for comp in block.components:
                st.write(
                    f"• **{comp['name']}** — qty {comp['quantity']} | {comp['detail']} "
                    f"| clearance ≥ {comp['clearance_mm']} mm"
                )


def render_simulation_tab(stage13: Dict[str, Any], ac_result: Optional[Dict[str, Any]]) -> None:
    """Render Stage 4 Step 3: power-flow and fault simulation overview."""
    if not ac_result:
        st.info("Run Step 1 to generate an AC Block configuration before running simulations.")
        return

    dc_blocks = stage13.get("dc_block_total_qty") or (
        stage13.get("container_count", 0) + stage13.get("cabinet_count", 0)
    )
    busbars = stage13.get("busbars_needed")
    # Respect Stage 2 payload; fall back to 2 only when busbar metadata is missing entirely.
    busbars = 2 if busbars is None else busbars
    fault_eq = estimate_dc_fault_equivalent(
        dc_blocks=int(dc_blocks),
        dc_busbars=int(busbars),
    )

    sim = simulate_ac_power_flow(
        ac_result,
        poi_mw=_to_float(stage13.get("poi_power_req_mw", 0.0)),
        highest_voltage_kv=_to_float(
            stage13.get(
                "highest_equipment_voltage_kv",
                stage13.get("poi_nominal_voltage_kv", 0.0),
            )
        ),
        dc_fault_equivalent_mva=_to_float(fault_eq.fault_mva),
    )

    st.subheader("Step 3 · Site Layout + Simulation")
    st.caption("Power-flow checks include POI export, overload margin, and DC fault equivalents.")

    c1, c2, c3 = st.columns(3)
    c1.metric("Available AC Capacity (MVA)", f"{sim['available_mva']:.2f}")
    c2.metric("POI Requirement (MVA)", f"{sim['poi_mva']:.2f}")
    c3.metric("Margin (MW)", f"{sim['margin_mw']:.2f}")

    st.markdown(
        f"- Highest equipment voltage: **{sim['highest_voltage_kv']:.2f} kV**  \n"
        f"- DC fault equivalent: **{sim['fault_equivalent_mva']:.1f} MVA**  \n"
        f"- Fault description: {fault_eq.description}"
    )

    for scenario in sim["scenarios"]:
        with st.expander(scenario["name"], expanded=True):
            d1, d2, d3 = st.columns(3)
            d1.metric("AC Flow (MW)", f"{scenario['ac_flow_mw']:.2f}")
            d2.metric("AC Flow (MVA)", f"{scenario['ac_flow_mva']:.2f}")
            d3.metric("Status", scenario["status"])
            st.progress(min(scenario["ac_flow_mva"] / max(sim["available_mva"], 0.01), 1.0))
