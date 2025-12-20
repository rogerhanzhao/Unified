from __future__ import annotations

from ac_logic import find_ac_block_container_only, find_ac_block_mixed
from stage4_app import render_block_layout_tab, render_simulation_tab
import streamlit as st

st.set_page_config(page_title="Stage 4 – AC Block", layout="wide")


# -----------------------------------------------------
# Main UI
# -----------------------------------------------------

st.title("Stage 4 – AC Block (V0.4)")
st.caption("Chain: RMU/SW → Transformer (MV/LV) → PCS → DC Busbar → DC Block")

stage13 = st.session_state.get("stage13_output")
if not stage13:
    st.error("Stage 1–3 output not found. Please complete sizing in Stage 1–3 first.")
    st.stop()

# Tabs for interaction
tab1, tab2, tab3 = st.tabs(
    ["Step 1 · AC Block Sizing", "Step 2 · Block SLD + Layout", "Step 3 · Site + Simulation"]
)

with tab1:
    # Read values from stage13_output
    poi_mw = stage13.get("poi_power_req_mw", 0.0)
    container_cnt = stage13.get("container_count", 0)
    cabinet_cnt = stage13.get("cabinet_count", 0)
    dc_total = stage13.get("dc_total_blocks", container_cnt + cabinet_cnt)
    poi_voltage = stage13.get("poi_nominal_voltage_kv", "")

    # Top Metrics
    c1, c2, c3 = st.columns(3)
    c1.metric("POI Power Requirement (MW)", f"{poi_mw:.2f}")
    c2.metric("DC Blocks Total", f"{dc_total}")
    c3.metric("POI Nominal Voltage (kV)", f"{poi_voltage}")
    

    st.write(f"Current DC configuration: container = {container_cnt}, cabinet = {cabinet_cnt}")
    st.divider()

    search_extra = st.number_input(
        "Search Extra AC Block Qty (V0.4)",
        min_value=0, value=40, step=5
    )

    if st.button("Run Step 1 · AC Block Sizing"):
        # Try container-only
        best_container = find_ac_block_container_only(
            poi_mw=float(poi_mw),
            container_cnt=int(container_cnt),
            search_extra=int(search_extra),
        )
        if best_container:
            st.success("Container-only DC Blocks matched AC Block configuration.")
            st.session_state["stage4_step1_result"] = best_container
        else:
            # Try mixed
            best_mixed = find_ac_block_mixed(
                poi_mw=float(poi_mw),
                container_cnt=int(container_cnt),
                cabinet_cnt=int(cabinet_cnt),
                search_extra=int(search_extra),
            )
            if best_mixed:
                st.warning("Container-only did not satisfy rules, using mixed DC Blocks for AC Block matching.")
                st.session_state["stage4_step1_result"] = best_mixed
            else:
                st.error(
                    "Neither container-only nor mixed DC Blocks can satisfy AC Block rules. "
                    "Please revise DC configuration in Stage 1–3 (e.g., adjust container/cabinet counts)."
                )

    res = st.session_state.get("stage4_step1_result")
    if res:
        st.markdown("## Step 1 · AC Block Sizing Summary (V0.4)")

        st.write(f"**Strategy**: {res.get('strategy', '').replace('_', ' ').title()}")

        cA, cB, cC, cD, cE = st.columns(5)
        with cA:
            st.metric("AC Blocks Quantity", f"{res['ac_block_qty']}")
        with cB:
            st.metric("AC Block Rating (MW)", f"{res['ac_block_rated_mw']:.2f}")
        with cC:
            st.metric("PCS per Block", f"{res['pcs_units']} × {res['pcs_unit_kw']} kW")
        with cD:
            st.metric("Total AC Capacity (MW)", f"{res['total_ac_mw']:.2f}")
        with cE:
            st.metric("Oversize vs POI (MW)", f"{res['oversize_mw']:.2f}")

        # DC Blocks per AC Block details
        if res.get("strategy") == "container_only":
            st.write(f"**DC Blocks per AC Block**: {res.get('dc_blocks_per_block', 0)}")
        else:
            st.write("**Mixed DC Distribution per AC Block**")
            st.write(f"• Containers / Block: {res.get('container_per_block', 0)}")
            st.write(f"• Cabinets / Block: {res.get('cabinet_per_block', 0)}")
            if res.get("container_rem", 0) or res.get("cabinet_rem", 0):
                st.write(
                    f"  ⚠ Remainder not evenly divisible: container_rem={res.get('container_rem', 0)}, "
                    f"cabinet_rem={res.get('cabinet_rem', 0)}"
                )
            st.write(
                f"  • DC Blocks per Block (base/max): "
                f"{res.get('dc_blocks_per_block_base', 0)} / {res.get('dc_blocks_per_block_max', 0)}"
            )

with tab2:
    render_block_layout_tab(stage13, st.session_state.get("stage4_step1_result"))

with tab3:
    render_simulation_tab(stage13, st.session_state.get("stage4_step1_result"))
