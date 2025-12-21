import streamlit as st
import pandas as pd
from calb_sizing_tool.reporting.export_docx import create_combined_report
from calb_sizing_tool.models import ProjectSizingResult, ACBlockResult, DCBlockResult

def show():
    st.header("AC Block Sizing")
    
    # 1. 检查前置步骤
    if 'dc_result_summary' not in st.session_state:
        st.warning("⚠ Please complete 'DC Sizing' first.")
        st.info("Go to the DC Sizing tab, enter parameters, and click 'Run Sizing'.")
        st.stop()
        
    dc_data = st.session_state['dc_result_summary']
    target_mw = dc_data.get('target_mw', 10.0)
    
    # 2. AC 输入参数
    st.subheader("AC Parameters")
    
    # 创建表单以进行计算
    with st.form("ac_sizing_form"):
        c1, c2 = st.columns(2)
        grid_kv = c1.number_input("Grid Voltage (kV)", min_value=1.0, value=33.0, step=0.1)
        lv_voltage = c2.number_input("PCS AC Output Voltage (LV bus, V_LL,rms)", min_value=100.0, value=800.0, step=10.0, help="This is the AC-side low-voltage bus voltage at PCS output feeding the step-up transformer LV winding (Line-to-Line RMS).")
        
        ac_block_size = st.selectbox("Standard Block Size (MW)", [2.5, 3.44, 5.0, 6.88])
        
        submitted = st.form_submit_button("Run AC Sizing")

    if submitted:
        # 3. Calculation Logic
        num_blocks = int(target_mw / ac_block_size)
        if target_mw % ac_block_size > 0.1:
            num_blocks += 1
            
        total_ac_capacity = num_blocks * ac_block_size
        overhead_mw = total_ac_capacity - target_mw
        
        # 4. Construct Full Sizing Result (Merging DC + AC)
        
        # Retrieve DC block info from DC view
        # Fallback if object is missing
        dc_template = dc_data.get('dc_block')
        if not dc_template:
             dc_template = DCBlockResult(
                block_id="DC-Gen", 
                capacity_mwh=5.0, 
                count=dc_data.get('container_count', 0),
                voltage_v=1200
            )
        
        # Distribute DC blocks among AC blocks
        total_dc_count = dc_template.count
        dc_per_ac = max(1, total_dc_count // num_blocks)
        
        ac_blocks_list = []
        for i in range(num_blocks):
            # Create a copy of the DC block structure for this AC block
            # Note: In a real scenario, we might handle remainders more precisely
            dc_copy = dc_template.model_copy()
            dc_copy.count = dc_per_ac
            
            ac_blocks_list.append(ACBlockResult(
                block_id=f"Block-{i+1}",
                transformer_kva=ac_block_size * 1000 / 0.9, # Assuming 0.9 PF
                mv_voltage_kv=grid_kv,
                lv_voltage_v=lv_voltage,
                pcs_power_kw=ac_block_size * 1000 / 2, # Assume 2 PCS per block
                num_pcs=2,
                dc_blocks_connected=[dc_copy]
            ))

        full_result = ProjectSizingResult(
            project_name="CALB ESS Project",
            system_power_mw=target_mw,
            system_capacity_mwh=dc_data.get('mwh', 0),
            ac_blocks=ac_blocks_list
        )
        
        # Save to Session State
        st.session_state['full_sizing_result'] = full_result
        
        # 5. Display Results
        st.divider()
        st.subheader("Sizing Results")
        
        k1, k2, k3 = st.columns(3)
        k1.metric("AC Block Count", f"{num_blocks} x {ac_block_size} MW")
        k2.metric("Total AC Capacity", f"{total_ac_capacity:.2f} MW")
        k3.metric("Overhead", f"{overhead_mw:.2f} MW")
        
        # 6. Export Buttons
        st.subheader("Downloads")
        c_btn1, c_btn2 = st.columns(2)
        
        with c_btn1:
            ac_report_bytes = create_combined_report(full_result, report_type="ac")
            st.download_button(
                "📄 Download AC Technical Report (DOCX)", 
                data=ac_report_bytes, 
                file_name="AC_Sizing_Report.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
            
        with c_btn2:
            combined_report_bytes = create_combined_report(full_result, report_type="combined")
            st.download_button(
                "📑 Download Combined Report (DC+AC)", 
                data=combined_report_bytes, 
                file_name="Combined_Sizing_Report.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )