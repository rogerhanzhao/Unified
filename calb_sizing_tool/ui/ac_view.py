import streamlit as st
import pandas as pd
import math
from calb_sizing_tool.reporting.export_docx import create_ac_report, create_combined_report, make_report_filename
from calb_sizing_tool.models import ProjectSizingResult, ACBlockResult, DCBlockResult

def show():
    st.header("AC Block Sizing")
    
    # 1. Dependency Check
    if 'dc_result_summary' not in st.session_state:
        st.warning("⚠ DC Sizing results not found.")
        st.info("Please go to the 'DC Sizing' page and run the calculation first.")
        return

    # Retrieve data from session state
    dc_data = st.session_state['dc_result_summary']
    try:
        # Access using standard keys defined in DC View
        # Use .get() with defaults to avoid KeyErrors if partial data exists
        dc_model = dc_data.get('dc_model')
        if not dc_model:
             # Fallback if model object missing but counts exist
             dc_model = DCBlockResult(
                block_id="DC-Fallback", 
                capacity_mwh=5.015, 
                count=int(dc_data.get('container_count', 0)),
                voltage_v=1200
            )
            
        target_mw = float(dc_data.get('target_mw', 10.0))
        target_mwh = float(dc_data.get('mwh', 0.0))
        
    except Exception as e:
        st.error(f"Data structure mismatch: {e}. Please re-run DC Sizing.")
        return
    
    # Display Context
    st.info(f"Basis: DC System has {dc_model.count} x {dc_model.container_model} ({dc_model.capacity_mwh:.3f} MWh each).")
    
    # 2. Inputs Form
    with st.form("ac_sizing_form"):
        st.subheader("Electrical Parameters")
        c1, c2 = st.columns(2)
        
        grid_kv = c1.number_input(
            "Grid Voltage (kV)", 
            min_value=1.0, value=33.0, step=0.1, 
            help="Medium Voltage (MV) at the collection bus / POI."
        )
        
        pcs_lv = c2.number_input(
            "PCS AC Output Voltage (LV bus, V_LL,rms)", 
            min_value=200.0, value=800.0, step=10.0,
            help="AC-side low-voltage bus voltage at PCS output."
        )
        
        st.subheader("Configuration")
        block_size = st.selectbox("Standard AC Block Size (MW)", [2.5, 3.44, 5.0, 6.88])
        
        submitted = st.form_submit_button("Run AC Sizing")
        
    # 3. Calculation & Results
    if submitted:
        # Basic Calc
        num_blocks = math.ceil(target_mw / block_size)
        total_ac_mw = num_blocks * block_size
        overhead = total_ac_mw - target_mw
        
        # Build Model
        # Distribute DC blocks evenly across AC blocks
        dc_per_ac = 0
        if num_blocks > 0:
            dc_per_ac = max(1, dc_model.count // num_blocks)
        
        ac_blocks_list = []
        for i in range(num_blocks):
            # Clone DC model for specific block attachment
            dc_copy = dc_model.model_copy()
            dc_copy.count = dc_per_ac
            
            # Create AC Block
            ac_blk = ACBlockResult(
                block_id=f"ACB-{i+1}",
                transformer_kva=block_size * 1000 / 0.9, # Approx MVA
                mv_voltage_kv=grid_kv,
                lv_voltage_v=pcs_lv,
                pcs_power_kw=block_size * 1000 / 2, # Assume 2 PCS modules per block standard
                num_pcs=2,
                dc_blocks_connected=[dc_copy]
            )
            ac_blocks_list.append(ac_blk)
            
        # Create Full Result Object
        full_result = ProjectSizingResult(
            project_name=dc_data.get('project_name', 'CALB Project'),
            system_power_mw=target_mw,
            system_capacity_mwh=target_mwh,
            ac_blocks=ac_blocks_list
        )
        
        # Save to Session State
        st.session_state['ac_result_summary'] = {
            "result_object": full_result,
            "grid_kv": grid_kv,
            "block_size": block_size
        }
        
        st.divider()
        st.subheader("AC Configuration Results")
        k1, k2, k3 = st.columns(3)
        k1.metric("AC Blocks", f"{num_blocks} x {block_size} MW")
        k2.metric("Total AC Power", f"{total_ac_mw:.2f} MW")
        k3.metric("Overhead Margin", f"{overhead:.2f} MW")
        
        # Topology info
        st.info(f"Topology: Each {block_size}MW AC Block connects to {dc_per_ac} DC Battery Containers.")
        
        st.success("AC Sizing Complete. Reports ready for download.")

    # 4. Downloads
    if 'ac_result_summary' in st.session_state:
        res_summary = st.session_state['ac_result_summary']
        res_obj = res_summary['result_object']
        
        # Reconstruct context from DC data
        # Ensure fallback for degradation table if missing
        deg_table = dc_data.get('stage3_df')
        if deg_table is None:
             # Simple reconstruction if real data missing
             years = list(range(21))
             deg_table = pd.DataFrame({
                 'Year': years, 
                 'SOH_Display_Pct': [100-2*y for y in years],
                 'POI_Usable_Energy_MWh': [target_mwh*(1-0.02*y) for y in years]
             })

        ctx = {
            "degradation_table": deg_table,
            "inputs": dc_data.get('inputs', {}).copy(),
            "dc_spec_raw": dc_data.get('raw_spec', {})
        }
        
        # Update inputs with AC params
        ctx['inputs'].update({
            "AC Grid Voltage": f"{res_summary['grid_kv']} kV",
            "AC Block Size": f"{res_summary['block_size']} MW"
        })
        
        st.subheader("Downloads")
        c_d1, c_d2 = st.columns(2)
        
        with c_d1:
            # FIX: Correct function call (2 arguments)
            ac_bytes = create_ac_report(res_obj, ctx)
            
            st.download_button(
                "📄 Download AC Technical Report (DOCX)",
                ac_bytes,
                make_report_filename(res_obj.project_name, "AC"),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
            
        with c_d2:
            # FIX: Correct function call (2 arguments)
            comb_bytes = create_combined_report(res_obj, ctx)
            
            st.download_button(
                "📑 Download Combined Report (DC+AC)",
                comb_bytes,
                make_report_filename(res_obj.project_name, "Combined"),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                type="primary"
            )