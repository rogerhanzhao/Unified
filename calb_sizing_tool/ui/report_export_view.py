from pathlib import Path

import streamlit as st
from calb_sizing_tool.reporting.export_docx import (
    make_proposal_filename,
)
from calb_sizing_tool.reporting.report_context import build_report_context
from calb_sizing_tool.reporting.report_v2 import export_report_v2_1
from calb_sizing_tool.state.project_state import init_project_state
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
    state = init_shared_state()
    init_project_state()
    dc_results = state.dc_results or {}
    ac_results = state.ac_results or {}
    diagram_results = st.session_state.get("diagram_results", {}) or {}
    layout_results = st.session_state.get("layout_results", {}) or {}
    artifacts = state.artifacts
    sld_entry = None
    if isinstance(diagram_results, dict) and diagram_results:
        preferred = diagram_results.get("last_style")
        if preferred and isinstance(diagram_results.get(preferred), dict):
            sld_entry = diagram_results.get(preferred)
        if sld_entry is None:
            for style_key in ("raw_v05", "pro_v10", "jp_v08"):
                entry = diagram_results.get(style_key)
                if isinstance(entry, dict) and (entry.get("png") or entry.get("svg")):
                    sld_entry = entry
                    break
    sld_png = artifacts.get("sld_png_bytes") or (sld_entry.get("png") if sld_entry else None)
    sld_svg = artifacts.get("sld_svg_bytes") or (sld_entry.get("svg") if sld_entry else None)
    outputs_dir = Path("outputs")
    if sld_png is None:
        candidate = outputs_dir / "sld_latest.png"
        if candidate.exists():
            sld_png = candidate.read_bytes()
            artifacts["sld_png_bytes"] = sld_png
    if sld_svg is None:
        candidate = outputs_dir / "sld_latest.svg"
        if candidate.exists():
            sld_svg = candidate.read_bytes()
            artifacts["sld_svg_bytes"] = sld_svg

    layout_entry = None
    if isinstance(layout_results, dict) and layout_results:
        preferred = layout_results.get("last_style")
        if preferred and isinstance(layout_results.get(preferred), dict):
            layout_entry = layout_results.get(preferred)
        if layout_entry is None:
            entry = layout_results.get("raw_v05")
            if isinstance(entry, dict) and (entry.get("png") or entry.get("svg")):
                layout_entry = entry
    layout_png = artifacts.get("layout_png_bytes") or (layout_entry.get("png") if layout_entry else None)
    layout_svg = artifacts.get("layout_svg_bytes") or (layout_entry.get("svg") if layout_entry else None)
    if layout_png is None:
        layout_png = st.session_state.get("layout_png_bytes")
    if layout_svg is None:
        layout_svg = st.session_state.get("layout_svg_bytes")
    if layout_png is None:
        candidate = outputs_dir / "layout_latest.png"
        if candidate.exists():
            layout_png = candidate.read_bytes()
            artifacts["layout_png_bytes"] = layout_png
    if layout_svg is None:
        candidate = outputs_dir / "layout_latest.svg"
        if candidate.exists():
            layout_svg = candidate.read_bytes()
            artifacts["layout_svg_bytes"] = layout_svg

    st.header("Report Export")
    st.caption("Generate unified V2.1 DOCX report with full AC and DC analysis.")

    stage13_output = (
        dc_results.get("stage13_output")
        or st.session_state.get("stage13_output")
        or {}
    )
    ac_output = ac_results or st.session_state.get("ac_output") or {}

    if not stage13_output or not ac_output:
        st.warning("Run DC sizing and AC sizing first to enable report export.")
        return

    project_name = None
    project = st.session_state.get("project")
    if isinstance(project, dict):
        project_name = project.get("name")
    project_name = (
        project_name
        or st.session_state.get("project_name")
        or stage13_output.get("project_name")
        or ac_output.get("project_name")
        or "CALB ESS Project"
    )
    st.session_state["project_name"] = project_name

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
        "tool_version": "V1.0",
        "sld_png_bytes": sld_png,
        "sld_svg_bytes": sld_svg,
        "layout_png_bytes": layout_png,
        "layout_svg_bytes": layout_svg,
    }

    st.subheader("Downloads")
    
    # V2.1 is now the standard report format
    report_template = "V2.1 (Beta)"
    
    c_d1, c_d2 = st.columns(2)

    with c_d1:
        st.info("AC Report generation moved to V2.1 format only.")

    with c_d2:
        stage2_raw = stage13_output.get("stage2_raw", {})
        block_code, block_name = _extract_block_identity(stage2_raw)

        # Build comprehensive project inputs from stage13_output
        project_inputs_for_report = {
            "project_name": project_name,
            "poi_power_mw": stage13_output.get("poi_power_req_mw"),
            "poi_energy_mwh": stage13_output.get("poi_energy_req_mwh"),
            "poi_energy_guarantee_mwh": stage13_output.get("poi_energy_req_mwh"),
            "poi_guarantee_year": stage13_output.get("poi_guarantee_year"),
            "poi_frequency_hz": stage13_output.get("poi_frequency_hz"),
        }
        ctx = build_report_context(
            session_state=st.session_state,
            stage_outputs={
                "stage13_output": stage13_output,
                "stage2": stage13_output.get("stage2_raw", {}),
                "ac_output": ac_output,
                "sld_snapshot": st.session_state.get("sld_snapshot"),
            },
            project_inputs=project_inputs_for_report,
            scenario_ids=stage13_output.get("selected_scenario", "container_only"),
        )
        comb_bytes = export_report_v2_1(ctx)
        file_suffix = "Combined_V2_1"
        button_label = "Download Combined Report V2.1"

        version = "V2.1"
        proposal_filename = make_proposal_filename(project_name, version=version)
        st.download_button(
            button_label,
            comb_bytes,
            proposal_filename,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            type="primary",
        )

    if not sld_png and not sld_svg:
        st.info("SLD image not found. Generate it in Single Line Diagram.")
    if not layout_png and not layout_svg:
        st.info("Layout image not found. Generate it in Site Layout.")
