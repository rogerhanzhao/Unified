import streamlit as st
import pandas as pd
import math
from calb_sizing_tool.reporting.export_docx import create_ac_report, create_combined_report, make_report_filename
from calb_sizing_tool.models import ProjectSizingResult, ACBlockResult, DCBlockResult

def _reconstruct_degradation_table(target_mwh, years=20):
    """
    辅助函数：如果 Session 中没有完整的年度数据表，基于目标容量重建一个标准衰减表。
    确保生成报告时图表有数据可画。
    """
    data = []
    # 模拟 CALB 标准衰减曲线 (线性简化版用于兜底)
    # Year 0 = 100%, Year 20 ≈ 60%
    for y in range(years + 1):
        soh = 100.0 - (2.0 * y) 
        if soh < 60: soh = 60 # floor
        usable = target_mwh * (soh / 100.0)
        data.append({
            "Year": y,
            "SOH_Display_Pct": soh,
            "POI_Usable_Energy_MWh": usable
        })
    return pd.DataFrame(data)

def show():
    st.header("AC Block Sizing")
    
    # 1. 检查前置步骤 (DC Sizing 是否完成)
    if 'dc_result_summary' not in st.session_state:
        st.warning("⚠ Please complete 'DC Sizing' first.")
        st.info("Go to the DC Sizing tab, enter parameters, and click 'Run Sizing'.")
        st.stop()
        
    dc_data = st.session_state['dc_result_summary']
    
    # 获取 DC 计算的目标值，安全转换为 float
    # 注意：dc_data 里的键名可能因 dc_view 版本略有不同，这里做兼容处理
    target_mw = float(dc_data.get('target_mw', dc_data.get('poi_power_req_mw', 10.0)))
    target_mwh = float(dc_data.get('mwh', dc_data.get('poi_energy_req_mwh', 0.0)))
    
    # Retrieve DC model info
    # 如果 dc_view 里存的是 'dc_model' (Pydantic对象)，直接用
    # 如果存的是 'dc_block'，也兼容
    dc_model = dc_data.get('dc_model', dc_data.get('dc_block'))
    
    if not dc_model:
         # Fallback creation if object missing
         dc_model = DCBlockResult(
            block_id="DC-Gen", 
            capacity_mwh=5.015, 
            count=int(dc_data.get('container_count', 0)),
            voltage_v=1200
        )
    
    # Display Context
    st.info(f"Basis: DC System has {dc_model.count} x {dc_model.container_model} ({dc_model.capacity_mwh:.3f} MWh each).")

    # 2. AC 输入参数
    st.subheader("AC Parameters")
    
    with st.form("ac_sizing_form"):
        c1, c2 = st.columns(2)
        
        grid_kv = c1.number_input(
            "Grid Voltage (kV)", 
            min_value=1.0, value=33.0, step=0.1, format="%.1f",
            help="Medium Voltage (MV) at the collection bus / POI."
        )
        
        pcs_lv = c2.number_input(
            "PCS AC Output Voltage (LV bus, V)", 
            min_value=100.0, value=800.0, step=10.0, 
            help="Line-to-Line RMS voltage at PCS output."
        )
        
        ac_block_size = st.selectbox("Standard Block Size (MW)", [2.5, 3.44, 5.0, 6.88])
        
        submitted = st.form_submit_button("Run AC Sizing")

    if submitted:
        # 3. Calculation Logic (Precision Fixes)
        num_blocks = math.ceil(target_mw / ac_block_size)
        total_ac_capacity = num_blocks * ac_block_size
        overhead_mw = total_ac_capacity - target_mw
        
        # 4. Construct Full Sizing Result (Merging DC + AC)
        
        # Distribute DC blocks among AC blocks
        total_dc_count = dc_model.count
        dc_per_ac = 0
        if num_blocks > 0:
            dc_per_ac = max(1, total_dc_count // num_blocks)
        
        ac_blocks_list = []
        for i in range(num_blocks):
            # Create a copy of the DC block structure for this AC block
            dc_copy = dc_model.model_copy()
            dc_copy.count = dc_per_ac
            
            ac_blocks_list.append(ACBlockResult(
                block_id=f"Block-{i+1}",
                transformer_kva=ac_block_size * 1000 / 0.9, # Assuming 0.9 PF
                mv_voltage_kv=grid_kv,
                lv_voltage_v=pcs_lv,
                pcs_power_kw=ac_block_size * 1000 / 2, # Assume 2 PCS modules per block (simplified)
                num_pcs=2,
                dc_blocks_connected=[dc_copy]
            ))

        full_result = ProjectSizingResult(
            project_name=dc_data.get('project_name', "CALB ESS Project"),
            system_power_mw=target_mw,
            system_capacity_mwh=target_mwh,
            ac_blocks=ac_blocks_list
        )
        
        # Save to Session State (for SLD view & Downloads)
        st.session_state['ac_result_summary'] = {
            "result_object": full_result,
            "grid_kv": grid_kv,
            "block_size": ac_block_size
        }
        
        st.success("AC Sizing Complete.")

    # 5. Display Results (Only if available)
    if 'ac_result_summary' in st.session_state:
        res_summary = st.session_state['ac_result_summary']
        full_result = res_summary['result_object']
        
        # Re-calc metrics for display
        num_blocks = len(full_result.ac_blocks)
        block_size = res_summary['block_size']
        total_ac = num_blocks * block_size
        overhead = total_ac - full_result.system_power_mw
        
        st.divider()
        st.subheader("Sizing Results")
        
        k1, k2, k3 = st.columns(3)
        k1.metric("AC Block Configuration", f"{num_blocks} x {block_size:.2f} MW")
        k2.metric("Total AC Capacity", f"{total_ac:.2f} MW")
        k3.metric("Overhead Power", f"{overhead:.2f} MW")
        
        # Topology info
        dc_per_ac = 0
        if full_result.ac_blocks and full_result.ac_blocks[0].dc_blocks_connected:
            dc_per_ac = full_result.ac_blocks[0].dc_blocks_connected[0].count
            
        st.info(f"Topology: Each {block_size}MW AC Block connects to {dc_per_ac} DC Battery Containers.")
        
        # 6. Prepare Report Context
        # Try to get degradation table from DC session data
        deg_table = dc_data.get('stage3_df')
        if deg_table is None or deg_table.empty:
             deg_table = _reconstruct_degradation_table(full_result.system_capacity_mwh)
        
        # Merge inputs
        input_assumptions = dc_data.get('inputs', {}).copy()
        input_assumptions.update({
            "AC Grid Voltage": f"{res_summary['grid_kv']:.1f} kV",
            "AC Block Size": f"{block_size:.2f} MW",
            "AC Overhead": f"{overhead:.2f} MW"
        })
        
        report_context = {
            "degradation_table": deg_table,
            "inputs": input_assumptions,
            "dc_spec_raw": dc_data.get('raw_spec', {}) # Pass raw excel spec
        }

        # 7. Export Buttons
        st.subheader("Downloads")
        
        c_btn1, c_btn2 = st.columns(2)
        
        with c_btn1:
            ac_report_bytes = create_ac_report(full_result, report_context)
            st.download_button(
                "📄 Download AC Technical Report (DOCX)", 
                data=ac_report_bytes, 
                file_name="AC_Sizing_Report.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
            
        with c_btn2:
            combined_report_bytes = create_combined_report(
                full_result, 
                report_type="combined",
                extra_context=report_context
            )
            st.download_button(
                "📑 Download Complete Technical Proposal (DOCX)", 
                data=combined_report_bytes, 
                file_name="Technical_Proposal_Combined.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                type="primary" 
            )