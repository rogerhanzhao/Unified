import os
import runpy

import streamlit as st

if not st.session_state.get("_dc_page_configured"):
    st.set_page_config(page_title="CALB ESS Sizing Tool – Stage 1–3 (DC)", layout="wide")
    st.session_state["_dc_page_configured"] = True

st.sidebar.title("Navigation")
nav_option = st.sidebar.radio(
    "Select Page",
    ("Stage 1–3 Inputs", "DC Block Sizing"),
    help="Toggle between input form and DC block sizing/export on a single page.",
)

st.session_state["dc_nav_external"] = True
st.session_state["dc_nav"] = (
    "Stage 1–3 Inputs" if nav_option == "Stage 1–3 Inputs" else "DC Block Results & Export"
)

PAGE_FILE = "dc_block_sizing.py"

if not os.path.isfile(PAGE_FILE):
    st.error(f"Page file not found: {PAGE_FILE}")
else:
    try:
        runpy.run_path(PAGE_FILE, run_name="__main__")
    except Exception as exc:
        st.error(f"Error loading Stage 1–3 page:\n{exc}")
        raise
