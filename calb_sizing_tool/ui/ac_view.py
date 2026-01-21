# -----------------------------------------------------------------------------
# Personal Open-Source Notice
#
# Copyright (c) 2026 Alex.Zhao. All rights reserved.
#
# This repository is released under the MIT License (see LICENSE file).
# Intended use: learning, evaluation, and engineering reference for Utility-scale
# BESS/ESS sizing and Reporting workflows.
#
# DISCLAIMER: This software is provided "AS IS", without warranty of any kind,
# express or implied. In no event shall the author(s) be liable for any claim,
# damages, or other liability arising from, out of, or in connection with the
# software or the use or other dealings in the software.
#
# NOTE: This is a personal project. It is not an official product or statement
# of any company or organization.
# -----------------------------------------------------------------------------

"""
AC SIZING V2 - 基于DC Block数量的推荐引擎
优先考虑 1:1, 1:2, 1:4 的搭配方案
"""
import math
from pathlib import Path

import pandas as pd
import streamlit as st

from calb_sizing_tool.common.allocation import allocate_dc_blocks, evenly_distribute
from calb_sizing_tool.models import DCBlockResult
from calb_sizing_tool.reporting.export_docx import (
    make_report_filename,
)
from calb_sizing_tool.reporting.report_v2 import export_report_v2_1
from calb_sizing_tool.state.project_state import bump_run_id_ac, init_project_state
from calb_sizing_tool.state.session_state import init_shared_state, set_run_time
from calb_sizing_tool.ui.ac_sizing_config import (
    ACBlockRatioOption,
    generate_ac_sizing_options,
    suggest_pcs_count_and_rating,
)


def _format_float(val, decimals=2) -> str:
    try:
        v = float(val or 0)
        return f"{v:.{decimals}f}"
    except Exception:
        return str(val)


def show():
    """AC SIZING V2 主函数"""
    state = init_shared_state()
    init_project_state()
    dc_results = state.dc_results
    ac_inputs = state.ac_inputs
    ac_results = state.ac_results

    st.header("⚡ AC Block Sizing (V2 - DC-First Approach)")

    # ========== STEP 1: Dependency & DC Summary ==========
    dc_data = st.session_state.get("dc_result_summary") or dc_results.get("dc_result_summary")
    stage13_output = st.session_state.get("stage13_output") or dc_results.get("stage13_output") or {}
    
    if not dc_data:
        st.warning("❌ DC sizing results not found.")
        st.info("Please run DC sizing first to determine DC Block count and capacity.")
        return

    try:
        dc_model = dc_data.get("dc_block")
        if not dc_model:
            dc_model = DCBlockResult(
                block_id="DC-Fallback",
                capacity_mwh=5.015,
                count=int(dc_data.get("container_count", 0)),
                voltage_v=1200,
            )

        # 关键数据来自DC Sizing
        dc_blocks_total = int(getattr(dc_model, "count", 0) or 0)  # ⭐ DC Block数量
        dc_block_mwh = float(getattr(dc_model, "capacity_mwh", 5.0) or 5.0)
        target_mw = float(dc_data.get("target_mw", stage13_output.get("poi_power_req_mw", 10.0)))
        target_mwh = float(dc_data.get("mwh", stage13_output.get("poi_energy_req_mwh", 0.0)))
        
    except Exception as exc:
        st.error(f"Data structure mismatch: {exc}")
        return

    project_name = (
        st.session_state.get("project_name")
        or ac_inputs.get("project_name")
        or stage13_output.get("project_name")
        or "CALB ESS Project"
    )
    st.session_state["project_name"] = project_name

    # ========== Display DC System Summary ==========
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("DC Blocks", f"{dc_blocks_total} × 20ft")
    col2.metric("DC Capacity", f"{dc_blocks_total * dc_block_mwh:.1f} MWh")
    col3.metric("POI Power Req.", f"{target_mw:.1f} MW")
    col4.metric("POI Energy Req.", f"{target_mwh:.0f} MWh")

    st.divider()

    # ========== STEP 2: Generate Options & Auto-select Best ==========
    st.subheader("🔧 AC Block Sizing Configuration")
    st.markdown("""
    System automatically recommends the best ratio based on your DC Block count.
    """)

    options = generate_ac_sizing_options(dc_blocks_total, target_mw, target_mwh, dc_block_mwh)

    # Auto-select the recommended option, or use saved selection
    selected_option = None
    if "selected_ac_ratio" in st.session_state:
        selected_ratio = st.session_state["selected_ac_ratio"]
        selected_option = next((o for o in options if o.ratio == selected_ratio), None)
    
    if selected_option is None:
        # Default to first recommended option
        for opt in options:
            if opt.is_recommended:
                selected_option = opt
                break
    
    if selected_option is None:
        selected_option = options[1]  # Fallback to option B (1:2)
    
    # Show ratio selection
    ratio_choices = [opt.ratio for opt in options]
    selected_ratio_idx = ratio_choices.index(selected_option.ratio) if selected_option.ratio in ratio_choices else 1
    
    col_ratio, col_desc = st.columns([1, 3])
    with col_ratio:
        choice_idx = st.selectbox(
            "AC:DC Ratio",
            range(len(ratio_choices)),
            index=selected_ratio_idx,
            format_func=lambda i: ratio_choices[i],
            help="Select the ratio of DC Blocks per AC Block (1:1, 1:2, or 1:4)"
        )
        if choice_idx != selected_ratio_idx:
            selected_option = options[choice_idx]
            st.session_state["selected_ac_ratio"] = selected_option.ratio
    
    with col_desc:
        st.info(selected_option.description)

    st.divider()

    # ========== STEP 3: Configure PCS for Selected Ratio ==========
    if selected_option:
        st.subheader(f"⚙️ PCS Configuration for {selected_option.ratio} Ratio")
        
        with st.form("ac_config_form"):
            col1, col2 = st.columns([2, 2])
            
            # PCS功率选择 from recommendations
            pcs_options = [f"{rec.readable}" for rec in selected_option.pcs_recommendations]
            pcs_options.append("🔧 Custom PCS Rating...")
            
            with col1:
                pcs_choice = st.selectbox(
                    "Select PCS Configuration",
                    range(len(pcs_options)),
                    format_func=lambda i: pcs_options[i],
                    help="Select from recommended configurations or enter custom PCS rating"
                )
                
                if pcs_choice < len(selected_option.pcs_recommendations):
                    chosen_rec = selected_option.pcs_recommendations[pcs_choice]
                    pcs_per_ac = chosen_rec.pcs_count
                    pcs_kw = chosen_rec.pcs_kw
                    st.write(f"**Selected**: {pcs_per_ac} × {pcs_kw} kW")
                else:
                    st.write("**Selected**: Custom configuration")
            
            with col2:
                if pcs_choice >= len(selected_option.pcs_recommendations):
                    st.write("**Enter Custom Values:**")
                    pcs_per_ac = st.number_input(
                        "PCS Count per AC Block",
                        min_value=1,
                        max_value=6,
                        value=2,
                        step=1,
                        key="custom_pcs_count"
                    )
                    pcs_kw = st.number_input(
                        "PCS Rating (kW)",
                        min_value=1000,
                        max_value=5000,
                        value=1500,
                        step=100,
                        key="custom_pcs_kw"
                    )
                else:
                    chosen_rec = selected_option.pcs_recommendations[pcs_choice]
                    pcs_per_ac = chosen_rec.pcs_count
                    pcs_kw = chosen_rec.pcs_kw
            
            # Container size info - based on SINGLE AC Block size
            single_block_ac_power = pcs_per_ac * pcs_kw / 1000  # MW per block
            # User requirement: > 5MW OR 4 PCS -> 40ft
            auto_container = "40ft" if single_block_ac_power > 5 or pcs_per_ac >= 4 else "20ft"
            st.info(f"**AC Block Container**: {auto_container} (Single block: {single_block_ac_power:.2f} MW, Total AC: {selected_option.ac_block_count * single_block_ac_power:.2f} MW)")
            
            submitted = st.form_submit_button("✅ Run AC Sizing", use_container_width=True)

        # ========== STEP 4: Calculation & Validation ==========
        if submitted:
            bump_run_id_ac()
            
            num_blocks = selected_option.ac_block_count
            pcs_per_block = pcs_per_ac
            block_size_mw = pcs_per_block * pcs_kw / 1000.0
            total_ac_mw = num_blocks * block_size_mw
            overhead = total_ac_mw - target_mw
            
            # Validation
            errors = []
            warnings = []
            
            # Check energy
            total_energy = dc_blocks_total * dc_block_mwh
            if total_energy < target_mwh * 0.95:
                errors.append(f"❌ Insufficient energy: {total_energy:.0f} MWh < {target_mwh:.0f} MWh")
            elif total_energy > target_mwh * 1.05:
                warnings.append(f"⚠️ Excess energy: {total_energy:.0f} MWh > {target_mwh:.0f} MWh (+{(total_energy/target_mwh-1)*100:.1f}%)")
            
            # Check power - overhead based on POI requirement, not single block
            if total_ac_mw < target_mw * 0.95:
                errors.append(f"❌ Insufficient power: {total_ac_mw:.1f} MW < {target_mw:.1f} MW")
            elif overhead > target_mw * 0.3:
                warnings.append(f"⚠️ Power overhead: {overhead:.1f} MW ({overhead/target_mw*100:.0f}% of POI requirement)")
            
            # Display errors
            if errors:
                for err in errors:
                    st.error(err)
                st.stop()
            
            # Display warnings
            if warnings:
                with st.expander("⚠️ Warnings"):
                    for warn in warnings:
                        st.warning(warn)
            
            # ========== Results Summary ==========
            st.success("✅ AC Configuration Complete!")
            st.divider()
            
            # Key metrics
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("AC Blocks", num_blocks)
            col2.metric("PCS per Block", pcs_per_block)
            col3.metric("AC Power per Block", f"{block_size_mw:.2f} MW")
            col4.metric("Total AC Power", f"{total_ac_mw:.2f} MW")
            
            # Configuration summary
            st.subheader("📋 Sizing Summary")
            summary_cols = st.columns(2)
            
            with summary_cols[0]:
                st.write("**DC Side:**")
                st.write(f"- Total DC Blocks: {dc_blocks_total} × 20ft")
                st.write(f"- DC Blocks per AC Block: ~{dc_blocks_total/num_blocks:.1f} avg")
                st.write(f"- Total DC Energy: {dc_blocks_total * dc_block_mwh:.1f} MWh")
            
            with summary_cols[1]:
                st.write("**AC Side:**")
                st.write(f"- Total AC Blocks: {num_blocks}")
                st.write(f"- PCS Configuration: {pcs_per_block} × {pcs_kw} kW")
                st.write(f"- Total AC Power: {total_ac_mw:.2f} MW")
            
            st.write("**Container Type:** " + ("40ft" if block_size_mw > 5 or pcs_per_block >= 4 else "20ft") + " per AC Block")
            st.divider()
            
            
            # Store results in session state
            
            # --- DETAILED DC ALLOCATION ---
            # Create the detailed DC allocation plan the SLD view needs.
            dc_blocks_per_ac_block_list = evenly_distribute(dc_blocks_total, num_blocks)
            dc_allocation_plan = []
            for i, num_dc in enumerate(dc_blocks_per_ac_block_list):
                feeder_allocations = allocate_dc_blocks(num_dc, pcs_per_block)
                dc_allocation_plan.append(
                    {
                        "ac_block_index": i + 1,
                        "dc_blocks_total": num_dc,
                        "feeder_allocations": feeder_allocations,
                    }
                )

            ac_output = {
                "project_name": project_name,
                "selected_ratio": selected_option.ratio,
                "num_blocks": num_blocks,
                "pcs_per_block": pcs_per_block,
                "pcs_kw": pcs_kw,
                "block_size_mw": block_size_mw,
                "total_ac_mw": total_ac_mw,
                "overhead_mw": overhead,
                "dc_blocks_per_ac": selected_option.dc_blocks_per_ac,
                "dc_allocation_plan": dc_allocation_plan,  # ⭐ NEW DETAILED PLAN
                "poi_power_mw": target_mw,
                "poi_energy_mwh": target_mwh,
                "mv_kv": float(st.session_state.get("grid_kv", 33.0)),
                "lv_v": float(st.session_state.get("pcs_lv_v", 690.0)),
                "transformer_count": num_blocks,
                "pcs_count_total": num_blocks * pcs_per_block,
            }
            
            st.session_state["ac_output"] = ac_output
            ac_results.update(ac_output)
            set_run_time("ac_results")
            
            st.info("✅ Configuration saved. Proceed to SLD generation and report export.")

