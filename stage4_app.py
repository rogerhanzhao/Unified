import os
import runpy

import streamlit as st

st.set_page_config(page_title="CALB ESS Sizing Tool – Stage 4 (AC)", layout="wide")
st.session_state["_stage4_page_config_set"] = True
st.title("CALB ESS Sizing Tool – Stage 4 (AC Block)")
st.caption(
    "Run this app separately to explore AC Block sizing. "
    "Stage 1–3 remains in the main app.py entrypoint."
)

PAGE_FILE = "pages/AC_Block_Sizing.py"

if not os.path.isfile(PAGE_FILE):
    st.error(f"Page file not found: {PAGE_FILE}")
else:
    try:
        runpy.run_path(PAGE_FILE, run_name="__main__")
    except Exception as exc:
        st.error(f"Error loading Stage 4 page:\n{exc}")
        raise
