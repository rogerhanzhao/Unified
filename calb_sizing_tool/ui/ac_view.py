import math

import pandas as pd
import streamlit as st

from calb_sizing_tool.config import AC_DATA_PATH, DC_DATA_PATH
from calb_sizing_tool.models import DCBlockResult
from calb_sizing_tool.reporting.export_docx import (
    create_ac_report,
    create_combined_report,
    make_report_filename,
)
from calb_sizing_tool.reporting.report_context import build_report_context
from calb_sizing_tool.reporting.report_v2 import export_report_v2


def _extract_block_identity(stage2_raw):
    block_code = None
    block_name = None
    block_table = stage2_raw.get("block_config_table") if isinstance(stage2_raw, dict) else None
    if isinstance(block_table, pd.DataFrame) and not block_table.empty:
        first_row = block_table.iloc[0]
        block_code = first_row.get("Block Code")
        block_name = first_row.get("Block Name")
    return block_code, block_name


def show():
    st.header("AC Block Sizing")

    # 1. Dependency Check
    if "dc_result_summary" not in st.session_state:
        st.warning("DC sizing results not found.")
        st.info("Please run DC sizing first.")
        return

    # Retrieve data from session state
    dc_data = st.session_state.get("dc_result_summary", {})
    stage13_output = st.session_state.get("stage13_output", {})

    try:
        dc_model = dc_data.get("dc_block")
        if not dc_model:
            dc_model = DCBlockResult(
                block_id="DC-Fallback",
                capacity_mwh=5.015,
                count=int(dc_data.get("container_count", 0)),
                voltage_v=1200,
            )

        target_mw = float(dc_data.get("target_mw", stage13_output.get("poi_power_req_mw", 10.0)))
        target_mwh = float(dc_data.get("mwh", stage13_output.get("poi_energy_req_mwh", 0.0)))
    except Exception as exc:
        st.error(f"Data structure mismatch: {exc}. Please re-run DC sizing.")
        return

    project_name = stage13_output.get("project_name", "CALB ESS Project")

    # Display Context
    st.info(
        f"Basis: DC system has {dc_model.count} x {dc_model.container_model} "
        f"({dc_model.capacity_mwh:.3f} MWh each)."
    )

    # 2. Inputs Form
    with st.form("ac_sizing_form"):
        st.subheader("Electrical Parameters")
        c1, c2 = st.columns(2)

        grid_kv = c1.number_input(
            "Grid Voltage (kV)",
            min_value=1.0,
            value=33.0,
            step=0.1,
            help="Medium Voltage (MV) at the collection bus / POI.",
        )

        pcs_lv = c2.number_input(
            "PCS AC Output Voltage (LV bus, V_LL,rms)",
            min_value=200.0,
            value=800.0,
            step=10.0,
            help="AC-side low-voltage bus voltage at PCS output.",
        )

        st.subheader("Configuration")
        block_size = st.selectbox("Standard AC Block Size (MW)", [2.5, 3.44, 5.0, 6.88])

        submitted = st.form_submit_button("Run AC Sizing")

    # 3. Calculation & Results
    if submitted:
        num_blocks = math.ceil(target_mw / block_size) if block_size > 0 else 0
        total_ac_mw = num_blocks * block_size
        overhead = total_ac_mw - target_mw

        dc_per_ac = 0
        if num_blocks > 0:
            dc_per_ac = max(1, dc_model.count // num_blocks)

        pcs_per_block = 2
        pcs_power_kw = block_size * 1000 / pcs_per_block
        transformer_kva = block_size * 1000 / 0.9
        total_pcs = num_blocks * pcs_per_block

        ac_output = {
            "project_name": project_name,
            "poi_power_mw": target_mw,
            "poi_energy_mwh": target_mwh,
            "grid_kv": grid_kv,
            "inverter_lv_v": pcs_lv,
            "block_size_mw": block_size,
            "num_blocks": num_blocks,
            "total_ac_mw": total_ac_mw,
            "overhead_mw": overhead,
            "pcs_power_kw": pcs_power_kw,
            "pcs_per_block": pcs_per_block,
            "total_pcs": total_pcs,
            "transformer_kva": transformer_kva,
            "transformer_count": num_blocks,
            "dc_blocks_per_ac": dc_per_ac,
            "mv_level_kv": grid_kv,
        }

        st.session_state["ac_output"] = ac_output

        st.divider()
        st.subheader("AC Configuration Results")
        k1, k2, k3 = st.columns(3)
        k1.metric("AC Blocks", f"{num_blocks} x {block_size} MW")
        k2.metric("Total AC Power", f"{total_ac_mw:.2f} MW")
        k3.metric("Overhead Margin", f"{overhead:.2f} MW")

        st.info(
            f"Topology: Each {block_size} MW AC block connects to {dc_per_ac} "
            "DC battery containers."
        )

        st.success("AC sizing complete. Reports are ready for download.")

    # 4. Downloads
    if "ac_output" in st.session_state:
        ac_output = st.session_state["ac_output"]

        inputs = {
            "Project Name": project_name,
            "POI Power Requirement (MW)": _format_float(ac_output.get("poi_power_mw"), 2),
            "POI Energy Requirement (MWh)": _format_float(ac_output.get("poi_energy_mwh"), 2),
            "Grid Voltage (kV)": _format_float(ac_output.get("grid_kv"), 1),
            "PCS AC Output Voltage (V_LL,rms)": _format_float(ac_output.get("inverter_lv_v"), 0),
            "Standard AC Block Size (MW)": _format_float(ac_output.get("block_size_mw"), 2),
        }
        if stage13_output:
            inputs["Selected DC Scenario"] = stage13_output.get("selected_scenario", "")
            if "dc_nameplate_bol_mwh" in stage13_output:
                inputs["DC Nameplate @BOL (MWh)"] = _format_float(
                    stage13_output.get("dc_nameplate_bol_mwh"), 3
                )

        report_context = {
            "project_name": project_name,
            "inputs": inputs,
            "dictionary_version": AC_DATA_PATH.name,
            "input_file_version": DC_DATA_PATH.name,
            "tool_version": "V1.0",
        }

        st.subheader("Downloads")
        report_template = st.selectbox(
            "Report Template",
            ["V1 (Stable)", "V2 (Beta)"],
            index=0,
            help="Default uses stable V1; V2 is beta and uses the new report structure.",
        )
        c_d1, c_d2 = st.columns(2)

        with c_d1:
            ac_bytes = create_ac_report(ac_output, report_context)

            st.download_button(
                "Download AC Report",
                ac_bytes,
                make_report_filename(project_name, "AC"),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )

        with c_d2:
            if not stage13_output:
                st.info("Run DC sizing to enable the combined report.")
            else:
                stage2_raw = stage13_output.get("stage2_raw", {})
                block_code, block_name = _extract_block_identity(stage2_raw)

                dc_output = {
                    "stage1": stage13_output,
                    "selected_scenario": stage13_output.get("selected_scenario", "container_only"),
                    "dc_block_total_qty": stage13_output.get("dc_block_total_qty"),
                    "container_count": stage13_output.get("container_count"),
                    "block_code": block_code,
                    "block_name": block_name,
                }

                if report_template.startswith("V2"):
                    ctx = build_report_context(
                        session_state=st.session_state,
                        stage_outputs={"stage13_output": stage13_output, "ac_output": ac_output},
                        project_inputs={"poi_energy_guarantee_mwh": stage13_output.get("poi_energy_req_mwh")},
                        scenario_ids=stage13_output.get("selected_scenario"),
                    )
                    comb_bytes = export_report_v2(ctx)
                    file_suffix = "Combined_V2_Beta"
                    button_label = "Download Combined Report V2 (Beta)"
                else:
                    comb_bytes = create_combined_report(dc_output, ac_output, report_context)
                    file_suffix = "Combined"
                    button_label = "Download Combined Report (DC+AC)"

                st.download_button(
                    button_label,
                    comb_bytes,
                    make_report_filename(project_name, file_suffix),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    type="primary",
                )


def _format_float(value, decimals):
    if value is None:
        return ""
    try:
        return f"{float(value):.{decimals}f}"
    except Exception:
        return str(value)
