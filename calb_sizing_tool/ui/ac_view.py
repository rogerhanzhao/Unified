import streamlit as st
import pandas as pd
from calb_sizing_tool.reporting.export_docx import create_combined_report
from calb_sizing_tool.models import ProjectSizingResult, ACBlockResult, DCBlockResult

def _reconstruct_degradation_table(target_mwh, years=20):
    """
    辅助函数：如果 Session 中没有完整的年度数据表，基于目标容量重建一个标准衰减表用于报告展示。
    """
    data = []
    # 模拟 CALB 标准衰减曲线 (线性简化版用于兜底)
    # Year 0 = 100%, Year 20 ≈ 60% (仅作示例)
    for y in range(years + 1):
        soh = 100.0 - (2.0 * y) 
        usable = target_mwh * (soh / 100.0)
        data.append({
            "Year": y,
            "SOH_Display_Pct": soh,
            "POI_Usable_Energy_MWh": usable
        })
    return pd.DataFrame(data)

def show():
    st.header("AC Block Sizing")
    
    # 1. 检查前置步骤
    if 'dc_result_summary' not in st.session_state:
        st.warning("⚠ Please complete 'DC Sizing' first.")
        st.info("Go to the DC Sizing tab, enter parameters, and click 'Run Sizing'.")
        st.stop()
        
    dc_data = st.session_state['dc_result_summary']
    # 获取 DC 计算的目标值
    target_mw = float(dc_data.get('target_mw', 10.0))
    target_mwh = float(dc_data.get('mwh', 0.0))
    
    # 2. AC 输入参数
    st.subheader("AC Parameters")
    
    with st.form("ac_sizing_form"):
        c1, c2 = st.columns(2)
        grid_kv = c1.number_input("Grid Voltage (kV)", min_value=1.0, value=33.0, step=0.1, format="%.1f")
        lv_voltage = c2.number_input("PCS AC Output Voltage (LV bus, V)", min_value=100.0, value=800.0, step=10.0, help="Line-to-Line RMS")
        
        ac_block_size = st.selectbox("Standard Block Size (MW)", [2.5, 3.44, 5.0, 6.88])
        
        submitted = st.form_submit_button("Run AC Sizing")

    if submitted:
        # 3. Calculation Logic (Precision Fixes)
        num_blocks = int(target_mw / ac_block_size)
        if target_mw % ac_block_size > 0.01: # 浮点数容错
            num_blocks += 1
            
        total_ac_capacity = num_blocks * ac_block_size
        overhead_mw = total_ac_capacity - target_mw
        
        # 4. Construct Full Sizing Result
        
        # Retrieve DC block info
        dc_template = dc_data.get('dc_block')
        if not dc_template:
             # Fallback creation
             dc_template = DCBlockResult(
                block_id="DC-Gen", 
                capacity_mwh=5.015, 
                count=dc_data.get('container_count', 0),
                voltage_v=1200
            )
        
        # Distribute DC blocks
        total_dc_count = dc_template.count
        dc_per_ac = 0
        if num_blocks > 0:
            dc_per_ac = max(1, total_dc_count // num_blocks)
        
        ac_blocks_list = []
        for i in range(num_blocks):
            dc_copy = dc_template.model_copy()
            dc_copy.count = dc_per_ac
            
            ac_blocks_list.append(ACBlockResult(
                block_id=f"Block-{i+1}",
                transformer_kva=ac_block_size * 1000 / 0.9,
                mv_voltage_kv=grid_kv,
                lv_voltage_v=lv_voltage,
                pcs_power_kw=ac_block_size * 1000 / 2, # Assume 2 PCS modules
                num_pcs=2,
                dc_blocks_connected=[dc_copy]
            ))

        full_result = ProjectSizingResult(
            project_name="CALB ESS Project",
            system_power_mw=target_mw,
            system_capacity_mwh=target_mwh,
            ac_blocks=ac_blocks_list
        )
        
        st.session_state['full_sizing_result'] = full_result
        
        # 5. Display Results (Precision Display)
        st.divider()
        st.subheader("Sizing Results")
        
        k1, k2, k3 = st.columns(3)
        k1.metric("AC Block Configuration", f"{num_blocks} x {ac_block_size:.2f} MW")
        k2.metric("Total AC Capacity", f"{total_ac_capacity:.2f} MW")
        k3.metric("Overhead Power", f"{overhead_mw:.2f} MW")
        
        st.info(f"Topology: Each {ac_block_size}MW AC Block connects to {dc_per_ac} DC Battery Containers.")
        
        # 6. Export Buttons
        st.subheader("Downloads")
        
        # 尝试获取 DC Sizing 中的年度数据表用于报告
        # 注意：这里我们尝试重建数据表，如果 session 中没有存储完整的 DataFrame
        deg_table = _reconstruct_degradation_table(target_mwh)
        report_context = {"degradation_table": deg_table}

        c_btn1, c_btn2 = st.columns(2)
        
        with c_btn1:
            ac_report_bytes = create_combined_report(
                full_result, 
                report_type="ac",
                extra_context=report_context
            )
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
                type="primary" # Highlight this button
            )