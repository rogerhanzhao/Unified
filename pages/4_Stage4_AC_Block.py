# pages/4_Stage4_AC_Block.py
from __future__ import annotations
import math
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import streamlit as st

from artifact_generation import (
    ensure_output_dirs,
    generate_stage4_report,
    render_block_sld,
    render_layout_plot,
)

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


# -----------------------------------------------------
# Main UI
# -----------------------------------------------------

st.title("Stage 4 – AC Block (V0.4)")
st.caption("Chain: RMU/SW → Transformer (MV/LV) → PCS → DC Busbar → DC Block")

stage13 = st.session_state.get("stage13_output")
if not stage13:
    st.error("Stage 1–3 output not found. Please complete sizing in Stage 1–3 first.")
    st.stop()


def _stage4_dirs(key_prefix: str) -> Tuple[Path, Path]:
    """Return temp/output directories configured by the user."""
    temp_key = f"{key_prefix}_temp_dir"
    output_key = f"{key_prefix}_output_dir"

    temp_dir = Path(st.session_state.get(temp_key, st.session_state.get("stage4_temp_dir", "temp")))
    output_dir = Path(st.session_state.get(output_key, st.session_state.get("stage4_output_dir", "outputs")))

    temp_dir = Path(
        st.text_input(
            "Temporary directory for render artifacts",
            value=str(temp_dir),
            key=f"{key_prefix}_temp_input",
        )
    )
    output_dir = Path(
        st.text_input(
            "Output directory for saved artifacts",
            value=str(output_dir),
            key=f"{key_prefix}_output_input",
        )
    )

    st.session_state[temp_key] = str(temp_dir)
    st.session_state[output_key] = str(output_dir)
    st.session_state["stage4_temp_dir"] = str(temp_dir)
    st.session_state["stage4_output_dir"] = str(output_dir)

    ensure_output_dirs(temp_dir=temp_dir, output_dir=output_dir)
    return temp_dir, output_dir

# Tabs for interaction
tab1, tab2, tab3 = st.tabs(
    [
        "Step 1 · AC Block Sizing",
        "Step 2 · Block SLD + Layout",
        "Step 3 · Reports & Simulation Preview",
    ]
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
    st.subheader("Generate Block SLD and Layout Artifacts")
    st.caption("Creates PNGs in the chosen temp/output folders for quick visual checks.")

    temp_dir, output_dir = _stage4_dirs("stage4_layout")
    st.caption(f"Artifacts will be written to **{temp_dir}** (temp) and **{output_dir}** (outputs).")

    existing_sld = st.session_state.get("stage4_sld_paths", {})
    existing_layout = st.session_state.get("stage4_layout_paths", {})
    if existing_sld or existing_layout:
        st.write("Last generated:")
        if existing_sld:
            st.write(f"• SLD: {existing_sld.get('temp')} (temp), {existing_sld.get('output')} (output)")
        if existing_layout:
            st.write(f"• Layout: {existing_layout.get('temp')} (temp), {existing_layout.get('output')} (output)")

    if st.button("Generate SLD + Layout Files", type="primary"):
        try:
            sld_temp, sld_output = render_block_sld(stage13, temp_dir=temp_dir, output_dir=output_dir)
            layout_temp, layout_output = render_layout_plot(stage13, temp_dir=temp_dir, output_dir=output_dir)
            st.session_state["stage4_sld_paths"] = {"temp": str(sld_temp), "output": str(sld_output)}
            st.session_state["stage4_layout_paths"] = {"temp": str(layout_temp), "output": str(layout_output)}
            st.success("Saved SLD and layout plots to temp/output folders.")
            st.image(str(sld_temp), caption="Block SLD preview")
            st.image(str(layout_temp), caption="Layout preview")
        except Exception as exc:
            st.error(f"Rendering failed: {exc}")

with tab3:
    st.subheader("Reports & Simulation Preview")
    st.caption("Save a DOCX that references the latest SLD/Layout files.")

    temp_dir, output_dir = _stage4_dirs("stage4_reports")
    sld_paths = st.session_state.get("stage4_sld_paths", {})
    layout_paths = st.session_state.get("stage4_layout_paths", {})

    sld_path = Path(sld_paths["output"]) if "output" in sld_paths else None
    layout_path = Path(layout_paths["output"]) if "output" in layout_paths else None

    if st.button("Generate Sample Stage 4 DOCX", type="primary"):
        try:
            if sld_path is None or not sld_path.exists():
                sld_temp, sld_output = render_block_sld(stage13, temp_dir=temp_dir, output_dir=output_dir)
                st.session_state["stage4_sld_paths"] = {"temp": str(sld_temp), "output": str(sld_output)}
                sld_path = sld_output
            if layout_path is None or not layout_path.exists():
                layout_temp, layout_output = render_layout_plot(stage13, temp_dir=temp_dir, output_dir=output_dir)
                st.session_state["stage4_layout_paths"] = {"temp": str(layout_temp), "output": str(layout_output)}
                layout_path = layout_output

            report_path = generate_stage4_report(
                stage13,
                sld_path=sld_path,
                layout_path=layout_path,
                output_dir=output_dir,
            )
            st.session_state["stage4_report_path"] = str(report_path)
            st.success(f"Report saved to {report_path}")
            with open(report_path, "rb") as fh:
                st.download_button(
                    "Download Latest Report",
                    data=fh,
                    file_name=report_path.name,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
        except Exception as exc:
            st.error(f"Report generation failed: {exc}")

    if "stage4_report_path" in st.session_state:
        st.caption(f"Last report: {st.session_state['stage4_report_path']}")
