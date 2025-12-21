import streamlit as st
from calb_sizing_tool.sld.visualizer import generate_sld

def show():
    st.header("Single Line Diagram")
    
    if 'full_sizing_result' not in st.session_state:
        st.warning("Run AC Sizing to generate topology.")
        return
        
    res = st.session_state['full_sizing_result']
    
    if st.button("Generate Diagram"):
        try:
            dot = generate_sld(res)
            st.graphviz_chart(dot, use_container_width=True)
        except Exception as e:
            st.error(f"Graphviz Error: {e}")
            st.caption("Ensure Graphviz executables are installed on the server.")