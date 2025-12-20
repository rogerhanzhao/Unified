import os
import runpy

import streamlit as st

st.set_page_config(page_title="CALB ESS Sizing Tool", layout="wide")
st.title("CALB ESS Sizing Tool – Stage 1–3 (DC)")
st.sidebar.info(
    "AC Block sizing is now separated into stage4_app.py for future integration. "
    "Run it in a separate Streamlit session when Stage 4 is needed."
)

PAGE_FILE = "pages/DC_Block_Sizing.py"

if not os.path.isfile(PAGE_FILE):
    st.error(f"Page file not found: {PAGE_FILE}")
else:
    try:
        runpy.run_path(PAGE_FILE, run_name="__main__")
    except Exception as exc:
        st.error(f"Error loading Stage 1–3 page:\n{exc}")
        raise
