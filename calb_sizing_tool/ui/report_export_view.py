import streamlit as st

from calb_sizing_tool.config import AC_DATA_PATH, DC_DATA_PATH
from calb_sizing_tool.reporting.export_docx import (
    create_ac_report,
    create_combined_report,
    make_report_filename,
)
from calb_sizing_tool.reporting.report_context import build_report_context
from calb_sizing_tool.reporting.report_v2 import export_report_v2_1
from calb_sizing_tool.state.session_state import init_shared_state


def _extract_block_identity(stage2_raw):
    block_code = None
    block_name = None
    block_table = stage2_raw.get("block_config_table") if isinstance(stage2_raw, dict) else None
    if block_table is not None and not block_table.empty:
        first_row = block_table.iloc[0]
        block_code = first_row.get("Block Code")
        block_name = first_row.get("Block Name")
    return block_code, block_name


def show():
    init_shared_state()
    dc_results = st.session_state.get("dc_results", {}) or {}
    ac_results = st.session_state.get("ac_results", {}) or {}
    diagram_results = st.session_state.get("diagram_results", {}) or {}
    layout_results = st.session_state.get("layout_results", {}) or {}

    st.header("Report Export")
    st.caption("Generate DOCX reports (V1 stable and V2.1 beta).")

    stage13_output = (
        dc_results.get("stage13_output")
        or st.session_state.get("stage13_output")
        or {}
    )
    ac_output = ac_results or st.session_state.get("ac_output") or {}

    if not stage13_output or not ac_output:
        st.warning("Run DC sizing and AC sizing first to enable report export.")
        return

    project_name = (
        stage13_output.get("project_name")
        or ac_output.get("project_name")
        or "CALB ESS Project"
    )

    inputs = {
        "Project Name": project_name,
        "POI Power Requirement (MW)": ac_output.get("poi_power_mw"),
        "POI Energy Requirement (MWh)": ac_output.get("poi_energy_mwh"),
        "Grid Voltage (kV)": ac_output.get("grid_kv"),
        "PCS AC Output Voltage (V_LL,rms)": ac_output.get("inverter_lv_v"),
        "Standard AC Block Size (MW)": ac_output.get("block_size_mw"),
    }

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
        ["V1 (Stable)", "V2.1 (Beta)"],
        index=0,
        help="V1 is stable; V2.1 embeds diagram PNGs when available.",
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
        if dc_results.get("results_dict"):
            dc_output["results_dict"] = dc_results.get("results_dict")
        if dc_results.get("report_order"):
            dc_output["report_order"] = dc_results.get("report_order")

        if report_template.startswith("V2.1"):
            ctx = build_report_context(
                session_state=st.session_state,
                stage_outputs={"stage13_output": stage13_output, "ac_output": ac_output},
                project_inputs={"poi_energy_guarantee_mwh": stage13_output.get("poi_energy_req_mwh")},
                scenario_ids=stage13_output.get("selected_scenario", "container_only"),
            )
            comb_bytes = export_report_v2_1(ctx)
            file_suffix = "Combined_V2_1_Beta"
            button_label = "Download Combined Report V2.1 (Beta)"
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

    sld_png = None
    layout_png = None
    if isinstance(diagram_results, dict) and diagram_results:
        preferred = diagram_results.get("last_style")
        if preferred and isinstance(diagram_results.get(preferred), dict):
            sld_png = diagram_results[preferred].get("png")
        if sld_png is None:
            for style_key in ("raw_v05", "pro_v10", "jp_v08"):
                if isinstance(diagram_results.get(style_key), dict):
                    sld_png = diagram_results[style_key].get("png")
                if sld_png:
                    break
    if isinstance(layout_results, dict) and layout_results:
        preferred = layout_results.get("last_style")
        if preferred and isinstance(layout_results.get(preferred), dict):
            layout_png = layout_results[preferred].get("png")
        if layout_png is None:
            for style_key in ("raw_v05", "top_v10"):
                if isinstance(layout_results.get(style_key), dict):
                    layout_png = layout_results[style_key].get("png")
                if layout_png:
                    break
    sld_png = sld_png or st.session_state.get("sld_pro_png_bytes")
    layout_png = layout_png or st.session_state.get("layout_png_bytes")

    if not sld_png:
        st.info("SLD Pro PNG not found. Generate it in Single Line Diagram > Pro tab.")
    if not layout_png:
        st.info("Layout PNG not found. Generate it in Site Layout.")
