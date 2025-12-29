import math
from pathlib import Path

import pandas as pd
import streamlit as st

from calb_sizing_tool.common.allocation import allocate_dc_blocks, evenly_distribute
from calb_sizing_tool.models import DCBlockResult
from calb_sizing_tool.reporting.export_docx import (
    create_ac_report,
    create_combined_report,
    make_report_filename,
    make_proposal_filename,
)
from calb_sizing_tool.reporting.report_context import build_report_context
from calb_sizing_tool.reporting.report_v2 import export_report_v2_1
from calb_sizing_tool.state.project_state import bump_run_id_ac, init_project_state
from calb_sizing_tool.state.session_state import init_shared_state, set_run_time


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
    state = init_shared_state()
    init_project_state()
    dc_results = state.dc_results
    ac_inputs = state.ac_inputs
    ac_results = state.ac_results

    st.header("AC Block Sizing")

    # 1. Dependency Check
    dc_data = st.session_state.get("dc_result_summary") or dc_results.get("dc_result_summary")
    stage13_output = st.session_state.get("stage13_output") or dc_results.get("stage13_output") or {}
    if not dc_data:
        st.warning("DC sizing results not found.")
        st.info("Please run DC sizing first.")
        return

    # Retrieve data from session state
    dc_data = dc_data or {}
    stage13_output = stage13_output or {}

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

    project_name = (
        st.session_state.get("project_name")
        or ac_inputs.get("project_name")
        or stage13_output.get("project_name")
        or "CALB ESS Project"
    )
    st.session_state["project_name"] = project_name

    # Display Context
    st.info(
        f"Basis: DC system has {dc_model.count} x {dc_model.container_model} "
        f"({dc_model.capacity_mwh:.3f} MWh each)."
    )

    def _init_input(field: str, default_value):
        key = f"ac_inputs.{field}"
        if key not in st.session_state:
            st.session_state[key] = default_value
        if field not in ac_inputs:
            ac_inputs[field] = st.session_state[key]
        return key

    # 2. Inputs Form
    with st.form("ac_sizing_form"):
        st.subheader("Electrical Parameters")
        c1, c2 = st.columns(2)

        grid_kv = c1.number_input(
            "Grid Voltage (kV)",
            min_value=1.0,
            key=_init_input(
                "grid_kv",
                float(
                    ac_inputs.get("grid_kv")
                    or ac_results.get("mv_kv")
                    or stage13_output.get("poi_nominal_voltage_kv", 33.0)
                ),
            ),
            step=0.1,
            help="Medium Voltage (MV) at the collection bus / POI.",
        )
        ac_inputs["grid_kv"] = grid_kv

        pcs_lv = c2.number_input(
            "PCS AC Output Voltage (LV bus, V_LL,rms)",
            min_value=200.0,
            key=_init_input(
                "lv_voltage_v",
                float(
                    ac_inputs.get("lv_voltage_v")
                    or ac_inputs.get("pcs_lv_v")
                    or ac_results.get("lv_voltage_v")
                    or ac_results.get("lv_v")
                    or 690.0
                ),
            ),
            step=10.0,
            help="AC-side low-voltage bus voltage at PCS output.",
        )
        ac_inputs["lv_voltage_v"] = pcs_lv
        ac_inputs["pcs_lv_v"] = pcs_lv

        st.subheader("Configuration")
        
        # PCS Specifications (standard sizes)
        pcs_specs = {
            "1250 kW": 1250,
            "1500 kW": 1500,
            "1725 kW": 1725,
            "2000 kW": 2000,
            "2500 kW": 2500,
        }
        pcs_default_name = ac_inputs.get("pcs_model", "2500 kW")
        if pcs_default_name not in pcs_specs:
            pcs_default_name = "2500 kW"
        
        pcs_model = st.selectbox(
            "PCS Module Rating",
            list(pcs_specs.keys()),
            index=list(pcs_specs.keys()).index(pcs_default_name),
            key=_init_input("pcs_model", pcs_default_name),
            help="Select standard PCS module size (kW)",
        )
        ac_inputs["pcs_model"] = pcs_model
        pcs_power_kw = pcs_specs[pcs_model]
        
        # PCS per AC Block - fixed to 2 or 4
        pcs_per_block_options = [2, 4]
        pcs_default = ac_inputs.get("pcs_per_block") or ac_results.get("pcs_per_block") or 4
        if pcs_default not in pcs_per_block_options:
            pcs_default = 4
        
        pcs_per_block = st.selectbox(
            "PCS per AC Block",
            pcs_per_block_options,
            index=pcs_per_block_options.index(int(pcs_default)),
            key=_init_input("pcs_per_block", int(pcs_default)),
            help="AC Block composition: 2 or 4 PCS modules",
        )
        ac_inputs["pcs_per_block"] = int(pcs_per_block)
        
        # Calculate AC Block size from PCS specs
        block_size_mw = (pcs_power_kw * pcs_per_block) / 1000.0
        ac_inputs["block_size_mw"] = block_size_mw
        
        # Container size selector (auto-suggest based on total power)
        st.write(f"**AC Block Size**: {block_size_mw:.2f} MW (from {int(pcs_per_block)} × {pcs_model})")

        submitted = st.form_submit_button("Run AC Sizing")

    # 3. Calculation & Results
    if submitted:
        bump_run_id_ac()
        ac_inputs["project_name"] = project_name
        ac_inputs["grid_kv"] = float(grid_kv)
        ac_inputs["lv_voltage_v"] = float(pcs_lv)
        ac_inputs["pcs_lv_v"] = float(pcs_lv)
        ac_inputs["block_size_mw"] = float(block_size_mw)  # From PCS specs calculation
        st.session_state["project_name"] = project_name

        num_blocks = math.ceil(target_mw / block_size_mw) if block_size_mw > 0 else 0
        total_ac_mw = num_blocks * block_size_mw
        overhead = total_ac_mw - target_mw

        dc_per_ac = 0
        if num_blocks > 0:
            dc_per_ac = max(1, dc_model.count // num_blocks)

        pcs_per_block = int(pcs_per_block)
        # pcs_power_kw is already set from PCS specs (not calculated)
        transformer_kva = block_size_mw * 1000 / 0.9
        total_pcs = num_blocks * pcs_per_block

        pcs_count_by_block = evenly_distribute(total_pcs, num_blocks)
        dc_blocks_total = int(getattr(dc_model, "count", 0) or 0)
        dc_blocks_total_by_block = evenly_distribute(dc_blocks_total, num_blocks)
        dc_blocks_per_feeder_by_block = []
        for idx, block_pcs in enumerate(pcs_count_by_block):
            block_dc_total = dc_blocks_total_by_block[idx] if idx < len(dc_blocks_total_by_block) else 0
            dc_blocks_per_feeder_by_block.append(allocate_dc_blocks(block_dc_total, block_pcs))

        dc_block_mwh_each = float(getattr(dc_model, "capacity_mwh", 0.0) or 0.0)
        pcs_count_primary = pcs_count_by_block[0] if pcs_count_by_block else pcs_per_block
        pcs_units = [
            {"id": f"PCS-{idx + 1}", "rating_kw_or_kva": pcs_power_kw}
            for idx in range(max(1, int(pcs_count_primary)))
        ]

        per_ac_block = []
        for block_index, feeder_counts in enumerate(dc_blocks_per_feeder_by_block, start=1):
            block_total = int(sum(feeder_counts))
            per_feeder = {
                f"F{idx + 1}": int(count) for idx, count in enumerate(feeder_counts)
            }
            per_pcs_group = [
                {"pcs_id": f"PCS-{idx + 1}", "dc_block_count": int(count)}
                for idx, count in enumerate(feeder_counts)
            ]
            per_ac_block.append(
                {
                    "block_id": f"B{block_index}",
                    "dc_blocks_total": block_total,
                    "per_feeder": per_feeder,
                    "per_pcs_group": per_pcs_group,
                }
            )

        primary_block = per_ac_block[0] if per_ac_block else {
            "dc_blocks_total": 0,
            "per_feeder": {},
            "per_pcs_group": [],
        }
        dc_block_allocation = {
            "total_dc_blocks": primary_block["dc_blocks_total"],
            "per_feeder": primary_block["per_feeder"],
            "per_pcs_group": primary_block["per_pcs_group"],
            "per_ac_block": per_ac_block,
            "site_total_dc_blocks": dc_blocks_total,
        }
        transformer_mva = round(transformer_kva / 1000.0, 1) if transformer_kva else 0.0

        ac_output = {
            "project_name": project_name,
            "poi_power_mw": target_mw,
            "poi_energy_mwh": target_mwh,
            "grid_kv": grid_kv,
            "inverter_lv_v": pcs_lv,
            "mv_voltage_kv": grid_kv,
            "lv_voltage_v": pcs_lv,
            "mv_kv": grid_kv,
            "lv_v": pcs_lv,
            "block_size_mw": block_size_mw,
            "num_blocks": num_blocks,
            "total_ac_mw": total_ac_mw,
            "overhead_mw": overhead,
            "pcs_power_kw": pcs_power_kw,
            "pcs_rating_kw_each": pcs_power_kw,
            "pcs_per_block": pcs_per_block,
            "pcs_count_per_ac_block": pcs_count_primary,
            "pcs_units": pcs_units,
            "pcs_count_by_block": pcs_count_by_block,
            "total_pcs": total_pcs,
            "pcs_count_total": total_pcs,
            "transformer_kva": transformer_kva,
            "transformer_mva": transformer_mva,
            "transformer_count": num_blocks,
            "dc_blocks_per_ac": dc_per_ac,
            "dc_blocks_total_by_block": dc_blocks_total_by_block,
            "dc_blocks_per_feeder_by_block": dc_blocks_per_feeder_by_block,
            "dc_block_allocation": dc_block_allocation,
            "dc_block_allocation_by_feeder": primary_block.get("per_feeder"),
            "dc_block_mwh_each": dc_block_mwh_each,
            "dc_block_energy_mwh_each": dc_block_mwh_each,
            "mv_level_kv": grid_kv,
        }

        st.session_state["ac_output"] = ac_output
        ac_results.update(ac_output)
        set_run_time("ac_results")

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
    ac_output = st.session_state.get("ac_output") or ac_results or {}
    if ac_output:

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
        if sld_png is None:
            sld_png = st.session_state.get("sld_pro_png_bytes")
        if sld_svg is None:
            sld_svg = (
                st.session_state.get("sld_pro_jp_svg_bytes")
                or st.session_state.get("sld_raw_svg_bytes")
            )

        outputs_dir = Path("outputs")
        if sld_png is None:
            candidate = outputs_dir / "sld_latest.png"
            if candidate.exists():
                sld_png = candidate.read_bytes()
        if sld_svg is None:
            candidate = outputs_dir / "sld_latest.svg"
            if candidate.exists():
                sld_svg = candidate.read_bytes()

        layout_entry = None
        if isinstance(layout_results, dict) and layout_results:
            preferred = layout_results.get("last_style")
            if preferred and isinstance(layout_results.get(preferred), dict):
                layout_entry = layout_results.get(preferred)
            if layout_entry is None:
                for style_key in ("raw_v05", "top_v10"):
                    entry = layout_results.get(style_key)
                    if isinstance(entry, dict) and (entry.get("png") or entry.get("svg")):
                        layout_entry = entry
                        break
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
        if layout_svg is None:
            candidate = outputs_dir / "layout_latest.svg"
            if candidate.exists():
                layout_svg = candidate.read_bytes()

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
        
        # V2.1 is now the only report format
        c_d1, c_d2 = st.columns(2)

        with c_d1:
            st.info("Report downloads (V2.1 format only)")

        with c_d2:
            if not stage13_output:
                st.info("Run DC sizing to enable the combined report.")
            else:
                ctx = build_report_context(
                    session_state=st.session_state,
                    stage_outputs={
                        "stage13_output": stage13_output,
                        "stage2": stage13_output.get("stage2_raw", {}),
                        "ac_output": ac_output,
                    },
                    project_inputs={
                        "poi_power_mw": stage13_output.get("poi_power_req_mw"),
                        "poi_energy_mwh": stage13_output.get("poi_energy_req_mwh"),
                        "poi_energy_guarantee_mwh": stage13_output.get("poi_energy_req_mwh"),
                        "poi_guarantee_year": stage13_output.get("poi_guarantee_year"),
                    },
                    scenario_ids=stage13_output.get("selected_scenario"),
                )
                comb_bytes = export_report_v2_1(ctx)
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


def _format_float(value, decimals):
    if value is None:
        return ""
    try:
        return f"{float(value):.{decimals}f}"
    except Exception:
        return str(value)
