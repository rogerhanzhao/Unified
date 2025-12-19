# pages/4_Stage4_AC_Block.py
from __future__ import annotations
import json
import math
from io import StringIO
from typing import Any, Dict, List, Optional

import altair as alt
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Stage 4 – AC Block", layout="wide")

# -----------------------------------------------------
# AC Block Sizing Functions
# -----------------------------------------------------

def find_ac_block_container_only(
    poi_mw: float,
    container_cnt: int,
    *,
    search_extra: int = 40
) -> Optional[Dict[str, Any]]:
    """
    Try container-only DC Blocks to match AC Blocks.
    """
    if container_cnt <= 0:
        return None

    candidates = [
        {"pcs_units": 2, "pcs_unit_kw": 1250, "ac_block_mw": 2.5},
        {"pcs_units": 2, "pcs_unit_kw": 1725, "ac_block_mw": 3.45},
        {"pcs_units": 4, "pcs_unit_kw": 1250, "ac_block_mw": 5.0},
        {"pcs_units": 4, "pcs_unit_kw": 1725, "ac_block_mw": 6.9},
    ]
    best = None
    best_score = None

    for cand in candidates:
        p_ac = cand["ac_block_mw"]
        n_min = max(1, int(math.ceil(poi_mw / p_ac)))

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
    search_extra: int = 40
) -> Optional[Dict[str, Any]]:
    """
    Try mixed (container + cabinet) DC Blocks to match AC Blocks.
    """
    dc_total = container_cnt + cabinet_cnt
    if dc_total <= 0:
        return None

    candidates = [
        {"pcs_units": 2, "pcs_unit_kw": 1250, "ac_block_mw": 2.5},
        {"pcs_units": 2, "pcs_unit_kw": 1725, "ac_block_mw": 3.45},
        {"pcs_units": 4, "pcs_unit_kw": 1250, "ac_block_mw": 5.0},
        {"pcs_units": 4, "pcs_unit_kw": 1725, "ac_block_mw": 6.9},
    ]
    best = None
    best_score = None

    for cand in candidates:
        p_ac = cand["ac_block_mw"]
        n_min = max(1, int(math.ceil(poi_mw / p_ac)))

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


def compute_dc_distribution(res: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Expand the AC Block sizing result into per-block DC distribution rows.
    """
    rows: List[Dict[str, Any]] = []
    qty = int(res.get("ac_block_qty", 0) or 0)
    if qty <= 0:
        return rows

    if res.get("strategy") == "container_only":
        dc_per = int(res.get("dc_blocks_per_block", 0) or 0)
        for i in range(qty):
            rows.append(
                {
                    "ac_block": i + 1,
                    "containers": dc_per,
                    "cabinets": 0,
                    "dc_blocks_total": dc_per,
                }
            )
    else:
        base_cont = int(res.get("container_per_block", 0) or 0)
        base_cab = int(res.get("cabinet_per_block", 0) or 0)
        rem_cont = int(res.get("container_rem", 0) or 0)
        rem_cab = int(res.get("cabinet_rem", 0) or 0)
        for i in range(qty):
            cont = base_cont + (1 if i < rem_cont else 0)
            cab = base_cab + (1 if i < rem_cab else 0)
            rows.append(
                {
                    "ac_block": i + 1,
                    "containers": cont,
                    "cabinets": cab,
                    "dc_blocks_total": cont + cab,
                }
            )
    return rows


def compute_line_current_a(power_mw: float, voltage_kv: float, power_factor: float = 0.95) -> float:
    """Simple 3-phase current estimate from MW and kV."""
    if voltage_kv <= 0 or power_factor <= 0:
        return 0.0
    power_w = power_mw * 1_000_000
    voltage_v = voltage_kv * 1_000
    current = power_w / (math.sqrt(3) * voltage_v * power_factor)
    return current


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
    ["Step 1 · AC Block Sizing", "Step 2 · Block SLD + Layout", "Step 3 · Site + Simulation & Export"]
)

with tab1:
    # Read values from stage13_output
    poi_mw = stage13.get("poi_power_req_mw", 0.0)
    container_cnt = stage13.get("container_count", 0)
    cabinet_cnt = stage13.get("cabinet_count", 0)
    dc_total = stage13.get("dc_total_blocks", container_cnt + cabinet_cnt)
    poi_voltage = stage13.get("poi_nominal_voltage_kv", "")
    highest_equip_voltage = stage13.get("highest_equipment_voltage_kv", "")

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
    res = st.session_state.get("stage4_step1_result")
    if not res:
        st.info("Run Step 1 to generate AC Block selection before viewing SLD and layout.")
    else:
        st.subheader("Single Line Diagram (SLD) Overview")
        poi_voltage = stage13.get("poi_nominal_voltage_kv", "")
        highest_equipment_voltage = stage13.get("highest_equipment_voltage_kv", "")
        poi_mw = stage13.get("poi_power_req_mw", 0.0)
        sld = f"""
digraph G {{
  rankdir=LR;
  node [shape=rectangle style="rounded,filled" fillcolor="#f4f8ff" color="#2b6cb0" fontname="Arial"];
  POI [label="POI\\n{poi_mw:.2f} MW @ {poi_voltage} kV"];
  RMU [label="RMU / Switchgear"];
  TX [label="Transformer\\nHighest Equip: {highest_equipment_voltage} kV"];
  PCS [label="PCS\\n{res.get('pcs_units', 0)} × {res.get('pcs_unit_kw', 0)} kW"];
  DCBus [label="DC Busbar"];
  DCBlock [label="DC Blocks / AC Block\\n{res.get('ac_block_rated_mw', 0):.2f} MW"];
  POI -> RMU -> TX -> PCS -> DCBus -> DCBlock;
}}
"""
        st.graphviz_chart(sld, use_container_width=True)

        st.caption("Voltage and capacity references come from Stage 1–3 outputs and the AC Block selection above.")

        st.subheader("Block-Level Layout Preview")
        distribution = compute_dc_distribution(res)
        if distribution:
            df = pd.DataFrame(distribution)
            df_chart = df.rename(columns={"containers": "Containers", "cabinets": "Cabinets"})
            c1, c2 = st.columns([1, 2])
            with c1:
                st.metric("AC Blocks", f"{res.get('ac_block_qty', 0)}")
                st.metric("AC Block Rating (MW)", f"{res.get('ac_block_rated_mw', 0):.2f}")
                st.metric("PCS Combo", f"{res.get('pcs_units', 0)} × {res.get('pcs_unit_kw', 0)} kW")
            with c2:
                st.dataframe(df.rename(columns={
                    "ac_block": "AC Block #",
                    "containers": "Containers",
                    "cabinets": "Cabinets",
                    "dc_blocks_total": "DC Blocks Total",
                }), use_container_width=True)

            chart = (
                alt.Chart(df_chart)
                .transform_fold(["Containers", "Cabinets"], as_=["type", "qty"])
                .mark_bar()
                .encode(
                    x=alt.X("ac_block:O", title="AC Block #"),
                    y=alt.Y("qty:Q", title="DC Blocks per AC Block"),
                    color=alt.Color("type:N", title="DC Block Type"),
                    tooltip=["ac_block", "type", "qty", "dc_blocks_total"],
                )
                .properties(height=300)
            )
            st.altair_chart(chart, use_container_width=True)
        else:
            st.warning("No DC distribution rows found for the selected AC Blocks.")

with tab3:
    res = st.session_state.get("stage4_step1_result")
    if not res:
        st.info("Run Step 1 to enable site-level simulation and export.")
    else:
        st.subheader("Station-Level Impact (Simplified)")
        load_pct = st.slider("Assumed operating level vs. POI requirement (%)", min_value=50, max_value=120, value=90, step=5)

        poi_mw = float(stage13.get("poi_power_req_mw", 0.0) or 0.0)
        transformer_rating_mva = float(stage13.get("transformer_rating_mva", 0.0) or poi_mw * 1.1)
        voltage_kv = float(stage13.get("poi_nominal_voltage_kv", 0.0) or 0.0)

        load_case_mw = poi_mw * load_pct / 100
        max_ac_case_mw = float(res.get("total_ac_mw", 0.0) or 0.0)

        sim_rows = [
            {
                "Scenario": "Operating Load",
                "Power MW": load_case_mw,
                "Transformer Util (%)": (load_case_mw / transformer_rating_mva * 100) if transformer_rating_mva else 0,
                "Line Current (A)": compute_line_current_a(load_case_mw, voltage_kv),
            },
            {
                "Scenario": "Max AC Block Output",
                "Power MW": max_ac_case_mw,
                "Transformer Util (%)": (max_ac_case_mw / transformer_rating_mva * 100) if transformer_rating_mva else 0,
                "Line Current (A)": compute_line_current_a(max_ac_case_mw, voltage_kv),
            },
        ]
        sim_df = pd.DataFrame(sim_rows)

        c1, c2, c3 = st.columns(3)
        c1.metric("Transformer Rating (MVA)", f"{transformer_rating_mva:.2f}")
        c2.metric("POI Voltage (kV)", f"{voltage_kv}")
        c3.metric("AC Blocks Total (MW)", f"{max_ac_case_mw:.2f}")

        util_chart = (
            alt.Chart(sim_df)
            .mark_bar()
            .encode(
                x=alt.X("Scenario:N", title="Scenario"),
                y=alt.Y("Transformer Util (%):Q", title="Transformer Utilization (%)"),
                color=alt.Color("Scenario:N", legend=None),
                tooltip=["Power MW", "Transformer Util (%)", "Line Current (A)"],
            )
            .properties(height=260)
        )
        st.altair_chart(util_chart, use_container_width=True)

        st.caption("Transformer utilization and line current are approximations based on 3-phase power at the POI voltage with PF=0.95.")

        st.subheader("Export / Download")
        export_payload = {
            "project": stage13.get("project_name", "CALB ESS Project"),
            "stage13_snapshot": stage13,
            "ac_block_selection": res,
            "simulation_inputs": {
                "load_pct": load_pct,
                "transformer_rating_mva": transformer_rating_mva,
                "poi_voltage_kv": voltage_kv,
            },
            "simulation_results": sim_rows,
        }
        export_json = json.dumps(export_payload, indent=2, ensure_ascii=False)
        st.download_button(
            "Download Stage 1–4 Summary (JSON)",
            data=export_json,
            file_name="stage1-4_summary.json",
            mime="application/json",
        )

        distribution_export = compute_dc_distribution(res)
        layout_csv_buffer = StringIO()
        pd.DataFrame(distribution_export).to_csv(layout_csv_buffer, index=False)
        st.download_button(
            "Download Block Layout (CSV)",
            data=layout_csv_buffer.getvalue(),
            file_name="ac_block_layout.csv",
            mime="text/csv",
        )
