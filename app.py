import streamlit as st
from pathlib import Path
import calb_sizing_tool.config # Init config

st.set_page_config(page_title="CALB ESS Platform", layout="wide")

with st.sidebar:
    if Path("calb_logo.png").exists():
        st.image("calb_logo.png", width=200)
    st.title("Navigation")
    page = st.radio("Go to", ["Dashboard", "DC Sizing", "AC Sizing", "Single Line Diagram"])

if page == "Dashboard":
    st.title("ESS Sizing Platform")
    st.info("Start with DC Sizing -> AC Sizing -> SLD.")

elif page == "DC Sizing":
    from calb_sizing_tool.ui.dc_view import show
    show()

elif page == "AC Sizing":
    from calb_sizing_tool.ui.ac_view import show
    show()

elif page == "Single Line Diagram":
    from calb_sizing_tool.ui.sld_view import show
    show()